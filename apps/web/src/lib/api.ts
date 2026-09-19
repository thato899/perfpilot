import type {
  ExpectedTraffic,
  InvestigationObjective,
  InvestigationState,
  Metric,
  Project,
  Report,
  Target,
  TestPlan,
  TestRun,
} from "@perfpilot/schemas/types";

const API_PROXY_PREFIX = "/api/perfpilot";

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: Record<string, unknown>;

  constructor(
    message: string,
    status: number,
    code = "api_error",
    detail: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

interface WireError {
  error?: { code?: string; message?: string; detail?: Record<string, unknown> };
}

interface WireProject {
  id: string;
  name: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

interface WireTarget {
  id: string;
  project_id: string;
  base_url: string;
  name: string;
  authorization_confirmed: boolean;
  authorization_confirmed_by?: string | null;
  authorization_confirmed_at?: string | null;
}

interface WireInvestigation {
  id: string;
  project_id: string;
  target_id: string;
  objective: InvestigationObjective;
  status: InvestigationState["status"];
  baseline_test_run_id?: string | null;
  current_test_run_id?: string | null;
}

interface WireInvestigationState {
  investigation_id: string;
  target_id: string;
  status: InvestigationState["status"];
  baseline_test_run_id?: string | null;
  current_test_run_id?: string | null;
  observations: Array<{
    id: string;
    statement: string;
    metric_ref: string;
  }>;
  findings: Array<{
    id: string;
    investigation_id?: string;
    severity: InvestigationState["findings"][number]["severity"];
    summary: string;
    observations: Array<{ id: string; statement: string; metric_ref: string }>;
  }>;
  hypotheses: Array<{
    id: string;
    finding_id: string;
    statement: string;
    confidence: number;
    status: InvestigationState["hypotheses"][number]["status"];
    evidence: Array<{ statement: string; source_ref: string }>;
    recommended_experiment?: {
      variable_to_isolate: string;
      change: string;
      expected_signal: string;
    } | null;
  }>;
  experiments: Array<{
    id: string;
    hypothesis_id: string;
    variable_changed: string;
    from?: unknown;
    to?: unknown;
    test_run_id: string;
  }>;
  decisions: Array<{ step: string; decision: string; made_by: string }>;
}

interface WireTestPlan {
  id: string;
  project_id: string;
  target_id: string;
  test_type: TestPlan["testType"];
  rationale: string;
  target_concurrency: number;
  ramp_strategy: {
    type: "step" | "linear" | "spike";
    step_size?: number;
    step_duration_s?: number;
  };
  user_journeys: string[];
  thresholds: Record<string, number>;
  duration: { total_s: number };
  stages: Array<{ target_vus: number; duration_s: number }>;
  success_criteria: string[];
  controlled_variable?: {
    name: string;
    baseline_value: unknown;
    experiment_value: unknown;
  } | null;
  status: TestPlan["status"];
}

interface WireTestRun {
  id: string;
  test_plan_id: string;
  target_id: string;
  status: TestRun["status"];
  progress: { current_vus: number; target_vus: number };
  clamped?: { requested_vus: number; executed_vus: number; reason: string } | null;
  started_at?: string | null;
  completed_at?: string | null;
}

interface WireMetric {
  id: string;
  test_run_id: string;
  endpoint?: string | null;
  p50_ms: number;
  p90_ms: number;
  p95_ms: number;
  p99_ms: number;
  throughput_rps: number;
  error_rate: number;
  concurrency: number;
  http_status_distribution: Record<string, number>;
  recorded_at: string;
}

interface WireReport {
  id: string;
  investigation_id: string;
  executive_summary: string;
  capacity: { sustainable_concurrency: number; recommended_operating_concurrency: number };
  key_metrics: {
    throughput_rps: number;
    p50_ms: number;
    p95_ms: number;
    p99_ms: number;
    error_rate: number;
    peak_concurrency_tested: number;
  };
  findings: Array<{
    id: string;
    severity: InvestigationState["findings"][number]["severity"];
    summary: string;
  }>;
  bottleneck_analysis: Array<{
    observation: string;
    likely_cause: string;
    evidence: string[];
    confidence: number;
  }>;
  recommendations: Array<{
    finding_id: string;
    statement: string;
    priority: InvestigationState["findings"][number]["severity"];
  }>;
  regression: { previous_p95_ms: number; current_p95_ms: number; regression_pct: number };
}

function projectFromWire(value: WireProject): Project {
  return {
    id: value.id,
    name: value.name,
    description: value.description ?? undefined,
    createdAt: value.created_at,
    updatedAt: value.updated_at,
  };
}

function targetFromWire(value: WireTarget): Target {
  return {
    id: value.id,
    projectId: value.project_id,
    baseUrl: value.base_url,
    name: value.name,
    authorizationConfirmed: value.authorization_confirmed,
    authorizationConfirmedBy: value.authorization_confirmed_by ?? undefined,
    authorizationConfirmedAt: value.authorization_confirmed_at ?? undefined,
  };
}

function investigationFromWire(value: WireInvestigationState): InvestigationState {
  return {
    investigationId: value.investigation_id,
    targetId: value.target_id,
    status: value.status,
    baselineTestRunId: value.baseline_test_run_id ?? undefined,
    currentTestRunId: value.current_test_run_id ?? undefined,
    observations: value.observations.map((item) => ({
      id: item.id,
      statement: item.statement,
      metricRef: item.metric_ref,
    })),
    findings: value.findings.map((finding) => ({
      id: finding.id,
      severity: finding.severity,
      summary: finding.summary,
      observations: finding.observations.map((item) => ({
        id: item.id,
        statement: item.statement,
        metricRef: item.metric_ref,
      })),
    })),
    hypotheses: value.hypotheses.map((hypothesis) => ({
      id: hypothesis.id,
      findingId: hypothesis.finding_id,
      statement: hypothesis.statement,
      confidence: hypothesis.confidence,
      status: hypothesis.status,
      evidence: hypothesis.evidence.map((item) => ({
        statement: item.statement,
        sourceRef: item.source_ref,
      })),
      recommendedExperiment: hypothesis.recommended_experiment
        ? {
            variableToIsolate: hypothesis.recommended_experiment.variable_to_isolate,
            change: hypothesis.recommended_experiment.change,
            expectedSignal: hypothesis.recommended_experiment.expected_signal,
          }
        : undefined,
    })),
    experiments: value.experiments.map((experiment) => ({
      id: experiment.id,
      hypothesisId: experiment.hypothesis_id,
      testPlanId: "",
      testRunId: experiment.test_run_id,
      variableChanged: experiment.variable_changed,
      baselineValue: experiment.from,
      experimentValue: experiment.to,
    })),
    decisions: value.decisions.map((item) => ({
      step: item.step,
      decision: item.decision,
      madeBy: item.made_by,
    })),
  };
}

function testPlanFromWire(value: WireTestPlan): TestPlan {
  return {
    id: value.id,
    projectId: value.project_id,
    targetId: value.target_id,
    testType: value.test_type,
    rationale: value.rationale,
    targetConcurrency: value.target_concurrency,
    rampStrategy: {
      type: value.ramp_strategy.type,
      stepSize: value.ramp_strategy.step_size,
      stepDurationS: value.ramp_strategy.step_duration_s,
    },
    userJourneys: value.user_journeys,
    thresholds: value.thresholds,
    duration: { totalS: value.duration.total_s },
    stages: value.stages.map((stage) => ({
      targetVus: stage.target_vus,
      durationS: stage.duration_s,
    })),
    successCriteria: value.success_criteria,
    controlledVariable: value.controlled_variable
      ? {
          name: value.controlled_variable.name,
          baselineValue: value.controlled_variable.baseline_value,
          experimentValue: value.controlled_variable.experiment_value,
        }
      : undefined,
    status: value.status,
  };
}

function testRunFromWire(value: WireTestRun): TestRun {
  return {
    id: value.id,
    testPlanId: value.test_plan_id,
    targetId: value.target_id,
    status: value.status,
    progress: value.progress
      ? { currentVus: value.progress.current_vus, targetVus: value.progress.target_vus }
      : undefined,
    clamped: value.clamped
      ? {
          requestedVus: value.clamped.requested_vus,
          executedVus: value.clamped.executed_vus,
          reason: value.clamped.reason,
        }
      : undefined,
    startedAt: value.started_at ?? undefined,
    completedAt: value.completed_at ?? undefined,
  };
}

function metricFromWire(value: WireMetric): Metric {
  return {
    id: value.id,
    testRunId: value.test_run_id,
    endpoint: value.endpoint ?? undefined,
    p50Ms: value.p50_ms,
    p90Ms: value.p90_ms,
    p95Ms: value.p95_ms,
    p99Ms: value.p99_ms,
    throughputRps: value.throughput_rps,
    errorRate: value.error_rate,
    concurrency: value.concurrency,
    httpStatusDistribution: value.http_status_distribution,
    recordedAt: value.recorded_at,
  };
}

function reportFromWire(value: WireReport): Report {
  return {
    id: value.id,
    investigationId: value.investigation_id,
    executiveSummary: value.executive_summary,
    capacity: {
      estimatedSustainableUsers: value.capacity.sustainable_concurrency,
      recommendedOperatingUsers: value.capacity.recommended_operating_concurrency,
    },
    keyMetrics: {
      throughputRps: value.key_metrics.throughput_rps,
      p50Ms: value.key_metrics.p50_ms,
      p95Ms: value.key_metrics.p95_ms,
      p99Ms: value.key_metrics.p99_ms,
      errorRate: value.key_metrics.error_rate,
      peakConcurrencyTested: value.key_metrics.peak_concurrency_tested,
    },
    findings: value.findings.map((finding) => ({
      id: finding.id,
      severity: finding.severity,
      summary: finding.summary,
      observations: [],
    })),
    bottleneckAnalysis: value.bottleneck_analysis.map((entry) => ({
      observation: entry.observation,
      likelyCause: entry.likely_cause,
      evidence: entry.evidence,
      confidence: entry.confidence,
    })),
    recommendations: value.recommendations.map((recommendation) => ({
      findingId: recommendation.finding_id,
      statement: recommendation.statement,
      priority: recommendation.priority,
    })),
    regression: {
      previousP95Ms: value.regression.previous_p95_ms,
      currentP95Ms: value.regression.current_p95_ms,
      regressionPct: value.regression.regression_pct,
    },
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PROXY_PREFIX}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let body: WireError = {};
    try {
      body = (await response.json()) as WireError;
    } catch {
      // Preserve the HTTP status even if an upstream proxy returned non-JSON.
    }
    throw new ApiRequestError(
      body.error?.message ?? `PerfPilot API request failed (${response.status}).`,
      response.status,
      body.error?.code,
      body.error?.detail,
    );
  }

  return (await response.json()) as T;
}

export interface CreateProjectInput {
  name: string;
  description?: string;
}

export async function createProject(input: CreateProjectInput): Promise<Project> {
  const body = await request<WireProject>("/projects", {
    method: "POST",
    body: JSON.stringify({ name: input.name, description: input.description }),
  });
  return projectFromWire(body);
}

export async function getProject(projectId: string): Promise<Project> {
  return projectFromWire(await request<WireProject>(`/projects/${projectId}`));
}

export interface CreateTargetInput {
  name: string;
  baseUrl: string;
  authorizationConfirmed: boolean;
  authorizationConfirmedBy: string;
}

export async function createTarget(projectId: string, input: CreateTargetInput): Promise<Target> {
  const body = await request<WireTarget>(`/projects/${projectId}/targets`, {
    method: "POST",
    body: JSON.stringify({
      name: input.name,
      base_url: input.baseUrl,
      authorization_confirmed: input.authorizationConfirmed,
      authorization_confirmed_by: input.authorizationConfirmedBy,
    }),
  });
  return targetFromWire(body);
}

export interface CreateInvestigationInput {
  targetId: string;
  objective: InvestigationObjective;
  expectedTraffic: ExpectedTraffic;
}

export async function createInvestigation(
  input: CreateInvestigationInput,
): Promise<InvestigationState> {
  const created = await request<WireInvestigation>("/investigations", {
    method: "POST",
    body: JSON.stringify({
      target_id: input.targetId,
      objective: input.objective,
      expected_traffic: {
        normal_concurrent_users: input.expectedTraffic.normalConcurrentUsers,
        peak_concurrent_users: input.expectedTraffic.peakConcurrentUsers,
        peak_description: input.expectedTraffic.peakDescription,
      },
    }),
  });
  return getInvestigation(created.id);
}

export async function getInvestigation(investigationId: string): Promise<InvestigationState> {
  return investigationFromWire(
    await request<WireInvestigationState>(`/investigations/${investigationId}`),
  );
}

export async function getFindings(
  investigationId: string,
): Promise<InvestigationState["findings"]> {
  const body = await request<{ findings: WireInvestigationState["findings"] }>(
    `/investigations/${investigationId}/findings`,
  );
  return body.findings.map(
    (finding) =>
      investigationFromWire({
        investigation_id: investigationId,
        target_id: "",
        status: "planning",
        observations: [],
        findings: [finding],
        hypotheses: [],
        experiments: [],
        decisions: [],
      }).findings[0],
  );
}

export async function getTestRun(runId: string): Promise<TestRun> {
  return testRunFromWire(await request<WireTestRun>(`/test-runs/${runId}`));
}

export async function getMetrics(runId: string): Promise<Metric[]> {
  const body = await request<{ metrics: WireMetric[] }>(`/test-runs/${runId}/metrics`);
  return body.metrics.map(metricFromWire);
}

export interface CreateTestPlanInput {
  projectId: string;
  targetId: string;
  objective: InvestigationObjective;
  userJourneys: string[];
  expectedTraffic: ExpectedTraffic;
  p95Ms: number;
  maxErrorRate: number;
  applicationName?: string;
}

export async function createTestPlan(input: CreateTestPlanInput): Promise<TestPlan> {
  const body = await request<WireTestPlan>("/tests/plan", {
    method: "POST",
    body: JSON.stringify({
      project_id: input.projectId,
      target_id: input.targetId,
      objective: input.objective,
      user_journeys: input.userJourneys,
      expected_traffic: {
        normal_concurrent_users: input.expectedTraffic.normalConcurrentUsers,
        peak_concurrent_users: input.expectedTraffic.peakConcurrentUsers,
        peak_description: input.expectedTraffic.peakDescription,
      },
      p95_ms: input.p95Ms,
      max_error_rate: input.maxErrorRate,
      application_name: input.applicationName,
    }),
  });
  return testPlanFromWire(body);
}

export async function startTestRun(
  planId: string,
  targetId: string,
): Promise<{ testRunId: string; status: TestRun["status"] }> {
  const body = await request<{ test_run_id: string; status: TestRun["status"] }>(
    `/tests/${planId}/run`,
    { method: "POST", body: JSON.stringify({ target_id: targetId }) },
  );
  return { testRunId: body.test_run_id, status: body.status };
}

export async function approveExperiment(
  investigationId: string,
  hypothesisId: string,
): Promise<{ testRunId: string }> {
  const body = await request<{ test_run_id: string }>(
    `/investigations/${investigationId}/experiments`,
    { method: "POST", body: JSON.stringify({ hypothesis_id: hypothesisId }) },
  );
  return { testRunId: body.test_run_id };
}

export async function continueInvestigation(
  investigationId: string,
  testRunId: string,
): Promise<InvestigationState> {
  const body = await request<{ updated_state: WireInvestigationState }>(
    `/investigations/${investigationId}/continue`,
    { method: "POST", body: JSON.stringify({ test_run_id: testRunId }) },
  );
  return investigationFromWire(body.updated_state);
}

export async function getReport(investigationId: string): Promise<Report> {
  return reportFromWire(await request<WireReport>(`/reports/${investigationId}`));
}
