"""Agent input/output contracts + shared investigation state.

Mirrors docs/agents/*.md and docs/architecture/data-flow.md — those documents
are the prose source of truth (including each agent's non-responsibilities
and failure states); this file is the typed contract each agent is built
against.

This is a Phase 0 CONTRACT, not a running implementation: it declares shape
only. No business logic (no calculations, no LLM calls) belongs in this
file — see packages/schemas/README.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .entities import (
    Evidence,
    ExperimentStatus,
    Finding,
    Hypothesis,
    InvestigationObjective,
    Metric,
    Observation,
    RecommendedExperiment,
    Severity,
    TestType,
)

# --------------------------------------------------------------------------
# Shared investigation state — owned exclusively by the Orchestrator.
# Specialists never see more of this than their own input schema projects
# out of it. See docs/architecture/data-flow.md#investigation-state.
# --------------------------------------------------------------------------


class DecisionLogEntry(BaseModel):
    step: str
    decision: str
    made_by: str  # "orchestrator" | an agent name, for audit


class ExperimentBudget(BaseModel):
    max_experiments: int = Field(ge=0)
    consumed: int = Field(ge=0)
    remaining: int = Field(ge=0)
    exhausted: bool


class ExperimentState(BaseModel):
    id: UUID
    # Optional on the compatibility seam: Phase 1 fixtures only carried an
    # experiment id, while persisted Phase 2 rows populate the full shape.
    hypothesis_id: UUID | None = None
    test_plan_id: UUID | None = None
    test_run_id: UUID | None = None
    variable_changed: str = ""
    baseline_value: Any | None = None
    experiment_value: Any | None = None
    status: ExperimentStatus = ExperimentStatus.PROPOSED
    sequence_index: int = Field(default=0, ge=0)
    created_at: datetime | None = None


class InvestigationState(BaseModel):
    investigation_id: UUID
    target_id: UUID
    status: str  # InvestigationStatus, see entities.py
    baseline_test_run_id: UUID | None = None
    current_test_run_id: UUID | None = None
    observations: list[Observation] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    experiments: list[ExperimentState] = Field(default_factory=list)
    experiment_budget: ExperimentBudget | None = None
    events: list[OrchestratorEvent] = Field(default_factory=list)
    decisions: list[DecisionLogEntry] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Orchestrator — docs/agents/orchestrator.md
# --------------------------------------------------------------------------


class OrchestratorEventType(str, Enum):
    TEST_RUN_COMPLETED = "test_run_completed"
    USER_REQUESTED_CONTINUE = "user_requested_continue"
    TIMEOUT = "timeout"
    INVESTIGATION_CREATED = "investigation_created"
    TEST_RUN_QUEUED = "test_run_queued"
    TEST_RUN_STARTED = "test_run_started"
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


class OrchestratorEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    sequence: int | None = Field(default=None, ge=1)
    type: OrchestratorEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    occurred_at: datetime | None = None


class OrchestratorStep(BaseModel):
    """Input to the Orchestrator."""

    investigation_state: InvestigationState
    event: OrchestratorEvent


class OrchestratorAction(str, Enum):
    INVOKE_TEST_PLANNER = "invoke_test_planner"
    INVOKE_LOAD_ENGINEER = "invoke_load_engineer"
    INVOKE_INVESTIGATOR = "invoke_investigator"
    INVOKE_REPORTING_AGENT = "invoke_reporting_agent"
    WAIT = "wait"
    COMPLETE = "complete"


class OrchestratorDecision(BaseModel):
    """Output of the Orchestrator."""

    next_action: OrchestratorAction
    specialist_input: dict[str, Any] | None = None
    updated_state: InvestigationState
    reasoning_ref: str | None = None  # AIExecution id, for audit


# --------------------------------------------------------------------------
# Test Planner — docs/agents/test-planner.md
# --------------------------------------------------------------------------


class ExpectedTraffic(BaseModel):
    normal_concurrent_users: int
    peak_concurrent_users: int
    peak_description: str | None = None


class PerformanceRequirements(BaseModel):
    p95_ms: float
    max_error_rate: float


class TargetDescription(BaseModel):
    application_name: str
    api_spec_ref: str | None = None
    user_journeys: list[str]
    expected_traffic: ExpectedTraffic
    performance_requirements: PerformanceRequirements


class ExperimentContext(BaseModel):
    hypothesis_id: UUID | None = None
    variable_to_isolate: str | None = None
    baseline_test_run_id: UUID | None = None


class TestPlanRequest(BaseModel):
    target_description: TargetDescription
    objective: InvestigationObjective
    experiment_context: ExperimentContext | None = None


class RampStrategy(BaseModel):
    type: str  # "step" | "linear" | "spike"
    step_size: int | None = None
    step_duration_s: int | None = None


class TestStagePlan(BaseModel):
    target_vus: int
    duration_s: int


class ControlledVariable(BaseModel):
    name: str
    baseline_value: Any
    experiment_value: Any


class TestPlanOutput(BaseModel):
    """Output of the Test Planner. Persisted as entities.TestPlan."""

    test_type: TestType
    rationale: str
    target_concurrency: int
    ramp_strategy: RampStrategy
    user_journeys: list[str]
    thresholds: dict[str, float]
    duration: dict[str, int]
    stages: list[TestStagePlan]
    success_criteria: list[str]
    controlled_variable: ControlledVariable | None = None


# --------------------------------------------------------------------------
# Load Engineer — docs/agents/load-engineer.md
# --------------------------------------------------------------------------


class TargetRef(BaseModel):
    base_url: str
    auth: str | None = None  # reference to a stored credential — never a raw secret


class LoadExecutionRequest(BaseModel):
    test_plan: TestPlanOutput
    target: TargetRef
    test_run_id: UUID


class ClampedInfo(BaseModel):
    requested_vus: int
    executed_vus: int
    reason: str


class LoadExecutionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED_OVER_LIMIT = "aborted_over_limit"


class LoadExecutionResult(BaseModel):
    test_run_id: UUID
    status: LoadExecutionStatus
    k6_script_ref: str
    raw_output_ref: str
    metrics: list[Metric]
    clamped: ClampedInfo | None = None


# --------------------------------------------------------------------------
# Performance Investigator — docs/agents/performance-investigator.md
# --------------------------------------------------------------------------


class TestRunMetricsRef(BaseModel):
    id: UUID
    metrics: list[Metric]


class InfrastructureMetrics(BaseModel):
    db_connection_pool_utilization: float | None = None
    cpu_pct: float | None = None
    memory_pct: float | None = None


class InvestigationAnalysisRequest(BaseModel):
    test_run: TestRunMetricsRef
    baseline_test_run: TestRunMetricsRef
    comparison: dict[str, Any]  # deterministic diff from packages/metrics
    thresholds: dict[str, float]
    prior_hypotheses: list[Hypothesis] | None = None
    infrastructure_metrics: InfrastructureMetrics | None = None


class FindingSummary(BaseModel):
    id: str
    severity: Severity
    summary: str


class HypothesisOutput(BaseModel):
    id: str
    statement: str
    evidence: list[Evidence] = Field(min_length=1)  # never emit an unevidenced hypothesis
    confidence: float
    recommended_experiment: RecommendedExperiment | None = None


class InvestigatorOutput(BaseModel):
    """Output of the Performance Investigator. Persisted as Finding + Hypothesis rows."""

    finding: FindingSummary
    observations: list[Observation]
    hypotheses: list[HypothesisOutput]


# --------------------------------------------------------------------------
# Reporting Agent — docs/agents/reporting-agent.md
# --------------------------------------------------------------------------


class CapacityEstimate(BaseModel):
    sustainable_concurrency: int
    recommended_operating_concurrency: int
    method: str  # points back to the packages/metrics calculation used


class RegressionComparison(BaseModel):
    previous_p95_ms: float
    current_p95_ms: float
    regression_pct: float


class ReportRequest(BaseModel):
    investigation_id: UUID
    investigation_state: InvestigationState
    capacity_estimate: CapacityEstimate
    regression_comparison: RegressionComparison
    # Deterministic key-metrics summary (throughput_rps, p50/p95/p99_ms,
    # error_rate, peak_concurrency_tested) computed once by packages/metrics
    # from the investigation's TestRun(s) — never recomputed by this agent.
    # Added while implementing agents/reporting (issue #15): ReportOutput.key_metrics
    # is required by docs/agents/reporting-agent.md's "Key metrics table"
    # responsibility, but nothing upstream of this schema previously carried
    # it into the request. Flagged as a schema-shape addition in the PR —
    # packages/schemas is Kamogelo's canonical file, this is proposed, not
    # unilaterally final.
    key_metrics: dict[str, Any]


class BottleneckAnalysisEntry(BaseModel):
    observation: str
    likely_cause: str
    evidence: list[str]
    confidence: float


class RecommendationOutput(BaseModel):
    finding_id: str  # every recommendation must trace back to a finding
    statement: str
    priority: Severity


class ReportOutput(BaseModel):
    """Output of the Reporting Agent. Persisted as entities.Report."""

    executive_summary: str
    capacity: CapacityEstimate
    key_metrics: dict[str, Any]
    findings: list[FindingSummary]
    bottleneck_analysis: list[BottleneckAnalysisEntry]
    recommendations: list[RecommendationOutput]
    regression: RegressionComparison
