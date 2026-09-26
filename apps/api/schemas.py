"""Request and response bodies for the HTTP layer.

These are the *wire* shapes api-contract.md documents. Entity responses reuse
`packages/schemas/python/entities.py` directly — those are the canonical
contract and re-declaring them here would be exactly the drift
CONTRIBUTING.md warns about. What lives in this file is only the shapes the
contract describes but `packages/schemas` doesn't: request bodies, and the
two ad-hoc response envelopes for test-run status and findings.
"""

from __future__ import annotations

from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

from packages.metrics.metrics import MetricComparison
from packages.schemas.python.agent_io import ExpectedTraffic
from packages.schemas.python.entities import (
    ExperimentStatus,
    Finding,
    InvestigationObjective,
    Metric,
    Project,
    TestRunStatus,
)

T = TypeVar("T", bound=BaseModel)


def from_orm(model_cls: type[T], row: object) -> T:
    """Convert a SQLAlchemy row into its packages/schemas counterpart.

    `from_attributes` is passed at the call site rather than set as
    `model_config` on the models themselves: those live in
    packages/schemas, which is the shared contract layer every module
    builds against. Loosening their config to suit this app's ORM would be
    a cross-owner change to serve one consumer — this keeps the coupling on
    our side of the seam.
    """
    return model_cls.model_validate(row, from_attributes=True)


# --- Projects -------------------------------------------------------------


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class ProjectSummaryResponse(Project):
    """`GET /api/projects/{id}` — "fetch a project and its summary".

    Extends the entity rather than redefining it, so a field added to
    Project shows up here automatically.
    """

    target_count: int
    latest_investigation_status: str | None = None


# --- Targets --------------------------------------------------------------


class CreateTargetRequest(BaseModel):
    base_url: str = Field(min_length=1)
    name: str = Field(min_length=1)
    # No `= True` default. The contract rejects an unconfirmed target, and a
    # default would let a caller omit the field and be treated as having
    # confirmed something they never saw.
    authorization_confirmed: bool
    authorization_confirmed_by: str | None = None


# --- Test plans and runs --------------------------------------------------


class CreateTestPlanRequest(BaseModel):
    """`POST /api/tests/plan` — TestPlanRequest plus the ids to persist against.

    api-contract.md says the body is agent_io's `TestPlanRequest`, which
    carries a target *description* but no target id. The API has to know
    which Target and Project the resulting plan belongs to, so those two ids
    are added here. Flagged in the PR as a contract clarification.
    """

    project_id: UUID
    target_id: UUID
    objective: InvestigationObjective
    user_journeys: list[str] = Field(min_length=1)
    expected_traffic: ExpectedTraffic
    p95_ms: float = Field(gt=0)
    max_error_rate: float = Field(ge=0.0, le=1.0)
    application_name: str | None = None


class RunTestPlanRequest(BaseModel):
    target_id: UUID


class TestRunQueuedResponse(BaseModel):
    test_run_id: UUID
    status: TestRunStatus


class TestRunProgress(BaseModel):
    current_vus: int
    target_vus: int


class TestRunStatusResponse(BaseModel):
    id: UUID
    status: TestRunStatus
    progress: TestRunProgress


class MetricsResponse(BaseModel):
    metrics: list[Metric]


# --- Investigations -------------------------------------------------------


class CreateInvestigationRequest(BaseModel):
    target_id: UUID
    objective: InvestigationObjective
    expected_traffic: ExpectedTraffic
    user_journeys: list[str] = Field(default_factory=lambda: ["/"])
    p95_ms: float = Field(default=500.0, gt=0)
    max_error_rate: float = Field(default=0.01, ge=0.0, le=1.0)
    application_name: str | None = None


class FindingsResponse(BaseModel):
    findings: list[Finding]


class ApproveExperimentRequest(BaseModel):
    hypothesis_id: UUID
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)


class ExperimentQueuedResponse(BaseModel):
    test_run_id: UUID
    experiment_id: UUID | None = None
    status: ExperimentStatus = ExperimentStatus.QUEUED


class ContinueInvestigationRequest(BaseModel):
    test_run_id: UUID
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Documented purely so it appears in the generated OpenAPI schema.

    Never constructed by hand — errors.py builds the body. It exists so
    `/docs` shows clients the envelope they'll get on a failure.
    """

    error: ErrorDetail


# --- Baselines (issue #34) -------------------------------------------------


class SelectBaselineRequest(BaseModel):
    """Promote a succeeded run to a named baseline for its target.

    `label` is required rather than defaulted: a baseline nobody named is one
    nobody chose deliberately, which is the situation this ticket exists to
    prevent. `idempotency_key` is optional — re-selecting the same run is
    already safe through the (target, run) uniqueness rule, so the key is for
    callers that want a safe retry before they know the run id landed.
    """

    test_run_id: UUID
    label: str = Field(min_length=1, max_length=255)
    selected_by: str = Field(min_length=1, max_length=255)
    idempotency_key: str | None = Field(default=None, max_length=255)


class BaselineRef(BaseModel):
    """The typed baseline reference #39 consumes.

    Carries the frozen compatibility identity as well as the ids, so a
    consumer can explain *why* a comparison was allowed without re-reading the
    plan.
    """

    id: UUID
    target_id: UUID
    test_run_id: UUID
    label: str
    selected_by: str
    test_type: str
    target_concurrency: int
    #: `v<n>:<sha256>` over the scenario fields listed in
    #: `apps/api/scenario_identity.py`. Opaque to the consumer: compare it for
    #: equality to tell two baselines apart, never parse it. The version prefix
    #: is what lets the rule change later without old values silently meaning
    #: something new.
    scenario_fingerprint: str


class BaselinesResponse(BaseModel):
    baselines: list[BaselineRef]


class ComparisonResponse(BaseModel):
    """A comparison against one intentionally chosen baseline.

    `comparisons` holds one entry per endpoint measured in both runs, in the
    canonical shape `packages/metrics` produces — this layer adds no fields to
    it and recomputes nothing. The `*_only_endpoints` lists name scopes
    measured in just one of the runs, so a consumer can tell a missing
    endpoint from an unchanged one.
    """

    baseline: BaselineRef
    current_test_run_id: UUID
    comparisons: list[MetricComparison]
    baseline_only_endpoints: list[str | None]
    current_only_endpoints: list[str | None]
