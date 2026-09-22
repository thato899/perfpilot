"""Celery tasks — async test execution (issue #13).

This is the EXECUTE step of data-flow.md's lifecycle, moved off the request
path. `POST /api/tests/{id}/run` returns 202 immediately and a worker picks
the run up from here; the contract promises that endpoint "never blocks on
test completion".

The task owns the TestRun's state machine and persistence. It owns none of
the reasoning: generating and running the k6 script is the Load Engineer's
(`deps.get_load_engineer()`), and deciding what happens next is the
Orchestrator's. Both implementations are resolved behind dependency seams.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import uuid
from datetime import UTC
from pathlib import Path

from sqlalchemy import select

from packages.metrics.metrics import compare_metrics, estimate_capacity
from packages.schemas.python.agent_io import (
    InvestigationAnalysisRequest,
    LoadExecutionRequest,
    LoadExecutionStatus,
    OrchestratorEvent,
    OrchestratorEventType,
    OrchestratorStep,
    RampStrategy,
    TargetRef,
    TestPlanOutput,
    TestRunMetricsRef,
    TestStagePlan,
)
from packages.schemas.python.entities import (
    ExperimentStatus,
    HypothesisStatus,
    InvestigationEventType,
    InvestigationStatus,
    TestRunStatus,
    TestType,
)

from .celery_app import celery_app
from .db import models as m
from .db.base import SessionLocal
from .deps import get_load_engineer, get_orchestrator
from .investigation_state import append_event
from .load_engineer_stub import TargetNotAllowedError

log = logging.getLogger(__name__)

_TERMINAL_STATUS = {
    LoadExecutionStatus.SUCCEEDED: TestRunStatus.SUCCEEDED,
    LoadExecutionStatus.FAILED: TestRunStatus.FAILED,
    LoadExecutionStatus.ABORTED_OVER_LIMIT: TestRunStatus.ABORTED_OVER_LIMIT,
}


def _plan_to_output(plan: m.TestPlan) -> TestPlanOutput:
    """Rebuild the planner's output shape from the persisted row.

    The Load Engineer's input is a `TestPlanOutput`, not a database row —
    keeping that boundary means the wrapper never has to know this app's
    ORM, which is what lets Govenor develop it against a fixture.
    """
    return TestPlanOutput(
        test_type=TestType(plan.test_type),
        rationale=plan.rationale,
        target_concurrency=plan.target_concurrency,
        ramp_strategy=RampStrategy(**plan.ramp_strategy),
        user_journeys=list(plan.user_journeys),
        thresholds=dict(plan.thresholds),
        duration=dict(plan.duration),
        stages=[TestStagePlan(**stage) for stage in plan.stages],
        success_criteria=list(plan.success_criteria),
        controlled_variable=(plan.controlled_variable if plan.controlled_variable else None),
    )


@celery_app.task(
    name="perfpilot.execute_test_run",
    bind=True,
    max_retries=0,
    # The return value is never consumed — the TestRun row *is* the result,
    # and that's what the dashboard polls. Storing it would also make
    # `.delay()` touch the Redis result backend from inside an HTTP request
    # handler, whose retry policy is ~20 attempts: with Redis down, that
    # turned a 202 into a 19-second hang. With this it fails in ~2s, and the
    # caller still gets its 202 because the row is committed either way.
    ignore_result=True,
)
def execute_test_run(self, test_run_id: str) -> dict:  # noqa: ANN001, ARG001
    """Take a queued TestRun through to a terminal state.

    max_retries=0 deliberately. Celery's default retry would re-run a *load
    test* against someone's application — the one operation in this system
    that must never happen again just because a database write blipped. A
    failed run is recorded as failed and left for a human to re-trigger.
    """
    run_uuid = uuid.UUID(test_run_id)
    session = SessionLocal()
    try:
        run = session.get(m.TestRun, run_uuid)
        if run is None:
            log.warning("execute_test_run: no TestRun %s", test_run_id)
            return {"test_run_id": test_run_id, "status": "not_found"}

        # Idempotency guard. A duplicate delivery (Celery is at-least-once)
        # must not start a second load test against the same target.
        if run.status is not TestRunStatus.QUEUED:
            log.info("execute_test_run: %s is %s, not queued", test_run_id, run.status)
            return {"test_run_id": test_run_id, "status": run.status.value, "skipped": True}

        plan = session.get(m.TestPlan, run.test_plan_id)
        target = session.get(m.Target, run.target_id)
        if plan is None or target is None:
            run.status = TestRunStatus.FAILED
            _fail_linked_investigation(session, run_uuid)
            session.commit()
            return {"test_run_id": test_run_id, "status": run.status.value}

        run.status = TestRunStatus.RUNNING
        run.started_at = _utcnow()
        linked_experiment = session.scalar(
            select(m.Experiment).where(m.Experiment.test_run_id == run.id)
        )
        if linked_experiment is not None:
            linked_experiment.status = ExperimentStatus.RUNNING
        session.commit()
        investigation = session.scalar(
            select(m.Investigation).where(m.Investigation.current_test_run_id == run.id)
        )
        if investigation is not None:
            append_event(
                session,
                investigation.id,
                InvestigationEventType.TEST_RUN_STARTED,
                {"test_run_id": str(run.id)},
                idempotency_key=f"test-run-started:{run.id}",
            )
            session.commit()

        request = LoadExecutionRequest(
            test_plan=_plan_to_output(plan),
            # A credential *reference*, never a raw secret — the schema
            # comment on TargetRef.auth is explicit, and this payload is
            # serialized through the broker.
            target=TargetRef(base_url=target.base_url, auth=None),
            test_run_id=run_uuid,
        )

        try:
            result = get_load_engineer().execute(request)
        except TargetNotAllowedError:
            # Allow-listed when the run was queued, removed before it ran.
            # Recorded as aborted rather than failed: nothing went wrong
            # technically, the system refused on purpose.
            log.warning("execute_test_run: %s target no longer allow-listed", test_run_id)
            run.status = TestRunStatus.ABORTED_OVER_LIMIT
            run.completed_at = _utcnow()
            _fail_linked_investigation(session, run_uuid)
            session.commit()
            return {"test_run_id": test_run_id, "status": run.status.value}
        except Exception:
            log.exception("execute_test_run: %s failed in the execution wrapper", test_run_id)
            run.status = TestRunStatus.FAILED
            run.completed_at = _utcnow()
            _fail_linked_investigation(session, run_uuid)
            session.commit()
            return {"test_run_id": test_run_id, "status": run.status.value}

        _persist_result(session, run, plan, result)
        session.commit()

        if run.status is TestRunStatus.SUCCEEDED:
            _advance_investigation(session, run_uuid)
        else:
            _fail_linked_investigation(session, run_uuid)
            session.commit()
        return {"test_run_id": test_run_id, "status": run.status.value}
    finally:
        session.close()


def _utcnow():  # noqa: ANN202
    from datetime import datetime

    return datetime.now(UTC)


def _fail_linked_investigation(session, test_run_id: uuid.UUID) -> None:  # noqa: ANN001
    experiment = session.scalar(select(m.Experiment).where(m.Experiment.test_run_id == test_run_id))
    if experiment is not None and experiment.status not in {
        ExperimentStatus.SUCCEEDED,
        ExperimentStatus.FAILED,
        ExperimentStatus.REJECTED,
    }:
        experiment.status = ExperimentStatus.FAILED
    investigation = session.scalar(
        select(m.Investigation).where(m.Investigation.current_test_run_id == test_run_id)
    )
    if investigation and investigation.status not in {
        InvestigationStatus.COMPLETE,
        InvestigationStatus.FAILED,
    }:
        investigation.status = InvestigationStatus.FAILED


def _persist_result(session, run: m.TestRun, plan: m.TestPlan, result) -> None:  # noqa: ANN001
    """Write the wrapper's output into the schema #11 defined."""
    run.status = _TERMINAL_STATUS[result.status]
    run.k6_script_ref = result.k6_script_ref
    run.raw_output_ref = result.raw_output_ref
    run.clamped = result.clamped.model_dump() if result.clamped else None
    run.completed_at = _utcnow()
    experiment = session.scalar(select(m.Experiment).where(m.Experiment.test_run_id == run.id))
    if experiment is not None:
        experiment.status = {
            LoadExecutionStatus.SUCCEEDED: ExperimentStatus.SUCCEEDED,
            LoadExecutionStatus.FAILED: ExperimentStatus.FAILED,
            LoadExecutionStatus.ABORTED_OVER_LIMIT: ExperimentStatus.FAILED,
        }[result.status]
        investigation = session.scalar(
            select(m.Investigation).where(m.Investigation.current_test_run_id == run.id)
        )
        if investigation is not None:
            append_event(
                session,
                investigation.id,
                InvestigationEventType.EXPERIMENT_COMPLETED,
                {
                    "experiment_id": str(experiment.id),
                    "test_run_id": str(run.id),
                    "status": experiment.status.value,
                },
                idempotency_key=f"experiment-completed:{experiment.id}",
            )

    # Denormalized at execution time so a run's *actual* stage progression,
    # including any clamping, is recorded independently of what was planned
    # — database-design.md is explicit about this being the point of the
    # table. The executed ceiling caps each stage, not just the total.
    executed_ceiling = result.clamped.executed_vus if result.clamped else None
    for index, stage in enumerate(plan.stages):
        target_vus = stage["target_vus"]
        if executed_ceiling is not None:
            target_vus = min(target_vus, executed_ceiling)
        session.add(
            m.TestStage(
                test_run_id=run.id,
                target_vus=target_vus,
                duration_s=stage["duration_s"],
                sequence_index=index,
            )
        )

    for metric in result.metrics:
        session.add(
            m.Metric(
                # The wrapper's id is ignored: it was generated outside this
                # database and nothing guarantees it's unique here.
                test_run_id=run.id,
                endpoint=metric.endpoint,
                p50_ms=metric.p50_ms,
                p90_ms=metric.p90_ms,
                p95_ms=metric.p95_ms,
                p99_ms=metric.p99_ms,
                throughput_rps=metric.throughput_rps,
                error_rate=metric.error_rate,
                concurrency=metric.concurrency,
                http_status_distribution=metric.http_status_distribution,
                recorded_at=metric.recorded_at,
            )
        )


def _advance_investigation(session, test_run_id: uuid.UUID) -> None:  # noqa: ANN001
    """The completion callback — data-flow.md's OBSERVE -> INVESTIGATE hop.

    Only investigations that already point at this run are advanced. A
    standalone test run (one triggered outside an investigation) has no
    state machine to move, and inventing one here would put the API in the
    business of deciding investigation flow, which is the Orchestrator's.

    Failures are logged, not raised: the test run itself genuinely
    completed, and marking it failed because a downstream decision errored
    would misreport what happened.
    """
    investigation = session.scalar(
        select(m.Investigation).where(m.Investigation.current_test_run_id == test_run_id)
    )
    if investigation is None:
        return

    try:
        from .routers.investigations import _load_state

        current_run = session.get(m.TestRun, test_run_id)
        plan = session.get(m.TestPlan, current_run.test_plan_id) if current_run else None
        if current_run is None or plan is None or not current_run.metrics:
            raise ValueError("completed investigation run has no plan or metrics")

        if investigation.status in {
            InvestigationStatus.PLANNING,
            InvestigationStatus.RUNNING,
            InvestigationStatus.EXPERIMENTING,
        }:
            investigation.status = InvestigationStatus.INVESTIGATING
            session.flush()

        baseline_run = (
            session.get(m.TestRun, investigation.baseline_test_run_id)
            if investigation.baseline_test_run_id
            else current_run
        )
        if baseline_run is None or not baseline_run.metrics:
            raise ValueError("investigation baseline has no metrics")

        analysis = _run_investigator(
            current_run,
            baseline_run,
            plan,
            _load_state(session, investigation),
        )
        _persist_investigator_output(session, investigation, analysis)
        session.flush()

        append_event(
            session,
            investigation.id,
            InvestigationEventType.TEST_RUN_COMPLETED,
            {"test_run_id": str(test_run_id), "status": "succeeded"},
            idempotency_key=f"test-run-completed:{test_run_id}",
        )

        decision = get_orchestrator().step(
            OrchestratorStep(
                investigation_state=_load_state(session, investigation),
                event=OrchestratorEvent(
                    type=OrchestratorEventType.TEST_RUN_COMPLETED,
                    payload={"test_run_id": str(test_run_id), "status": "succeeded"},
                ),
            )
        )
        if (
            decision.next_action.value == "invoke_reporting_agent"
            and investigation.experiments_run >= investigation.max_experiments
        ):
            append_event(
                session,
                investigation.id,
                InvestigationEventType.BUDGET_EXHAUSTED,
                {
                    "consumed": investigation.experiments_run,
                    "max_experiments": investigation.max_experiments,
                },
                idempotency_key=f"budget-exhausted:{investigation.id}",
            )
        investigation.status = InvestigationStatus(decision.updated_state.status)
        if decision.next_action.value == "invoke_reporting_agent":
            _persist_report(session, investigation, current_run, baseline_run, plan)
            append_event(
                session,
                investigation.id,
                InvestigationEventType.REPORT_PERSISTED,
                {"investigation_id": str(investigation.id)},
                idempotency_key=f"report-persisted:{investigation.id}",
            )
            investigation.status = InvestigationStatus.COMPLETE
        session.commit()
    except Exception:
        log.exception("execute_test_run: could not advance investigation %s", investigation.id)
        session.rollback()
        failed = session.get(m.Investigation, investigation.id)
        if failed and failed.status not in {
            InvestigationStatus.COMPLETE,
            InvestigationStatus.FAILED,
        }:
            failed.status = InvestigationStatus.FAILED
            session.commit()


def _load_investigator_module():
    path = Path(__file__).parents[2] / "agents" / "performance-investigator" / "investigator.py"
    spec = importlib.util.spec_from_file_location("perfpilot_investigator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Performance Investigator module is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _metric_schema(row: m.Metric):
    from packages.schemas.python.entities import Metric

    return Metric.model_validate(row, from_attributes=True)


def _run_investigator(current, baseline, plan, state):  # noqa: ANN001
    module = _load_investigator_module()
    current_metrics = [_metric_schema(metric) for metric in current.metrics]
    baseline_metrics = [_metric_schema(metric) for metric in baseline.metrics]
    comparison = compare_metrics(baseline_metrics[-1], current_metrics[-1])
    request = InvestigationAnalysisRequest(
        test_run=TestRunMetricsRef(id=current.id, metrics=current_metrics),
        baseline_test_run=TestRunMetricsRef(id=baseline.id, metrics=baseline_metrics),
        comparison=comparison.model_dump(mode="json"),
        thresholds=dict(plan.thresholds),
        prior_hypotheses=state.hypotheses or None,
        infrastructure_metrics=None,
    )
    return module.PerformanceInvestigator().analyze(request)


def _persist_investigator_output(session, investigation, output) -> None:  # noqa: ANN001
    finding = session.scalar(
        select(m.Finding).where(m.Finding.investigation_id == investigation.id).limit(1)
    )
    if finding is None:
        finding = m.Finding(
            investigation_id=investigation.id,
            severity=output.finding.severity,
            summary=output.finding.summary,
            observations=[observation.model_dump() for observation in output.observations],
            sequence_index=0,
        )
        session.add(finding)
        session.flush()
    else:
        finding.severity = output.finding.severity
        finding.summary = output.finding.summary
        finding.observations = [observation.model_dump() for observation in output.observations]

    append_event(
        session,
        investigation.id,
        InvestigationEventType.FINDING_RECORDED,
        {"finding_id": str(finding.id)},
        idempotency_key=f"finding-recorded:{finding.id}",
    )

    for sequence_index, hypothesis_output in enumerate(output.hypotheses):
        hypothesis = session.scalar(
            select(m.Hypothesis)
            .where(m.Hypothesis.finding_id == finding.id)
            .where(m.Hypothesis.statement == hypothesis_output.statement)
            .limit(1)
        )
        status = (
            HypothesisStatus.SUPPORTED
            if hypothesis_output.confidence >= 0.8
            else HypothesisStatus.TESTING
        )
        if hypothesis is None:
            session.add(
                m.Hypothesis(
                    finding_id=finding.id,
                    statement=hypothesis_output.statement,
                    confidence=hypothesis_output.confidence,
                    status=status,
                    evidence=[e.model_dump() for e in hypothesis_output.evidence],
                    recommended_experiment=(
                        hypothesis_output.recommended_experiment.model_dump()
                        if hypothesis_output.recommended_experiment
                        else None
                    ),
                    sequence_index=sequence_index,
                )
            )
            session.flush()
            hypothesis = session.scalar(
                select(m.Hypothesis)
                .where(m.Hypothesis.finding_id == finding.id)
                .where(m.Hypothesis.statement == hypothesis_output.statement)
                .limit(1)
            )
        else:
            hypothesis.confidence = hypothesis_output.confidence
            hypothesis.status = status
            hypothesis.evidence = [e.model_dump() for e in hypothesis_output.evidence]

        if hypothesis is not None and hypothesis_output.recommended_experiment:
            proposed = session.scalar(
                select(m.Experiment)
                .where(m.Experiment.hypothesis_id == hypothesis.id)
                .where(m.Experiment.status == ExperimentStatus.PROPOSED)
                .order_by(m.Experiment.sequence_index, m.Experiment.created_at)
                .limit(1)
            )
            if proposed is None:
                proposed = m.Experiment(
                    hypothesis_id=hypothesis.id,
                    variable_changed=hypothesis_output.recommended_experiment.variable_to_isolate,
                    baseline_value=None,
                    experiment_value=hypothesis_output.recommended_experiment.change,
                    status=ExperimentStatus.PROPOSED,
                    sequence_index=sequence_index,
                )
                session.add(proposed)
                session.flush()
                append_event(
                    session,
                    investigation.id,
                    InvestigationEventType.EXPERIMENT_PROPOSED,
                    {
                        "experiment_id": str(proposed.id),
                        "hypothesis_id": str(hypothesis.id),
                    },
                    idempotency_key=f"experiment-proposed:{proposed.id}",
                )

        append_event(
            session,
            investigation.id,
            InvestigationEventType.HYPOTHESIS_RECORDED,
            {"hypothesis_id": str(hypothesis.id)},
            idempotency_key=f"hypothesis-recorded:{hypothesis.id}",
        )


def _persist_report(session, investigation, current, baseline, plan) -> None:  # noqa: ANN001
    from agents.reporting.report_builder import build_report
    from packages.schemas.python.agent_io import (
        CapacityEstimate,
        RegressionComparison,
        ReportRequest,
    )

    from .routers.investigations import _load_state

    current_metric = _metric_schema(current.metrics[-1])
    baseline_metric = _metric_schema(baseline.metrics[-1])
    thresholds = dict(plan.thresholds)
    capacity = estimate_capacity(
        [_metric_schema(metric) for metric in current.metrics],
        p95_ms=thresholds["p95_ms"],
        max_error_rate=thresholds["max_error_rate"],
    )
    report = build_report(
        ReportRequest(
            investigation_id=investigation.id,
            investigation_state=_load_state(session, investigation),
            capacity_estimate=CapacityEstimate(**capacity),
            regression_comparison=RegressionComparison(
                previous_p95_ms=baseline_metric.p95_ms,
                current_p95_ms=current_metric.p95_ms,
                regression_pct=compare_metrics(baseline_metric, current_metric).p95_delta_pct,
            ),
            key_metrics={
                "throughput_rps": current_metric.throughput_rps,
                "p50_ms": current_metric.p50_ms,
                "p95_ms": current_metric.p95_ms,
                "p99_ms": current_metric.p99_ms,
                "error_rate": current_metric.error_rate,
                "peak_concurrency_tested": current_metric.concurrency,
            },
        )
    )
    existing = session.scalar(
        select(m.Report).where(m.Report.investigation_id == investigation.id).limit(1)
    )
    values = {
        "executive_summary": report.executive_summary,
        "capacity": report.capacity.model_dump(),
        "key_metrics": report.key_metrics,
        "bottleneck_analysis": [entry.model_dump() for entry in report.bottleneck_analysis],
        "regression": report.regression.model_dump(),
    }
    if existing is None:
        session.add(m.Report(investigation_id=investigation.id, **values))
    else:
        for key, value in values.items():
            setattr(existing, key, value)

    # Recommendations keep their canonical Hypothesis relationship. Reporting
    # emits the persisted Finding id; choose that finding's highest-confidence
    # hypothesis rather than inventing a second recommendation relationship.
    for sequence_index, recommendation in enumerate(report.recommendations):
        try:
            finding_id = uuid.UUID(recommendation.finding_id)
        except (TypeError, ValueError):
            continue
        hypothesis = session.scalar(
            select(m.Hypothesis)
            .where(m.Hypothesis.finding_id == finding_id)
            .order_by(m.Hypothesis.confidence.desc(), m.Hypothesis.created_at)
            .limit(1)
        )
        if hypothesis is None:
            continue
        row = session.scalar(
            select(m.Recommendation)
            .where(m.Recommendation.hypothesis_id == hypothesis.id)
            .where(m.Recommendation.statement == recommendation.statement)
            .limit(1)
        )
        if row is None:
            row = m.Recommendation(
                hypothesis_id=hypothesis.id,
                statement=recommendation.statement,
                priority=recommendation.priority,
                sequence_index=sequence_index,
            )
            session.add(row)
            session.flush()
        else:
            row.priority = recommendation.priority
            row.sequence_index = sequence_index
        append_event(
            session,
            investigation.id,
            InvestigationEventType.RECOMMENDATION_RECORDED,
            {"recommendation_id": str(row.id), "hypothesis_id": str(hypothesis.id)},
            idempotency_key=f"recommendation-recorded:{row.id}",
        )
