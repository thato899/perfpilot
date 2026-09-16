"""Celery tasks — async test execution (issue #13).

This is the EXECUTE step of data-flow.md's lifecycle, moved off the request
path. `POST /api/tests/{id}/run` returns 202 immediately and a worker picks
the run up from here; the contract promises that endpoint "never blocks on
test completion".

The task owns the TestRun's state machine and persistence. It owns none of
the reasoning: generating and running the k6 script is the Load Engineer's
(`deps.get_load_engineer()`), and deciding what happens next is the
Orchestrator's. Both are stubs today, both behind seams.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC

from sqlalchemy import select

from packages.schemas.python.agent_io import (
    LoadExecutionRequest,
    LoadExecutionStatus,
    RampStrategy,
    TargetRef,
    TestPlanOutput,
    TestStagePlan,
)
from packages.schemas.python.entities import (
    InvestigationStatus,
    TestRunStatus,
    TestType,
)

from .celery_app import celery_app
from .db import models as m
from .db.base import SessionLocal
from .deps import get_load_engineer, get_orchestrator
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
            session.commit()
            return {"test_run_id": test_run_id, "status": run.status.value}

        run.status = TestRunStatus.RUNNING
        run.started_at = _utcnow()
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
            session.commit()
            return {"test_run_id": test_run_id, "status": run.status.value}
        except Exception:
            log.exception("execute_test_run: %s failed in the execution wrapper", test_run_id)
            run.status = TestRunStatus.FAILED
            run.completed_at = _utcnow()
            session.commit()
            return {"test_run_id": test_run_id, "status": run.status.value}

        _persist_result(session, run, plan, result)
        session.commit()

        _advance_investigation(session, run_uuid)
        return {"test_run_id": test_run_id, "status": run.status.value}
    finally:
        session.close()


def _utcnow():  # noqa: ANN202
    from datetime import datetime

    return datetime.now(UTC)


def _persist_result(session, run: m.TestRun, plan: m.TestPlan, result) -> None:  # noqa: ANN001
    """Write the wrapper's output into the schema #11 defined."""
    run.status = _TERMINAL_STATUS[result.status]
    run.k6_script_ref = result.k6_script_ref
    run.raw_output_ref = result.raw_output_ref
    run.clamped = result.clamped.model_dump() if result.clamped else None
    run.completed_at = _utcnow()

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

        decision = get_orchestrator().continue_investigation(
            _load_state(session, investigation), test_run_id
        )
        investigation.status = InvestigationStatus(decision.updated_state.status)
        session.commit()
    except Exception:
        log.exception("execute_test_run: could not advance investigation %s", investigation.id)
        session.rollback()
