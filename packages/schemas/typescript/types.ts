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
}

export interface Evidence {
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
}

export interface ExperimentRecord {
  id: string;
  hypothesisId: string;
  testPlanId: string;
  testRunId: string;
  variableChanged: string;
  baselineValue: unknown;
  experimentValue: unknown;
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
// Common API error shape — docs/api/api-contract.md#common-error-shape
// ---------------------------------------------------------------------------

export interface ApiError {
  error: {
    code: string;
    message: string;
    detail?: Record<string, unknown>;
  };
}
