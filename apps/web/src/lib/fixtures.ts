/**
 * Canned demo data — the docs/demo-scenario.md walkthrough (DB connection
 * pool contention at ~750 concurrent users), used by lib/mock-api.ts until
 * a real apps/api exists (see docs/development/next-steps.md: "build the
 * dashboard against a mocked API returning fixture InvestigationState/Report
 * payloads").
 *
 * The numbers here match agents/reporting/fixtures/investigation_states.py's
 * demo_scenario_request() on the Python side — same narrative, same
 * capacity/regression figures — so the whole demo tells one consistent story
 * regardless of which layer you're looking at.
 */
import type {
  BottleneckAnalysisEntry,
  Finding,
  Hypothesis,
  InvestigationState,
  Report,
  Target,
} from "@perfpilot/schemas/types";

export const DEMO_TARGET: Target = {
  id: "tgt_demo",
  projectId: "proj_demo",
  baseUrl: "https://demo.perfpilot.local",
  name: "Demo e-commerce app",
  authorizationConfirmed: true,
  authorizationConfirmedBy: "thato",
  authorizationConfirmedAt: new Date().toISOString(),
};

/** One entry per "tick" a mock investigation advances through — mirrors
 * demo-scenario.md's step ramp (10 -> 1000 concurrent users), the anomaly
 * at 750, the follow-up experiment, and the final report. */
export interface InvestigationTick {
  vus: number;
  status: InvestigationState["status"];
  label: string;
}

export const DEMO_TICKS: InvestigationTick[] = [
  { vus: 10, status: "running", label: "Ramping to 10 concurrent users" },
  { vus: 50, status: "running", label: "Ramping to 50 concurrent users" },
  { vus: 100, status: "running", label: "Ramping to 100 concurrent users" },
  { vus: 250, status: "running", label: "Ramping to 250 concurrent users" },
  { vus: 500, status: "running", label: "Ramping to 500 concurrent users — healthy" },
  {
    vus: 750,
    status: "investigating",
    label: "750 concurrent users — anomaly detected (p95 latency 420ms → 2.8s)",
  },
  {
    vus: 750,
    status: "experimenting",
    label: "Follow-up experiment: DB connection pool doubled (50 → 100)",
  },
  { vus: 1000, status: "reporting", label: "Investigation complete — compiling report" },
];

const DEMO_FINDING_ID = "finding_demo_pool_contention";

const DEMO_OBSERVATIONS = [
  {
    id: "obs-1",
    statement: "p95 latency rose from 420ms to 2.8s at 750 concurrent users.",
    metricRef: "metric:p95Ms#stage-750",
  },
  {
    id: "obs-2",
    statement: "Database connection pool utilization reached 98% at 750 concurrent users.",
    metricRef: "metric:dbConnectionPoolUtilization#stage-750",
  },
];

export const DEMO_FINDING: Finding = {
  id: DEMO_FINDING_ID,
  severity: "HIGH",
  summary:
    "p95 latency degraded sharply at ~750 concurrent users; recovered after doubling the " +
    "DB connection pool size in a follow-up experiment.",
  observations: DEMO_OBSERVATIONS,
};

export const DEMO_HYPOTHESIS: Hypothesis = {
  id: "hyp_demo_pool_contention",
  findingId: DEMO_FINDING_ID,
  statement: "Database connection pool contention.",
  confidence: 0.87,
  status: "supported",
  evidence: [
    {
      statement: "DB connection pool utilization reached 98% at 750 concurrent users",
      sourceRef: "metric:dbConnectionPoolUtilization#stage-750",
    },
    {
      statement: "p95 latency improved ~42% after doubling the connection pool size (50 → 100)",
      sourceRef: "experiment:pool-size-doubled#comparison",
    },
  ],
};

const DEMO_BOTTLENECK: BottleneckAnalysisEntry = {
  observation: DEMO_FINDING.summary,
  likelyCause: DEMO_HYPOTHESIS.statement,
  evidence: DEMO_HYPOTHESIS.evidence.map((e) => `${e.statement} (source: ${e.sourceRef})`),
  confidence: DEMO_HYPOTHESIS.confidence,
};

/** Same numbers as agents/reporting/fixtures/investigation_states.py's
 * demo_scenario_request() / docs/agents/reporting-agent.md's own
 * illustrative example. */
export function buildDemoReport(investigationId: string): Report {
  return {
    id: `rep_${investigationId}`,
    investigationId,
    executiveSummary:
      "The application remained healthy up to approximately 500 concurrent users. " +
      "Performance degradation began around 750 concurrent users, traced to database " +
      "connection pool contention and confirmed by a follow-up experiment.",
    capacity: {
      estimatedSustainableUsers: 620,
      recommendedOperatingUsers: 500,
    },
    keyMetrics: {
      throughputRps: 340,
      p50Ms: 120,
      p95Ms: 890,
      p99Ms: 1450,
      errorRate: 0.008,
      peakConcurrencyTested: 1000,
    },
    findings: [DEMO_FINDING],
    bottleneckAnalysis: [DEMO_BOTTLENECK],
    recommendations: [
      {
        findingId: DEMO_FINDING_ID,
        statement: "Investigate database connection pool saturation.",
        priority: "HIGH",
      },
      {
        findingId: DEMO_FINDING_ID,
        statement: "Inspect slow queries surfaced during the 750-user stage.",
        priority: "MEDIUM",
      },
      {
        findingId: DEMO_FINDING_ID,
        statement: "Review missing indexes on the hot query paths.",
        priority: "MEDIUM",
      },
    ],
    regression: {
      previousP95Ms: 420,
      currentP95Ms: 890,
      regressionPct: 112.0,
    },
  };
}
