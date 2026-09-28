import { describe, expect, it } from "vitest";

import type { Metric, MetricComparison } from "@perfpilot/schemas/types";

import type { ComparisonState } from "../comparison-view";
import {
  buildComparisonExport,
  comparisonExportCsv,
  COMPARISON_EXPORT_VERSION,
} from "../comparison-export";

const metric = (id: string, values: Partial<Metric> = {}): Metric => ({
  id,
  testRunId: id === "base-metric" ? "base-run" : "experiment-run",
  p50Ms: 100,
  p90Ms: 180,
  p95Ms: 250,
  p99Ms: 300,
  throughputRps: 50,
  errorRate: 0.01,
  concurrency: 100,
  httpStatusDistribution: {},
  recordedAt: "2026-09-27T00:00:00Z",
  ...values,
});

function availableState(
  comparison: Partial<MetricComparison> = {},
): Extract<ComparisonState, { status: "available" }> {
  return {
    status: "available",
    response: {
      baseline: {
        id: "baseline-1",
        targetId: "target-1",
        testRunId: "base-run",
        label: "release baseline",
        selectedBy: "Thato",
        testType: "load",
        targetConcurrency: 100,
        scenarioFingerprint: "v1:abc",
      },
      currentTestRunId: "experiment-run",
      comparisons: [
        {
          status: "available",
          conclusion: "improvement",
          baselineMetricId: "base-metric",
          currentMetricId: "experiment-metric",
          baselineThresholds: { p95Ms: 500, maxErrorRate: 0.02 },
          currentThresholds: { p95Ms: 450, maxErrorRate: 0.01 },
          baselineThresholdPassed: true,
          currentThresholdPassed: true,
          p50DeltaMs: -10,
          p50DeltaPct: -9.09,
          p90DeltaMs: -15,
          p90DeltaPct: -8.33,
          p95DeltaMs: -25,
          p95DeltaPct: -10,
          p99DeltaMs: -30,
          p99DeltaPct: -10,
          throughputDeltaRps: 5,
          throughputDeltaPct: 10,
          errorRateDelta: -0.002,
          errorRateDeltaPct: -16.67,
          concurrencyDelta: 0,
          concurrencyDeltaPct: 0,
          ...comparison,
        },
      ],
      baselineOnlyEndpoints: ["/old"],
      currentOnlyEndpoints: ["/new"],
    },
    baselineMetrics: [metric("base-metric")],
    currentMetrics: [metric("experiment-metric", { p50Ms: 90, p95Ms: 225, throughputRps: 55 })],
    experimentId: "experiment-1",
  };
}

function parseCsvRow(row: string): string[] {
  const cells: string[] = [];
  let value = "";
  let quoted = false;
  for (let index = 0; index < row.length; index += 1) {
    const character = row[index];
    if (quoted && character === '"' && row[index + 1] === '"') {
      value += '"';
      index += 1;
    } else if (character === '"') {
      quoted = !quoted;
    } else if (character === "," && !quoted) {
      cells.push(value);
      value = "";
    } else {
      value += character;
    }
  }
  cells.push(value);
  return cells;
}

describe("comparison export serialization", () => {
  it("preserves canonical values, units, deltas, thresholds, identity and version", () => {
    const exported = buildComparisonExport(availableState(), "2026-09-28T10:00:00.000Z");
    const [comparison] = exported.comparisons;

    expect(exported).toMatchObject({
      schema_version: COMPARISON_EXPORT_VERSION,
      generated_at: "2026-09-28T10:00:00.000Z",
      target_id: "target-1",
      baseline: {
        id: "baseline-1",
        test_run_id: "base-run",
        scenario_fingerprint: "v1:abc",
      },
      experiment: { id: "experiment-1", test_run_id: "experiment-run" },
      units: { latency: "ms", throughput: "requests/second", error_rate: "fraction (0–1)" },
      baseline_only_endpoints: ["/old"],
      experiment_only_endpoints: ["/new"],
    });
    expect(comparison).toMatchObject({
      scope: null,
      status: "available",
      conclusion: "improvement",
      baseline: { p50_ms: 100, p95_ms: 250, error_rate_fraction: 0.01 },
      experiment: { p50_ms: 90, p95_ms: 225, error_rate_fraction: 0.01 },
      deltas: { p50_delta_ms: -10, p95_delta_pct: -10, error_rate_delta_fraction: -0.002 },
      thresholds: {
        baseline: { p95_ms: 500, max_error_rate_fraction: 0.02 },
        experiment: { p95_ms: 450, max_error_rate_fraction: 0.01 },
        baseline_passed: true,
        experiment_passed: true,
      },
    });
  });

  it("keeps canonical concurrency values when metric records are absent", () => {
    const state = availableState({
      baselineMetricId: null,
      currentMetricId: null,
      baselineConcurrency: 200,
      currentConcurrency: 200,
      concurrencyDelta: 25,
      concurrencyDeltaPct: 14.29,
    });
    const [comparison] = buildComparisonExport(state).comparisons;

    expect(comparison.baseline.concurrency_users).toBe(200);
    expect(comparison.experiment.concurrency_users).toBe(200);
    expect(comparison.deltas).toMatchObject({
      concurrency_delta_users: 25,
      concurrency_delta_pct: 14.29,
    });
  });

  it.each([
    ["improvement", "available"],
    ["regression", "available"],
    ["unchanged", "available"],
    ["inconclusive", "available"],
    ["unavailable", "unavailable"],
    ["incompatible", "incompatible"],
  ] as const)("preserves the canonical %s/%s state", (conclusion, status) => {
    const exported = buildComparisonExport(
      availableState({
        status,
        conclusion,
        reason: status === "available" ? null : "Canonical reason from the API.",
        baselineMetricId: null,
        currentMetricId: null,
        p95DeltaMs: null,
        p95DeltaPct: null,
      }),
    );

    expect(exported.comparisons[0]).toMatchObject({
      status,
      conclusion,
      reason: status === "available" ? null : "Canonical reason from the API.",
      baseline: { p95_ms: null },
      experiment: { p95_ms: null },
      deltas: { p95_delta_ms: null, p95_delta_pct: null },
    });
  });

  it("writes CSV with RFC 4180 quoting and neutralizes formula-like text", () => {
    const state = availableState({
      reason: '=HYPERLINK("https://example.invalid","open")',
    });
    state.response.baseline.label = ' =SUM(1,2), "baseline"';

    const csv = comparisonExportCsv(state, "2026-09-28T10:00:00.000Z");

    expect(csv).toContain('"baseline_label"');
    expect(csv).toContain('"\' =SUM(1,2), ""baseline"""');
    expect(csv).toContain('"\'=HYPERLINK(""https://example.invalid"",""open"")"');
    expect(csv).toContain('"baseline_error_rate_fraction"');
    expect(csv).toContain('"0.01"');
  });

  it("keeps missing values empty rather than turning them into zero", () => {
    const csv = comparisonExportCsv(
      availableState({
        status: "unavailable",
        conclusion: "unavailable",
        reason: "No metrics were recorded.",
        baselineMetricId: null,
        currentMetricId: null,
        p50DeltaMs: null,
        p50DeltaPct: null,
      }),
    );

    const [headerLine, dataLine] = csv.trimEnd().split("\r\n");
    const headers = parseCsvRow(headerLine);
    const values = parseCsvRow(dataLine);
    const row = Object.fromEntries(headers.map((header, index) => [header, values[index]]));

    expect(row).toMatchObject({
      status: "unavailable",
      conclusion: "unavailable",
      reason: "No metrics were recorded.",
      baseline_p50_ms: "",
      experiment_p50_ms: "",
      p50_delta_ms: "",
      p50_delta_pct: "",
    });
  });
});
