/**
 * Frontend-facing contract types.
 *
 * Mirrors packages/schemas/python/{entities,agent_io}.py — those files (and
 * the prose in docs/agents/*.md, docs/database/database-design.md) are the
 * source of truth. Keep this file in sync with them; see
 * packages/schemas/README.md and CONTRIBUTING.md#changing-a-shared-contract.
 *
 * This is a Phase 0 CONTRACT, not a running implementation: it declares
 * shape only. No fetch logic, no React components, no business logic
 * belongs in this file.
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type TestType =
  "load" | "stress" | "spike" | "endurance" | "capacity" | "baseline" | "regression";

export type TestPlanStatus = "proposed" | "approved" | "superseded";

export type TestRunStatus = "queued" | "running" | "succeeded" | "failed" | "aborted_over_limit";

export type InvestigationObjective =
  "determine_capacity" | "diagnose_regression" | "validate_fix" | "baseline";

export type InvestigationStatus =
  "planning" | "running" | "investigating" | "experimenting" | "reporting" | "complete" | "failed";

export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";

export type HypothesisStatus = "proposed" | "testing" | "supported" | "rejected";

export type ExperimentStatus =
  "proposed" | "approved" | "queued" | "running" | "succeeded" | "failed" | "rejected";

// ---------------------------------------------------------------------------
// Core entities — docs/database/database-design.md
// ---------------------------------------------------------------------------

export interface Project {
  id: string;
  name: string;
  description?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Target {
  id: string;
  projectId: string;
  baseUrl: string;
  name: string;
  authorizationConfirmed: boolean;
  authorizationConfirmedBy?: string;
  authorizationConfirmedAt?: string;
}

export interface RampStrategy {
  type: "step" | "linear" | "spike";
  stepSize?: number;
  stepDurationS?: number;
}

export interface TestStagePlan {
  targetVus: number;
  durationS: number;
}

export interface ControlledVariable {
  name: string;
  baselineValue: unknown;
  experimentValue: unknown;
}

export interface TestPlan {
  id: string;
  projectId: string;
  targetId: string;
  testType: TestType;
  rationale: string;
  targetConcurrency: number;
  rampStrategy: RampStrategy;
  userJourneys: string[];
  thresholds: Record<string, number>;
  duration: { totalS: number };
  stages: TestStagePlan[];
  successCriteria: string[];
  controlledVariable?: ControlledVariable;
  status: TestPlanStatus;
}

export interface ClampedInfo {
  requestedVus: number;
  executedVus: number;
  reason: string;
}

export interface TestRun {
  id: string;
  testPlanId: string;
  targetId: string;
  status: TestRunStatus;
  progress?: { currentVus: number; targetVus: number };
  clamped?: ClampedInfo;
  startedAt?: string;
  completedAt?: string;
}

export interface Metric {
  id: string;
  testRunId: string;
  endpoint?: string; // undefined = aggregate across the whole run
  p50Ms: number;
  p90Ms: number;
  p95Ms: number;
  p99Ms: number;
  throughputRps: number;
  errorRate: number;
  concurrency: number;
  httpStatusDistribution: Record<string, number>;
  recordedAt: string;
}

// ---------------------------------------------------------------------------
// Investigation — docs/architecture/data-flow.md#investigation-state
// ---------------------------------------------------------------------------

/** Mirrors agent_io.ExpectedTraffic (packages/schemas/python) — this is the
 * `expected_traffic` body `POST /api/investigations` takes per
 * docs/api/api-contract.md, which apps/web sends directly. Added while
 * building the dashboard (issue #14); previously missing from this file
 * entirely even though the API contract requires it. */
export interface ExpectedTraffic {
  normalConcurrentUsers: number;
  peakConcurrentUsers: number;
  peakDescription?: string;
}

export interface Observation {
  id: string;
  statement: string;
  metricRef: string;
}

export interface Finding {
  id: string;
  severity: Severity;
  summary: string;
  observations: Observation[];
  sequenceIndex?: number;
}

export interface Evidence {
  id?: string;
  statement: string;
  sourceRef: string;
}

export interface RecommendedExperiment {
  variableToIsolate: string;
  change: string;
  expectedSignal: string;
}

export interface Hypothesis {
  id: string;
  findingId: string;
  statement: string;
  confidence: number; // 0.0 - 1.0
  status: HypothesisStatus;
  evidence: Evidence[];
  recommendedExperiment?: RecommendedExperiment;
  sequenceIndex?: number;
}

export interface ExperimentRecord {
  id: string;
  hypothesisId: string;
  testPlanId?: string;
  testRunId?: string;
  variableChanged: string;
  baselineValue: unknown;
  experimentValue: unknown;
  status: ExperimentStatus;
  sequenceIndex: number;
}

export interface ExperimentBudget {
  maxExperiments: number;
  consumed: number;
  remaining: number;
  exhausted: boolean;
}

export interface InvestigationEvent {
  id: string;
  sequence: number;
  type: string;
  payload: Record<string, unknown>;
  idempotencyKey?: string;
  occurredAt: string;
}

export interface DecisionLogEntry {
  step: string;
  decision: string;
  madeBy: string;
}

/** Mirrors the Orchestrator's InvestigationState — what the dashboard's
 *  investigation view renders. See docs/architecture/data-flow.md. */
export interface InvestigationState {
  investigationId: string;
  targetId: string;
  status: InvestigationStatus;
  baselineTestRunId?: string;
  currentTestRunId?: string;
  observations: Observation[];
  findings: Finding[];
  hypotheses: Hypothesis[];
  experiments: ExperimentRecord[];
  experimentBudget?: ExperimentBudget;
  events?: InvestigationEvent[];
  decisions: DecisionLogEntry[];
}

// ---------------------------------------------------------------------------
// Report — docs/agents/reporting-agent.md
// ---------------------------------------------------------------------------

export interface CapacitySummary {
  estimatedSustainableUsers: number;
  recommendedOperatingUsers: number;
}

export interface KeyMetrics {
  throughputRps: number;
  p50Ms: number;
  p95Ms: number;
  p99Ms: number;
  errorRate: number;
  peakConcurrencyTested: number;
}

export interface BottleneckAnalysisEntry {
  observation: string;
  likelyCause: string;
  evidence: string[];
  confidence: number;
}

export interface RecommendationItem {
  findingId: string;
  statement: string;
  priority: Severity;
  sequenceIndex?: number;
}

export interface RegressionSummary {
  previousP95Ms: number;
  currentP95Ms: number;
  regressionPct: number;
}

export interface Report {
  id: string;
  investigationId: string;
  executiveSummary: string;
  capacity: CapacitySummary;
  keyMetrics: KeyMetrics;
  findings: Finding[];
  bottleneckAnalysis: BottleneckAnalysisEntry[];
  recommendations: RecommendationItem[];
  regression: RegressionSummary;
}

// ---------------------------------------------------------------------------
// Baselines and comparison — docs/api/api-contract.md#baselines, issue #34
//
// The comparison numbers are produced by packages/metrics and passed through
// the API unchanged; nothing on the client recomputes them. Percent fields are
// null when the baseline value was zero, which is a real "cannot be expressed
// as a percentage" rather than a zero-percent change — rendering it as 0%
// would assert something the data does not say.
// ---------------------------------------------------------------------------

export type ComparisonStatus = "available" | "incompatible" | "unavailable";

export interface MetricComparison {
  status: ComparisonStatus;
  reason?: string | null;
  baselineMetricId?: string | null;
  currentMetricId?: string | null;
  baselineTestRunId?: string | null;
  currentTestRunId?: string | null;
  baselineConcurrency?: number | null;
  currentConcurrency?: number | null;
  p50DeltaMs?: number | null;
  p50DeltaPct?: number | null;
  p90DeltaMs?: number | null;
  p90DeltaPct?: number | null;
  p95DeltaMs?: number | null;
  p95DeltaPct?: number | null;
  p99DeltaMs?: number | null;
  p99DeltaPct?: number | null;
  throughputDeltaRps?: number | null;
  throughputDeltaPct?: number | null;
  errorRateDelta?: number | null;
  errorRateDeltaPct?: number | null;
}

/** Why the API refused to compare a run with a named baseline. Returned as the
 *  `error.code` of a 409, with the offending values under `error.detail`.
 *
 *  Branch on these rather than on `error.message`: the codes are the contract
 *  and the sentences are not. `scenario_mismatch` carries a `differing_fields`
 *  array naming the scenario fields that disagree, which is the one a UI can
 *  turn into an explanation rather than an apology. */
export type IncompatibleReason =
  | "baseline_run_not_succeeded"
  | "current_run_not_succeeded"
  | "environment_mismatch"
  | "test_type_mismatch"
  | "concurrency_mismatch"
  | "scenario_mismatch"
  | "scenario_identity_unsupported"
  | "baseline_metrics_unavailable"
  | "current_metrics_unavailable"
  | "no_shared_endpoint";

/** A deliberately chosen historical run, with the compatibility identity
 *  frozen at selection time. */
export interface BaselineRef {
  id: string;
  targetId: string;
  testRunId: string;
  label: string;
  selectedBy: string;
  testType: TestType;
  targetConcurrency: number;
  /** `v<n>:<sha256>` over the scenario the baseline run executed — ramp
   *  strategy, stages, duration, journeys, plus type and concurrency. Opaque:
   *  compare it for equality, never parse it. Two baselines with the same
   *  fingerprint are interchangeable as references; two with different ones
   *  are not comparable with each other. */
  scenarioFingerprint: string;
}

export interface ComparisonResponse {
  baseline: BaselineRef;
  currentTestRunId: string;
  comparisons: MetricComparison[];
  /** Endpoints measured in the baseline run only — a real difference between
   *  the two runs, not an absence of change. */
  baselineOnlyEndpoints: (string | null)[];
  /** Endpoints measured in the current run only. */
  currentOnlyEndpoints: (string | null)[];
}

// ---------------------------------------------------------------------------
// Common API error shape — docs/api/api-contract.md#common-error-shape
// ---------------------------------------------------------------------------

export interface ApiError {
  error: {
    code: string;
    message: string;
    detail?: Record<string, unknown>;
  };
}
