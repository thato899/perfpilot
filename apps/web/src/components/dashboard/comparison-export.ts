import type { Metric, MetricComparison } from "@perfpilot/schemas/types";

import type { ComparisonState } from "./comparison-view";

export const COMPARISON_EXPORT_VERSION = "perfpilot.comparison.v1";

const metricValueFields = {
  p50_ms: "p50Ms",
  p90_ms: "p90Ms",
  p95_ms: "p95Ms",
  p99_ms: "p99Ms",
  throughput_rps: "throughputRps",
  error_rate_fraction: "errorRate",
  concurrency_users: "concurrency",
} as const;

const deltaFields = {
  p50_delta_ms: "p50DeltaMs",
  p50_delta_pct: "p50DeltaPct",
  p90_delta_ms: "p90DeltaMs",
  p90_delta_pct: "p90DeltaPct",
  p95_delta_ms: "p95DeltaMs",
  p95_delta_pct: "p95DeltaPct",
  p99_delta_ms: "p99DeltaMs",
  p99_delta_pct: "p99DeltaPct",
  throughput_delta_rps: "throughputDeltaRps",
  throughput_delta_pct: "throughputDeltaPct",
  error_rate_delta_fraction: "errorRateDelta",
  error_rate_delta_pct: "errorRateDeltaPct",
  concurrency_delta_users: "concurrencyDelta",
  concurrency_delta_pct: "concurrencyDeltaPct",
} as const;

type MetricValueKey = (typeof metricValueFields)[keyof typeof metricValueFields];
type DeltaKey = (typeof deltaFields)[keyof typeof deltaFields];

function metricById(metrics: Metric[], id: string | null | undefined): Metric | null {
  return id ? (metrics.find((metric) => metric.id === id) ?? null) : null;
}

function metricValues(
  metric: Metric | null,
): Record<keyof typeof metricValueFields, number | null> {
  return Object.fromEntries(
    Object.entries(metricValueFields).map(([exportName, sourceName]) => [
      exportName,
      metric?.[sourceName as MetricValueKey] ?? null,
    ]),
  ) as Record<keyof typeof metricValueFields, number | null>;
}

function comparisonDeltas(
  comparison: MetricComparison,
): Record<keyof typeof deltaFields, number | null> {
  return Object.fromEntries(
    Object.entries(deltaFields).map(([exportName, sourceName]) => [
      exportName,
      comparison[sourceName as DeltaKey] ?? null,
    ]),
  ) as Record<keyof typeof deltaFields, number | null>;
}

function metricRow(
  state: Extract<ComparisonState, { status: "available" }>,
  comparison: MetricComparison,
) {
  const baselineMetric = metricById(state.baselineMetrics, comparison.baselineMetricId);
  const currentMetric = metricById(state.currentMetrics, comparison.currentMetricId);
  return {
    scope: currentMetric?.endpoint ?? baselineMetric?.endpoint ?? null,
    status: comparison.status,
    conclusion: comparison.conclusion,
    reason: comparison.reason ?? null,
    baseline_metric_id: comparison.baselineMetricId ?? null,
    current_metric_id: comparison.currentMetricId ?? null,
    baseline_test_run_id:
      comparison.baselineTestRunId ??
      baselineMetric?.testRunId ??
      state.response.baseline.testRunId,
    current_test_run_id:
      comparison.currentTestRunId ?? currentMetric?.testRunId ?? state.response.currentTestRunId,
    baseline: {
      ...metricValues(baselineMetric),
      concurrency_users: comparison.baselineConcurrency ?? baselineMetric?.concurrency ?? null,
    },
    experiment: {
      ...metricValues(currentMetric),
      concurrency_users: comparison.currentConcurrency ?? currentMetric?.concurrency ?? null,
    },
    deltas: comparisonDeltas(comparison),
    thresholds: {
      baseline: comparison.baselineThresholds
        ? {
            p95_ms: comparison.baselineThresholds.p95Ms,
            max_error_rate_fraction: comparison.baselineThresholds.maxErrorRate,
          }
        : null,
      experiment: comparison.currentThresholds
        ? {
            p95_ms: comparison.currentThresholds.p95Ms,
            max_error_rate_fraction: comparison.currentThresholds.maxErrorRate,
          }
        : null,
      baseline_passed: comparison.baselineThresholdPassed ?? null,
      experiment_passed: comparison.currentThresholdPassed ?? null,
    },
  };
}

export function buildComparisonExport(
  state: Extract<ComparisonState, { status: "available" }>,
  generatedAt = new Date().toISOString(),
) {
  return {
    schema_version: COMPARISON_EXPORT_VERSION,
    generated_at: generatedAt,
    target_id: state.response.baseline.targetId,
    baseline: {
      id: state.response.baseline.id,
      target_id: state.response.baseline.targetId,
      test_run_id: state.response.baseline.testRunId,
      label: state.response.baseline.label,
      selected_by: state.response.baseline.selectedBy,
      test_type: state.response.baseline.testType,
      target_concurrency_users: state.response.baseline.targetConcurrency,
      scenario_fingerprint: state.response.baseline.scenarioFingerprint,
    },
    experiment: {
      id: state.experimentId ?? null,
      test_run_id: state.response.currentTestRunId,
    },
    units: {
      latency: "ms",
      throughput: "requests/second",
      error_rate: "fraction (0–1)",
      concurrency: "users",
      threshold_max_error_rate: "fraction (0–1)",
    },
    baseline_only_endpoints: state.response.baselineOnlyEndpoints,
    experiment_only_endpoints: state.response.currentOnlyEndpoints,
    comparisons: state.response.comparisons.map((comparison) => metricRow(state, comparison)),
  };
}

const csvColumns = [
  "schema_version",
  "generated_at",
  "target_id",
  "baseline_id",
  "baseline_label",
  "baseline_selected_by",
  "baseline_test_type",
  "baseline_test_run_id",
  "baseline_target_concurrency_users",
  "baseline_scenario_fingerprint",
  "experiment_id",
  "experiment_test_run_id",
  "scope",
  "status",
  "conclusion",
  "reason",
  "baseline_metric_id",
  "current_metric_id",
  "baseline_p50_ms",
  "experiment_p50_ms",
  "p50_delta_ms",
  "p50_delta_pct",
  "baseline_p90_ms",
  "experiment_p90_ms",
  "p90_delta_ms",
  "p90_delta_pct",
  "baseline_p95_ms",
  "experiment_p95_ms",
  "p95_delta_ms",
  "p95_delta_pct",
  "baseline_p99_ms",
  "experiment_p99_ms",
  "p99_delta_ms",
  "p99_delta_pct",
  "baseline_throughput_rps",
  "experiment_throughput_rps",
  "throughput_delta_rps",
  "throughput_delta_pct",
  "baseline_error_rate_fraction",
  "experiment_error_rate_fraction",
  "error_rate_delta_fraction",
  "error_rate_delta_pct",
  "baseline_concurrency_users",
  "experiment_concurrency_users",
  "concurrency_delta_users",
  "concurrency_delta_pct",
  "baseline_threshold_p95_ms",
  "baseline_threshold_max_error_rate_fraction",
  "baseline_threshold_passed",
  "experiment_threshold_p95_ms",
  "experiment_threshold_max_error_rate_fraction",
  "experiment_threshold_passed",
  "baseline_only_endpoints",
  "experiment_only_endpoints",
] as const;

function csvCell(value: unknown): string {
  let text = value == null ? "" : String(value);
  if (typeof value === "string" && /^[\s]*[=+@-]/.test(text)) {
    text = `'${text}`;
  }
  return `"${text.replaceAll('"', '""')}"`;
}

export function comparisonExportCsv(
  state: Extract<ComparisonState, { status: "available" }>,
  generatedAt = new Date().toISOString(),
): string {
  const data = buildComparisonExport(state, generatedAt);
  const lines = [csvColumns.map(csvCell).join(",")];

  for (const comparison of data.comparisons) {
    const values: Record<(typeof csvColumns)[number], unknown> = {
      schema_version: data.schema_version,
      generated_at: data.generated_at,
      target_id: data.target_id,
      baseline_id: data.baseline.id,
      baseline_label: data.baseline.label,
      baseline_selected_by: data.baseline.selected_by,
      baseline_test_type: data.baseline.test_type,
      baseline_test_run_id: data.baseline.test_run_id,
      baseline_target_concurrency_users: data.baseline.target_concurrency_users,
      baseline_scenario_fingerprint: data.baseline.scenario_fingerprint,
      experiment_id: data.experiment.id,
      experiment_test_run_id: data.experiment.test_run_id,
      scope: comparison.scope ?? "aggregate",
      status: comparison.status,
      conclusion: comparison.conclusion,
      reason: comparison.reason,
      baseline_metric_id: comparison.baseline_metric_id,
      current_metric_id: comparison.current_metric_id,
      baseline_p50_ms: comparison.baseline.p50_ms,
      experiment_p50_ms: comparison.experiment.p50_ms,
      p50_delta_ms: comparison.deltas.p50_delta_ms,
      p50_delta_pct: comparison.deltas.p50_delta_pct,
      baseline_p90_ms: comparison.baseline.p90_ms,
      experiment_p90_ms: comparison.experiment.p90_ms,
      p90_delta_ms: comparison.deltas.p90_delta_ms,
      p90_delta_pct: comparison.deltas.p90_delta_pct,
      baseline_p95_ms: comparison.baseline.p95_ms,
      experiment_p95_ms: comparison.experiment.p95_ms,
      p95_delta_ms: comparison.deltas.p95_delta_ms,
      p95_delta_pct: comparison.deltas.p95_delta_pct,
      baseline_p99_ms: comparison.baseline.p99_ms,
      experiment_p99_ms: comparison.experiment.p99_ms,
      p99_delta_ms: comparison.deltas.p99_delta_ms,
      p99_delta_pct: comparison.deltas.p99_delta_pct,
      baseline_throughput_rps: comparison.baseline.throughput_rps,
      experiment_throughput_rps: comparison.experiment.throughput_rps,
      throughput_delta_rps: comparison.deltas.throughput_delta_rps,
      throughput_delta_pct: comparison.deltas.throughput_delta_pct,
      baseline_error_rate_fraction: comparison.baseline.error_rate_fraction,
      experiment_error_rate_fraction: comparison.experiment.error_rate_fraction,
      error_rate_delta_fraction: comparison.deltas.error_rate_delta_fraction,
      error_rate_delta_pct: comparison.deltas.error_rate_delta_pct,
      baseline_concurrency_users: comparison.baseline.concurrency_users,
      experiment_concurrency_users: comparison.experiment.concurrency_users,
      concurrency_delta_users: comparison.deltas.concurrency_delta_users,
      concurrency_delta_pct: comparison.deltas.concurrency_delta_pct,
      baseline_threshold_p95_ms: comparison.thresholds.baseline?.p95_ms ?? null,
      baseline_threshold_max_error_rate_fraction:
        comparison.thresholds.baseline?.max_error_rate_fraction ?? null,
      baseline_threshold_passed: comparison.thresholds.baseline_passed,
      experiment_threshold_p95_ms: comparison.thresholds.experiment?.p95_ms ?? null,
      experiment_threshold_max_error_rate_fraction:
        comparison.thresholds.experiment?.max_error_rate_fraction ?? null,
      experiment_threshold_passed: comparison.thresholds.experiment_passed,
      baseline_only_endpoints: JSON.stringify(data.baseline_only_endpoints),
      experiment_only_endpoints: JSON.stringify(data.experiment_only_endpoints),
    };
    lines.push(csvColumns.map((column) => csvCell(values[column])).join(","));
  }

  return `${lines.join("\r\n")}\r\n`;
}

function safeFilenamePart(value: string): string {
  return value.replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 80) || "comparison";
}

export function downloadComparisonExport(
  state: Extract<ComparisonState, { status: "available" }>,
  format: "csv" | "json",
): void {
  const filename = `comparison-${safeFilenamePart(state.response.currentTestRunId)}.${format}`;
  const content =
    format === "csv"
      ? comparisonExportCsv(state)
      : `${JSON.stringify(buildComparisonExport(state), null, 2)}\n`;
  const blob = new Blob([content], {
    type: format === "csv" ? "text/csv;charset=utf-8" : "application/json;charset=utf-8",
  });
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.append(anchor);

  try {
    anchor.click();
  } finally {
    anchor.remove();
    window.setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
  }
}
