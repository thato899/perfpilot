"""Database-backed entity contracts.

Mirrors docs/database/database-design.md — that document is the prose source
of truth; this file is the typed contract other packages import against.

This is a Phase 0 CONTRACT, not a running implementation: it declares shape
only. ORM mapping (SQLAlchemy models), migrations, and persistence logic are
Phase 1 work owned by Developer 3/Kamogelo (see docs/development/team-workflow.md).
No business logic belongs in this file — see packages/schemas/README.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------


class TestType(str, Enum):
    LOAD = "load"
    STRESS = "stress"
    SPIKE = "spike"
    ENDURANCE = "endurance"
    CAPACITY = "capacity"
    BASELINE = "baseline"
    REGRESSION = "regression"


class TestPlanStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class TestRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED_OVER_LIMIT = "aborted_over_limit"


class InvestigationObjective(str, Enum):
    DETERMINE_CAPACITY = "determine_capacity"
    DIAGNOSE_REGRESSION = "diagnose_regression"
    VALIDATE_FIX = "validate_fix"
    BASELINE = "baseline"


class InvestigationStatus(str, Enum):
    PLANNING = "planning"
    RUNNING = "running"
    INVESTIGATING = "investigating"
    EXPERIMENTING = "experimenting"
    REPORTING = "reporting"
    COMPLETE = "complete"
    FAILED = "failed"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    TESTING = "testing"
    SUPPORTED = "supported"
    REJECTED = "rejected"


class ExperimentStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"


class InvestigationEventType(str, Enum):
    INVESTIGATION_CREATED = "investigation_created"
    TEST_RUN_QUEUED = "test_run_queued"
    TEST_RUN_STARTED = "test_run_started"
    TEST_RUN_COMPLETED = "test_run_completed"
    FINDING_RECORDED = "finding_recorded"
    HYPOTHESIS_RECORDED = "hypothesis_recorded"
    EXPERIMENT_PROPOSED = "experiment_proposed"
    EXPERIMENT_APPROVED = "experiment_approved"
    EXPERIMENT_STARTED = "experiment_started"
    EXPERIMENT_COMPLETED = "experiment_completed"
    RECOMMENDATION_RECORDED = "recommendation_recorded"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CONTINUE_REQUESTED = "continue_requested"
    REPORT_PERSISTED = "report_persisted"


class ExperimentConclusion(str, Enum):
    HYPOTHESIS_SUPPORTED = "hypothesis_supported"
    HYPOTHESIS_REJECTED = "hypothesis_rejected"
    INCONCLUSIVE = "inconclusive"


class AgentName(str, Enum):
    ORCHESTRATOR = "orchestrator"
    TEST_PLANNER = "test_planner"
    LOAD_ENGINEER = "load_engineer"
    PERFORMANCE_INVESTIGATOR = "performance_investigator"
    REPORTING = "reporting"


# --------------------------------------------------------------------------
# Core entities — see docs/database/database-design.md for relationships
# --------------------------------------------------------------------------


class Project(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class Target(BaseModel):
    id: UUID
    project_id: UUID
    base_url: str
    name: str
    authorization_confirmed: bool
    authorization_confirmed_by: str | None = None
    authorization_confirmed_at: datetime | None = None
    created_at: datetime


class TestPlan(BaseModel):
    id: UUID
    project_id: UUID
    target_id: UUID
    test_type: TestType
    rationale: str
    target_concurrency: int
    ramp_strategy: dict[str, Any]
    user_journeys: list[str]
    thresholds: dict[str, Any]
    duration: dict[str, Any]
    stages: list[dict[str, Any]]
    success_criteria: list[str]
    controlled_variable: dict[str, Any] | None = None
    status: TestPlanStatus
    created_at: datetime


class TestRun(BaseModel):
    id: UUID
    test_plan_id: UUID
    target_id: UUID
    status: TestRunStatus
    k6_script_ref: str | None = None
    raw_output_ref: str | None = None
    clamped: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TestStage(BaseModel):
    id: UUID
    test_run_id: UUID
    target_vus: int
    duration_s: int
    sequence_index: int


class Metric(BaseModel):
    id: UUID
    test_run_id: UUID
    endpoint: str | None = None  # None = aggregate across the whole run
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    throughput_rps: float
    error_rate: float
    concurrency: int
    http_status_distribution: dict[str, int]
    recorded_at: datetime


class Investigation(BaseModel):
    id: UUID
    project_id: UUID
    target_id: UUID
    objective: InvestigationObjective
    status: InvestigationStatus
    baseline_test_run_id: UUID | None = None
    current_test_run_id: UUID | None = None
    experiments_run: int = 0
    max_experiments: int = 3
    event_sequence: int = 0
    created_at: datetime
    updated_at: datetime


class Observation(BaseModel):
    id: str
    statement: str
    metric_ref: str


class Finding(BaseModel):
    id: UUID
    investigation_id: UUID
    severity: Severity
    summary: str
    observations: list[Observation]
    sequence_index: int | None = None


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    statement: str
    source_ref: str


class RecommendedExperiment(BaseModel):
    variable_to_isolate: str
    change: str
    expected_signal: str


class Hypothesis(BaseModel):
    id: UUID
    finding_id: UUID
    statement: str
    confidence: float  # 0.0 - 1.0
    status: HypothesisStatus
    evidence: list[Evidence]
    recommended_experiment: RecommendedExperiment | None = None
    sequence_index: int | None = None


class Experiment(BaseModel):
    id: UUID
    hypothesis_id: UUID
    test_plan_id: UUID | None = None
    test_run_id: UUID | None = None
    variable_changed: str
    baseline_value: Any | None = None
    experiment_value: Any | None = None
    status: ExperimentStatus = ExperimentStatus.PROPOSED
    sequence_index: int = 0
    idempotency_key: str | None = None


class InvestigationEvent(BaseModel):
    id: UUID
    investigation_id: UUID
    sequence: int
    type: InvestigationEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    occurred_at: datetime


class ExperimentResult(BaseModel):
    id: UUID
    experiment_id: UUID
    comparison: dict[str, Any]  # deterministic diff — see packages/metrics
    conclusion: ExperimentConclusion


class Recommendation(BaseModel):
    id: UUID
    hypothesis_id: UUID
    statement: str
    priority: Severity
    sequence_index: int | None = None


class Report(BaseModel):
    id: UUID
    investigation_id: UUID
    executive_summary: str
    capacity: dict[str, Any]
    key_metrics: dict[str, Any]
    bottleneck_analysis: list[dict[str, Any]]
    regression: dict[str, Any]


class AIExecution(BaseModel):
    id: UUID
    investigation_id: UUID | None = None
    test_run_id: UUID | None = None
    agent: AgentName
    timestamp: datetime
    input_reference: str
    output_reference: str
    decision: str
    provider: str
    model: str
