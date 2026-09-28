import Link from "next/link";
import type { ComparisonResponse, Metric, MetricComparison } from "@perfpilot/schemas/types";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export type ComparisonState =
  | { status: "loading" }
  | { status: "missing"; message: string }
  | { status: "incompatible"; message: string }
  | { status: "unavailable"; message: string }
  | {
      status: "available";
      response: ComparisonResponse;
      baselineMetrics: Metric[];
      currentMetrics: Metric[];
      experimentId?: string;
    };

function number(value: number | null | undefined, digits = 2): string {
  return value == null || !Number.isFinite(value)
    ? "Unavailable"
    : value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function signed(value: number | null | undefined, suffix: string): string {
  return value == null || !Number.isFinite(value)
    ? "Unavailable"
    : `${value > 0 ? "+" : ""}${number(value)}${suffix}`;
}

function percent(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value)
    ? "Unavailable"
    : `${value > 0 ? "+" : ""}${number(value)}%`;
}

function metricById(metrics: Metric[], id: string | null | undefined): Metric | undefined {
  return id ? metrics.find((metric) => metric.id === id) : undefined;
}

interface DisplayRow {
  label: string;
  base: number | undefined;
  current: number | undefined;
  delta: number | null | undefined;
  change: number | null | undefined;
  unit: string;
  deltaUnit?: string;
  scale: number;
}

function ComparisonRows({
  comparison,
  baselineMetrics,
  currentMetrics,
}: {
  comparison: MetricComparison;
  baselineMetrics: Metric[];
  currentMetrics: Metric[];
}) {
  const baseline = metricById(baselineMetrics, comparison.baselineMetricId);
  const current = metricById(currentMetrics, comparison.currentMetricId);
  const rows: DisplayRow[] = [
    {
      label: "p50 latency",
      base: baseline?.p50Ms,
      current: current?.p50Ms,
      delta: comparison.p50DeltaMs,
      change: comparison.p50DeltaPct,
      unit: " ms",
      scale: 1,
    },
    {
      label: "p95 latency",
      base: baseline?.p95Ms,
      current: current?.p95Ms,
      delta: comparison.p95DeltaMs,
      change: comparison.p95DeltaPct,
      unit: " ms",
      scale: 1,
    },
    {
      label: "p99 latency",
      base: baseline?.p99Ms,
      current: current?.p99Ms,
      delta: comparison.p99DeltaMs,
      change: comparison.p99DeltaPct,
      unit: " ms",
      scale: 1,
    },
    {
      label: "Throughput",
      base: baseline?.throughputRps,
      current: current?.throughputRps,
      delta: comparison.throughputDeltaRps,
      change: comparison.throughputDeltaPct,
      unit: " req/s",
      scale: 1,
    },
    {
      label: "Error rate",
      base: baseline?.errorRate,
      current: current?.errorRate,
      delta: comparison.errorRateDelta,
      change: comparison.errorRateDeltaPct,
      unit: "%",
      deltaUnit: " pp",
      scale: 100,
    },
    {
      label: "Concurrency",
      base: comparison.baselineConcurrency ?? baseline?.concurrency,
      current: comparison.currentConcurrency ?? current?.concurrency,
      delta: comparison.concurrencyDelta,
      change: comparison.concurrencyDeltaPct,
      unit: " users",
      scale: 1,
    },
  ];

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Metric</TableHead>
          <TableHead className="text-right">Baseline</TableHead>
          <TableHead className="text-right">Experiment</TableHead>
          <TableHead className="text-right">Absolute delta</TableHead>
          <TableHead className="text-right">Change</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.label}>
            <TableCell>{row.label}</TableCell>
            <TableCell className="text-right">
              {number(row.base == null ? row.base : row.base * row.scale)}
              {row.base == null ? "" : row.unit}
            </TableCell>
            <TableCell className="text-right">
              {number(row.current == null ? row.current : row.current * row.scale)}
              {row.current == null ? "" : row.unit}
            </TableCell>
            <TableCell className="text-right">
              {row.delta == null
                ? "Unavailable"
                : signed(row.delta * row.scale, row.deltaUnit ?? row.unit)}
            </TableCell>
            <TableCell className="text-right">{percent(row.change)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function ComparisonView({ state }: { state: ComparisonState }) {
  return (
    <Card id="comparison">
      <CardHeader>
        <CardTitle>Baseline and experiment comparison</CardTitle>
        <CardDescription>
          Values and deltas come from the selected baseline, run metrics, and canonical comparison
          API.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {state.status === "loading" && (
          <p role="status" className="text-sm text-muted-foreground">
            Loading comparison…
          </p>
        )}
        {state.status === "missing" && (
          <p role="status" className="text-sm text-muted-foreground">
            {state.message}
          </p>
        )}
        {state.status === "incompatible" && (
          <div role="status" className="flex flex-col gap-2 text-sm">
            <Badge variant="destructive" className="w-fit">
              Incompatible
            </Badge>
            <p>{state.message}</p>
          </div>
        )}
        {state.status === "unavailable" && (
          <div role="status" className="flex flex-col gap-2 text-sm">
            <Badge variant="secondary" className="w-fit">
              Comparison unavailable
            </Badge>
            <p>{state.message}</p>
          </div>
        )}
        {state.status === "available" && (
          <>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
              <Badge variant="outline">Canonical data available</Badge>
              <span>
                Baseline:{" "}
                <Link
                  className="underline"
                  href={`/api/perfpilot/test-runs/${state.response.baseline.testRunId}`}
                >
                  {state.response.baseline.testRunId}
                </Link>
              </span>
              <span>
                Experiment:{" "}
                <Link
                  className="underline"
                  href={`/api/perfpilot/test-runs/${state.response.currentTestRunId}`}
                >
                  {state.response.currentTestRunId}
                </Link>
              </span>
              {state.experimentId && (
                <span>
                  Experiment record:{" "}
                  <Link className="underline" href={`#experiment-${state.experimentId}`}>
                    {state.experimentId}
                  </Link>
                </span>
              )}
              <Link className="underline" href="#findings">
                Related findings
              </Link>
              <Link className="underline" href="#report">
                Report
              </Link>
            </div>
            {(() => {
              const aggregate = state.response.comparisons.find(
                (item) => metricById(state.currentMetrics, item.currentMetricId)?.endpoint == null,
              );
              const thresholds = aggregate;
              return (
                <section
                  aria-label="Comparison conclusion"
                  className="flex flex-col gap-2 rounded-md border p-3 text-sm"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">Overall conclusion:</span>
                    <Badge
                      variant={aggregate?.conclusion === "regression" ? "destructive" : "secondary"}
                    >
                      {aggregate?.conclusion ?? "unavailable"}
                    </Badge>
                    {aggregate?.reason && <span>{aggregate.reason}</span>}
                    {aggregate?.baselineThresholdPassed != null && (
                      <span>
                        Baseline thresholds: {aggregate.baselineThresholdPassed ? "pass" : "fail"}
                      </span>
                    )}
                    {aggregate?.currentThresholdPassed != null && (
                      <span>
                        Experiment thresholds: {aggregate.currentThresholdPassed ? "pass" : "fail"}
                      </span>
                    )}
                  </div>
                  {thresholds?.baselineThresholds && thresholds.currentThresholds ? (
                    <p>
                      Thresholds — baseline: p95 ≤ {number(thresholds.baselineThresholds.p95Ms)} ms,
                      error rate ≤ {number(thresholds.baselineThresholds.maxErrorRate * 100)}%;
                      experiment: p95 ≤ {number(thresholds.currentThresholds.p95Ms)} ms, error rate
                      ≤ {number(thresholds.currentThresholds.maxErrorRate * 100)}%.
                    </p>
                  ) : (
                    <p className="text-muted-foreground">
                      Threshold values are unavailable for this run pair.
                    </p>
                  )}
                </section>
              );
            })()}
            {state.response.comparisons.map((comparison, index) => {
              const currentMetric = metricById(state.currentMetrics, comparison.currentMetricId);
              const scope = currentMetric?.endpoint ?? "Aggregate";
              return (
                <section
                  key={comparison.currentMetricId ?? index}
                  className="flex flex-col gap-2"
                  aria-label={`Comparison for ${scope}`}
                >
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <h3 className="font-medium">Scope: {scope}</h3>
                    <Badge variant={comparison.status === "available" ? "secondary" : "outline"}>
                      {comparison.status}
                    </Badge>
                    <span className="text-muted-foreground">
                      Conclusion: {comparison.conclusion}
                    </span>
                    {comparison.reason && (
                      <span className="text-muted-foreground">{comparison.reason}</span>
                    )}
                    {currentMetric && (
                      <Link
                        className="underline"
                        href={`/api/perfpilot/test-runs/${currentMetric.testRunId}/metrics`}
                      >
                        Metric record
                      </Link>
                    )}
                  </div>
                  {comparison.status === "available" ? (
                    <div className="overflow-x-auto">
                      <ComparisonRows
                        comparison={comparison}
                        baselineMetrics={state.baselineMetrics}
                        currentMetrics={state.currentMetrics}
                      />
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      {comparison.reason ?? "This metric pair cannot be compared."}
                    </p>
                  )}
                </section>
              );
            })}
            {state.response.comparisons.length === 0 && (
              <p role="status" className="text-sm">
                No shared metric scopes are available for comparison.
              </p>
            )}
            {(state.response.baselineOnlyEndpoints.length > 0 ||
              state.response.currentOnlyEndpoints.length > 0) && (
              <p className="text-sm text-muted-foreground">
                Unmatched endpoint scopes: baseline only{" "}
                {state.response.baselineOnlyEndpoints.map((v) => v ?? "aggregate").join(", ") ||
                  "none"}
                ; experiment only{" "}
                {state.response.currentOnlyEndpoints.map((v) => v ?? "aggregate").join(", ") ||
                  "none"}
                .
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
