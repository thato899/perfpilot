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

from packages.schemas.python.agent_io import ExpectedTraffic
from packages.schemas.python.entities import (
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


class FindingsResponse(BaseModel):
    findings: list[Finding]


class ApproveExperimentRequest(BaseModel):
    hypothesis_id: UUID


class ExperimentQueuedResponse(BaseModel):
    test_run_id: UUID


class ContinueInvestigationRequest(BaseModel):
    test_run_id: UUID


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
