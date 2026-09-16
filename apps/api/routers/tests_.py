"""Test plans and runs — api-contract.md#test-plans, #test-runs.

Module named `tests_` rather than `tests` so pytest's collector doesn't
mistake it for a test package.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from packages.schemas.python.agent_io import (
    PerformanceRequirements,
    TargetDescription,
    TestPlanRequest,
)
from packages.schemas.python.entities import Metric as MetricSchema
from packages.schemas.python.entities import TestPlan as TestPlanSchema
from packages.schemas.python.entities import TestPlanStatus, TestRunStatus

from ..db import models as m
from ..deps import AppSettings, DbSession, OrchestratorDep, require_auth
from ..errors import conflict, forbidden_target, not_found, safety_limit
from ..schemas import (
    CreateTestPlanRequest,
    ErrorResponse,
    MetricsResponse,
    RunTestPlanRequest,
    TestRunProgress,
    TestRunQueuedResponse,
    TestRunStatusResponse,
    from_orm,
)
from ..tasks import execute_test_run

log = logging.getLogger(__name__)


def _dispatch(run_id: UUID) -> None:
    """Enqueue execution, tolerating a broker that's down.

    The TestRun row is already committed and genuinely is `queued` — which
    is exactly what the 202 promises. A broker outage is an operational
    problem, not a bad request, and raising here would leave the caller
    unsure whether the run exists (it does). It stays visible via
    `GET /api/test-runs/{id}` as `queued` and can be re-dispatched.

    Logged at exception level on purpose: a queue nothing is draining is
    something an operator has to see.
    """
    try:
        execute_test_run.delay(str(run_id))
    except Exception:
        log.exception("could not enqueue execution for TestRun %s — it stays queued", run_id)


router = APIRouter(prefix="/api", tags=["tests"], dependencies=[Depends(require_auth)])

ERRORS: dict[int | str, dict] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


@router.post("/tests/plan", status_code=status.HTTP_201_CREATED, responses=ERRORS)
def create_test_plan(
    body: CreateTestPlanRequest,
    db: DbSession,
    orchestrator: OrchestratorDep,
) -> TestPlanSchema:
    """Invoke the Test Planner (via the Orchestrator) and persist the plan.

    This endpoint owns validation, persistence and the HTTP shape; it does
    not own what the plan *contains* — that reasoning belongs to
    Thatayaone's agents (api-contract.md#ownership-note). The only thing
    this layer does to the agent's output is store it.
    """
    project = db.get(m.Project, body.project_id)
    if project is None:
        raise not_found("Project", body.project_id)
    target = db.get(m.Target, body.target_id)
    if target is None or target.project_id != body.project_id:
        raise not_found("Target", body.target_id)

    plan_request = TestPlanRequest(
        target_description=TargetDescription(
            application_name=body.application_name or target.name,
            user_journeys=body.user_journeys,
            expected_traffic=body.expected_traffic,
            performance_requirements=PerformanceRequirements(
                p95_ms=body.p95_ms, max_error_rate=body.max_error_rate
            ),
        ),
        objective=body.objective,
    )
    plan = orchestrator.plan_test(plan_request)

    row = m.TestPlan(
        project_id=body.project_id,
        target_id=body.target_id,
        test_type=plan.test_type,
        rationale=plan.rationale,
        target_concurrency=plan.target_concurrency,
        ramp_strategy=plan.ramp_strategy.model_dump(),
        user_journeys=plan.user_journeys,
        thresholds=plan.thresholds,
        duration=plan.duration,
        stages=[s.model_dump() for s in plan.stages],
        success_criteria=plan.success_criteria,
        controlled_variable=(
            plan.controlled_variable.model_dump() if plan.controlled_variable else None
        ),
        # Persisted as `proposed`, per the contract — approval is the
        # separate POST /api/tests/{id}/run call below.
        status=TestPlanStatus.PROPOSED,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return from_orm(TestPlanSchema, row)


@router.post("/tests/{plan_id}/run", status_code=status.HTTP_202_ACCEPTED, responses=ERRORS)
def run_test_plan(
    plan_id: UUID,
    body: RunTestPlanRequest,
    db: DbSession,
    settings: AppSettings,
) -> TestRunQueuedResponse:
    """Approve a plan and enqueue execution. Never blocks on the test."""
    plan = db.get(m.TestPlan, plan_id)
    if plan is None:
        raise not_found("TestPlan", plan_id)

    target = db.get(m.Target, body.target_id)
    if target is None:
        raise not_found("Target", body.target_id)

    # Re-checked at run time, not trusted from plan creation: the contract
    # returns 403 "if the target's authorization has been revoked since the
    # plan was created". Defence in depth, matching what the Load Engineer
    # does again immediately before invoking k6.
    if not target.authorization_confirmed or not settings.host_is_allowed(target.base_url):
        raise forbidden_target(target.base_url)

    # 409 rather than silently queueing a second run: the contract maps 409
    # to "Action conflicts with current resource state (e.g. re-running a
    # test still in_progress)".
    active = db.scalar(
        select(m.TestRun.id)
        .where(m.TestRun.test_plan_id == plan_id)
        .where(m.TestRun.status.in_([TestRunStatus.QUEUED, TestRunStatus.RUNNING]))
        .limit(1)
    )
    if active is not None:
        raise conflict(
            "run_in_progress",
            "This test plan already has a run queued or running.",
            {"test_run_id": str(active)},
        )

    # Safety ceiling. api-contract.md qualifies this with "and the plan
    # wasn't already clamped", but `clamped` is a TestRun column — no such
    # field exists on TestPlan, and at approval time there is no run yet.
    # Implemented as a straight ceiling check; the qualifier is raised in the
    # PR as a contract question rather than guessed at.
    if plan.target_concurrency > settings.max_virtual_users:
        raise safety_limit(
            "vus_over_limit",
            "Requested concurrency exceeds the configured safety ceiling.",
            {
                "requested_vus": plan.target_concurrency,
                "max_virtual_users": settings.max_virtual_users,
            },
        )

    duration = plan.duration if isinstance(plan.duration, dict) else {}
    requested_duration = duration.get("total_s")
    if (
        isinstance(requested_duration, int)
        and requested_duration > settings.max_test_duration_seconds
    ):
        raise safety_limit(
            "duration_over_limit",
            "Requested duration exceeds the configured safety ceiling.",
            {
                "requested_seconds": requested_duration,
                "max_test_duration_seconds": settings.max_test_duration_seconds,
            },
        )

    run = m.TestRun(
        test_plan_id=plan.id,
        target_id=target.id,
        status=TestRunStatus.QUEUED,
    )
    plan.status = TestPlanStatus.APPROVED
    db.add(run)
    db.commit()
    db.refresh(run)

    # Dispatched only after the commit above. Enqueueing first would race:
    # a worker can pick the job up before the transaction is visible and
    # find no such TestRun.
    _dispatch(run.id)

    return TestRunQueuedResponse(test_run_id=run.id, status=run.status)


@router.get("/test-runs/{run_id}", response_model=TestRunStatusResponse, responses=ERRORS)
def get_test_run(run_id: UUID, db: DbSession) -> TestRunStatusResponse:
    run = db.get(m.TestRun, run_id)
    if run is None:
        raise not_found("TestRun", run_id)

    plan = db.get(m.TestPlan, run.test_plan_id)
    target_vus = plan.target_concurrency if plan else 0

    # current_vus comes from the most recent recorded stage. Until the
    # worker writes stages (#13) this is 0 for a queued run and the final
    # stage's target once one exists — honest about what's known rather
    # than interpolating a number nothing measured.
    current_vus = db.scalar(
        select(m.TestStage.target_vus)
        .where(m.TestStage.test_run_id == run_id)
        .order_by(m.TestStage.sequence_index.desc())
        .limit(1)
    )

    return TestRunStatusResponse(
        id=run.id,
        status=run.status,
        progress=TestRunProgress(current_vus=current_vus or 0, target_vus=target_vus),
    )


@router.get("/test-runs/{run_id}/metrics", response_model=MetricsResponse, responses=ERRORS)
def get_test_run_metrics(run_id: UUID, db: DbSession) -> MetricsResponse:
    if db.get(m.TestRun, run_id) is None:
        raise not_found("TestRun", run_id)
    metrics = db.scalars(
        select(m.Metric).where(m.Metric.test_run_id == run_id).order_by(m.Metric.recorded_at)
    ).all()
    return MetricsResponse(metrics=[from_orm(MetricSchema, x) for x in metrics])
