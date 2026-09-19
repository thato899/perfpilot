"""Investigations and reports — api-contract.md#investigations, #reports."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.schemas.python.agent_io import (
    InvestigationState,
    PerformanceRequirements,
    TargetDescription,
    TestPlanRequest,
)
from packages.schemas.python.entities import Finding as FindingSchema
from packages.schemas.python.entities import Investigation as InvestigationSchema
from packages.schemas.python.entities import (
    InvestigationStatus,
    TestPlanStatus,
    TestRunStatus,
)
from packages.schemas.python.entities import Report as ReportSchema

from ..db import models as m
from ..deps import AppSettings, DbSession, OrchestratorDep, require_auth
from ..errors import conflict, forbidden_target, not_found
from ..schemas import (
    ApproveExperimentRequest,
    ContinueInvestigationRequest,
    CreateInvestigationRequest,
    ErrorResponse,
    ExperimentQueuedResponse,
    FindingsResponse,
    from_orm,
)

router = APIRouter(prefix="/api", tags=["investigations"], dependencies=[Depends(require_auth)])

ERRORS: dict[int | str, dict] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _load_state(db: Session, investigation: m.Investigation) -> InvestigationState:
    """Project the persisted rows into the Orchestrator's InvestigationState.

    data-flow.md makes the Orchestrator the only writer of this object; the
    API's job is to assemble the read-side view of it from what's stored, so
    the dashboard and the Orchestrator see the same shape.
    """
    findings = db.scalars(
        select(m.Finding).where(m.Finding.investigation_id == investigation.id)
    ).all()
    finding_ids = [f.id for f in findings]
    hypotheses = (
        db.scalars(select(m.Hypothesis).where(m.Hypothesis.finding_id.in_(finding_ids))).all()
        if finding_ids
        else []
    )
    experiments = (
        db.scalars(
            select(m.Experiment).where(m.Experiment.hypothesis_id.in_([h.id for h in hypotheses]))
        ).all()
        if hypotheses
        else []
    )

    return InvestigationState(
        investigation_id=investigation.id,
        target_id=investigation.target_id,
        status=investigation.status.value,
        baseline_test_run_id=investigation.baseline_test_run_id,
        current_test_run_id=investigation.current_test_run_id,
        findings=[
            {
                "id": str(f.id),
                "investigation_id": str(f.investigation_id),
                "severity": f.severity.value,
                "summary": f.summary,
                "observations": f.observations,
            }
            for f in findings
        ],
        hypotheses=[
            {
                "id": str(h.id),
                "finding_id": str(h.finding_id),
                "statement": h.statement,
                "confidence": h.confidence,
                "status": h.status.value,
                "evidence": h.evidence,
                "recommended_experiment": h.recommended_experiment,
            }
            for h in hypotheses
        ],
        experiments=[
            {
                "id": str(e.id),
                "hypothesis_id": str(e.hypothesis_id),
                "variable_changed": e.variable_changed,
                "from": e.baseline_value,
                "to": e.experiment_value,
                "test_run_id": str(e.test_run_id),
            }
            for e in experiments
        ],
    )


@router.post("/investigations", status_code=status.HTTP_201_CREATED, responses=ERRORS)
def create_investigation(
    body: CreateInvestigationRequest,
    db: DbSession,
    settings: AppSettings,
    orchestrator: OrchestratorDep,
) -> InvestigationSchema:
    """Start an investigation — kicks off UNDERSTAND -> PLAN."""
    target = db.get(m.Target, body.target_id)
    if target is None:
        raise not_found("Target", body.target_id)
    if not target.authorization_confirmed or not settings.host_is_allowed(target.base_url):
        raise forbidden_target(target.base_url)

    investigation = m.Investigation(
        project_id=target.project_id,
        target_id=target.id,
        objective=body.objective,
        status=InvestigationStatus.PLANNING,
    )
    db.add(investigation)
    db.commit()
    db.refresh(investigation)

    db.commit()

    # The initial planner/run link is part of the investigation lifecycle,
    # not a second frontend-only workflow. The current TestRun points to its
    # TestPlan, so current_test_run_id is the authoritative active-plan edge.
    try:
        decision = orchestrator.start_investigation(investigation.id, target.id)
        if decision.next_action.value != "invoke_test_planner":
            raise RuntimeError("initial investigation did not request Test Planner")
        plan = orchestrator.plan_test(
            TestPlanRequest(
                target_description=TargetDescription(
                    application_name=body.application_name or target.name,
                    user_journeys=body.user_journeys,
                    expected_traffic=body.expected_traffic,
                    performance_requirements=PerformanceRequirements(
                        p95_ms=body.p95_ms,
                        max_error_rate=body.max_error_rate,
                    ),
                ),
                objective=body.objective,
            )
        )
        plan_row = m.TestPlan(
            project_id=target.project_id,
            target_id=target.id,
            test_type=plan.test_type,
            rationale=plan.rationale,
            target_concurrency=plan.target_concurrency,
            ramp_strategy=plan.ramp_strategy.model_dump(),
            user_journeys=plan.user_journeys,
            thresholds=plan.thresholds,
            duration=plan.duration,
            stages=[stage.model_dump() for stage in plan.stages],
            success_criteria=plan.success_criteria,
            controlled_variable=(
                plan.controlled_variable.model_dump() if plan.controlled_variable else None
            ),
            status=TestPlanStatus.APPROVED,
        )
        db.add(plan_row)
        db.flush()
        from .tests_ import _dispatch, validate_run_limits

        validate_run_limits(plan_row, settings)
        run = m.TestRun(
            test_plan_id=plan_row.id,
            target_id=target.id,
            status=TestRunStatus.QUEUED,
        )
        db.add(run)
        db.flush()
        investigation.current_test_run_id = run.id
        investigation.status = InvestigationStatus.RUNNING
        db.commit()
        db.refresh(investigation)
        _dispatch(run.id)
    except Exception:
        db.rollback()
        failed = db.get(m.Investigation, investigation.id)
        if failed is not None and failed.status not in {
            InvestigationStatus.COMPLETE,
            InvestigationStatus.FAILED,
        }:
            failed.status = InvestigationStatus.FAILED
            db.commit()
        raise

    return from_orm(InvestigationSchema, investigation)


@router.get("/investigations/{investigation_id}", responses=ERRORS)
def get_investigation(investigation_id: UUID, db: DbSession) -> InvestigationState:
    investigation = db.get(m.Investigation, investigation_id)
    if investigation is None:
        raise not_found("Investigation", investigation_id)
    return _load_state(db, investigation)


@router.get(
    "/investigations/{investigation_id}/findings",
    response_model=FindingsResponse,
    responses=ERRORS,
)
def get_findings(investigation_id: UUID, db: DbSession) -> FindingsResponse:
    if db.get(m.Investigation, investigation_id) is None:
        raise not_found("Investigation", investigation_id)
    findings = db.scalars(
        select(m.Finding).where(m.Finding.investigation_id == investigation_id)
        # Ranked, per the contract's "fetch just the ranked findings".
        # Severity is a Postgres enum declared worst-first, so its natural
        # sort order is already the ranking.
        .order_by(m.Finding.severity)
    ).all()
    return FindingsResponse(findings=[from_orm(FindingSchema, f) for f in findings])


@router.post(
    "/investigations/{investigation_id}/experiments",
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERRORS,
)
def approve_experiment(
    investigation_id: UUID,
    body: ApproveExperimentRequest,
    db: DbSession,
    settings: AppSettings,
) -> ExperimentQueuedResponse:
    """The human-in-the-loop gate before more load is generated.

    security-model.md: the Orchestrator may *recommend* an experiment, but
    nothing generates additional load until it's explicitly approved here.
    """
    investigation = db.get(m.Investigation, investigation_id)
    if investigation is None:
        raise not_found("Investigation", investigation_id)

    hypothesis = db.get(m.Hypothesis, body.hypothesis_id)
    if hypothesis is None:
        raise not_found("Hypothesis", body.hypothesis_id)
    if hypothesis.finding.investigation_id != investigation.id:
        raise conflict(
            "invalid_investigation_hypothesis",
            "The Hypothesis does not belong to this investigation.",
            {"hypothesis_id": str(body.hypothesis_id)},
        )

    if not hypothesis.recommended_experiment:
        raise conflict(
            "no_recommended_experiment",
            "This hypothesis has no recommended experiment to approve.",
            {"hypothesis_id": str(body.hypothesis_id)},
        )

    if investigation.experiments_run >= settings.max_experiments_per_investigation:
        raise conflict(
            "experiment_budget_exhausted",
            "This investigation has already used its experiment budget.",
            {
                "experiments_run": investigation.experiments_run,
                "max_experiments": settings.max_experiments_per_investigation,
            },
        )

    # The follow-up plan is the Test Planner's output in the real flow. Until
    # that exists, the experiment reuses the investigation's current plan so
    # the FK chain (Experiment -> TestPlan, TestRun) is real rather than
    # dangling. #13 replaces this with a planner call.
    plan = db.scalar(
        select(m.TestPlan)
        .where(m.TestPlan.target_id == investigation.target_id)
        .order_by(m.TestPlan.created_at.desc())
        .limit(1)
    )
    if plan is None:
        raise conflict(
            "no_test_plan",
            "No test plan exists for this investigation's target yet.",
            {"target_id": str(investigation.target_id)},
        )

    run = m.TestRun(
        test_plan_id=plan.id, target_id=investigation.target_id, status=TestRunStatus.QUEUED
    )
    db.add(run)
    db.flush()
    db.add(
        m.Experiment(
            hypothesis_id=hypothesis.id,
            test_plan_id=plan.id,
            test_run_id=run.id,
            variable_changed=hypothesis.recommended_experiment.get(
                "variable_to_isolate", "unknown"
            ),
            baseline_value=None,
            experiment_value=None,
        )
    )
    investigation.experiments_run += 1
    investigation.status = InvestigationStatus.RUNNING
    plan.status = TestPlanStatus.APPROVED
    # The approved experiment becomes the investigation's current run, which
    # is what lets the worker's completion callback find it again.
    investigation.current_test_run_id = run.id
    db.commit()
    db.refresh(run)

    # After the commit, and tolerant of a down broker — see tests_._dispatch.
    from .tests_ import _dispatch

    _dispatch(run.id)
    return ExperimentQueuedResponse(test_run_id=run.id)


@router.post("/investigations/{investigation_id}/continue", responses=ERRORS)
def continue_investigation(
    investigation_id: UUID,
    body: ContinueInvestigationRequest,
    db: DbSession,
    orchestrator: OrchestratorDep,
) -> dict:
    """Advance the investigation given the latest completed run.

    Called by the Celery worker's completion callback (#13) and by a manual
    "continue" in the dashboard. Returns the Orchestrator's decision
    verbatim — this layer persists the state it comes back with and adds
    nothing to it.
    """
    investigation = db.get(m.Investigation, investigation_id)
    if investigation is None:
        raise not_found("Investigation", investigation_id)
    run = db.get(m.TestRun, body.test_run_id)
    if run is None:
        raise not_found("TestRun", body.test_run_id)
    if run.target_id != investigation.target_id:
        raise conflict(
            "invalid_investigation_run",
            "The TestRun does not belong to this investigation target.",
            {"test_run_id": str(body.test_run_id)},
        )

    decision = orchestrator.continue_investigation(_load_state(db, investigation), body.test_run_id)
    investigation.status = InvestigationStatus(decision.updated_state.status)
    investigation.current_test_run_id = decision.updated_state.current_test_run_id
    db.commit()
    return decision.model_dump(mode="json")


@router.get("/reports/{investigation_id}", responses=ERRORS)
def get_report(investigation_id: UUID, db: DbSession) -> ReportSchema:
    """Fetch a completed report.

    404 until the investigation reaches reporting/complete — the contract is
    explicit that this endpoint does not auto-generate a partial report.
    """
    report = db.scalar(select(m.Report).where(m.Report.investigation_id == investigation_id))
    if report is None:
        raise not_found("Report", investigation_id)
    return from_orm(ReportSchema, report)
