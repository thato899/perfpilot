"use client";

import { useState } from "react";
import type { Report } from "@perfpilot/schemas/types";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { SeverityBadge } from "@/components/dashboard/severity-badge";
import { downloadReportCsv } from "@/components/dashboard/report-export";

const KEY_METRIC_LABELS: Record<keyof Report["keyMetrics"], string> = {
  throughputRps: "Throughput",
  p50Ms: "Median latency",
  p95Ms: "p95 latency",
  p99Ms: "p99 latency",
  errorRate: "Error rate",
  peakConcurrencyTested: "Peak concurrency",
};

const KEY_METRIC_ORDER: (keyof Report["keyMetrics"])[] = [
  "throughputRps",
  "p95Ms",
  "p99Ms",
  "errorRate",
  "p50Ms",
  "peakConcurrencyTested",
];

function formatMetricValue(key: keyof Report["keyMetrics"], value: number): string {
  if (key === "errorRate") {
    return new Intl.NumberFormat(undefined, {
      style: "percent",
      maximumFractionDigits: 2,
    }).format(value);
  }
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(value);
}

function metricUnit(key: keyof Report["keyMetrics"], value: number): string {
  if (key === "throughputRps") return "req/s";
  if (key === "p50Ms" || key === "p95Ms" || key === "p99Ms") return "ms";
  if (key === "peakConcurrencyTested") return value === 1 ? "user" : "users";
  return "";
}

function formatMetric(key: keyof Report["keyMetrics"], value: number): string {
  return [formatMetricValue(key, value), metricUnit(key, value)].filter(Boolean).join(" ");
}

export function ReportView({
  report,
  hasPreviousRun = true,
}: {
  report: Report;
  hasPreviousRun?: boolean;
}) {
  const [exportError, setExportError] = useState<string | null>(null);
  const peakConcurrency = report.keyMetrics.peakConcurrencyTested;
  const allRequestsFailed = report.keyMetrics.errorRate >= 1;
  const capacityEstablished = peakConcurrency > 1 && !allRequestsFailed;

  return (
    <div id="report" className="scroll-mt-6 flex flex-col gap-6">
      <section aria-labelledby="report-summary-title">
        <Card className="overflow-hidden border-primary/20 shadow-sm">
          <CardHeader className="border-b bg-gradient-to-r from-primary/[0.08] to-transparent px-5 py-5 sm:px-6">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">
              Run summary
            </p>
            <CardTitle id="report-summary-title" className="text-xl sm:text-2xl">
              Executive summary
            </CardTitle>
          </CardHeader>
          <CardContent className="px-5 py-5 sm:px-6">
            <p className="max-w-4xl text-sm leading-7 sm:text-base">{report.executiveSummary}</p>
            <Button
              type="button"
              variant="outline"
              className="mt-4"
              onClick={() => {
                setExportError(null);
                try {
                  downloadReportCsv(report, hasPreviousRun);
                } catch {
                  setExportError("Could not download the report CSV. Please try again.");
                }
              }}
            >
              Download report CSV
            </Button>
            {exportError && (
              <p role="alert" className="mt-2 text-sm text-destructive">
                {exportError}
              </p>
            )}
          </CardContent>
        </Card>
      </section>

      {allRequestsFailed && (
        <div
          role="note"
          className="rounded-xl border border-amber-300/70 bg-amber-50/80 px-4 py-3 text-sm leading-relaxed text-amber-950 dark:border-amber-700/60 dark:bg-amber-950/30 dark:text-amber-100"
        >
          All measured requests failed. Latency here measures failed responses, and the error rate
          alone does not identify a cause. Check the exact request path and HTTP response from the
          load worker before testing more users.
        </div>
      )}

      {peakConcurrency <= 1 && (
        <div
          role="note"
          className="flex flex-col gap-1 rounded-xl border border-amber-300/70 bg-amber-50/80 px-4 py-3 text-sm text-amber-950 dark:border-amber-700/60 dark:bg-amber-950/30 dark:text-amber-100 sm:flex-row sm:items-start sm:gap-3"
        >
          <Badge
            variant="outline"
            className="w-fit border-amber-400 text-amber-800 dark:text-amber-200"
          >
            Limited load coverage
          </Badge>
          <p className="leading-relaxed">
            Only {peakConcurrency} concurrent user{peakConcurrency === 1 ? "" : "s"} tested. This
            confirms behavior at the tested load; it does not establish the application&apos;s
            capacity.
          </p>
        </div>
      )}

      <div
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
        aria-label="Key performance metrics"
      >
        {KEY_METRIC_ORDER.map((key) => (
          <Card key={key} className="gap-2 py-4">
            <CardContent className="px-4">
              <dl>
                <dt className="text-sm font-medium text-muted-foreground">
                  {KEY_METRIC_LABELS[key]}
                </dt>
                <dd className="mt-2 text-2xl font-semibold tracking-tight tabular-nums sm:text-3xl">
                  <span>{formatMetricValue(key, report.keyMetrics[key])}</span>
                  {metricUnit(key, report.keyMetrics[key]) && (
                    <span className="ml-1 text-sm font-medium text-muted-foreground">
                      {metricUnit(key, report.keyMetrics[key])}
                    </span>
                  )}
                </dd>
              </dl>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Capacity estimate</CardTitle>
            <CardDescription>
              Interpret this estimate alongside the tested concurrency.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 pb-4 text-sm">
            {capacityEstablished ? (
              <>
                <div className="flex items-baseline justify-between gap-4">
                  <span className="text-muted-foreground">Estimated sustainable</span>
                  <span className="text-right font-semibold tabular-nums">
                    ~{report.capacity.estimatedSustainableUsers} users
                  </span>
                </div>
                <div className="flex items-baseline justify-between gap-4">
                  <span className="text-muted-foreground">Recommended operating</span>
                  <span className="text-right font-semibold tabular-nums">
                    {report.capacity.recommendedOperatingUsers} users
                  </span>
                </div>
              </>
            ) : (
              <>
                <p className="text-lg font-semibold">Not established</p>
                <p className="leading-relaxed text-muted-foreground">
                  {allRequestsFailed
                    ? "All measured requests failed. Resolve the endpoint failure before estimating capacity."
                    : `The run reached ${formatMetric("peakConcurrencyTested", peakConcurrency)}. A higher load test is needed to estimate capacity.`}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {hasPreviousRun ? (
          <Card>
            <CardHeader>
              <CardTitle>Change from previous run</CardTitle>
              <CardDescription>Compared using the p95 response time.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 pb-4 text-sm">
              <div className="flex items-baseline justify-between gap-4">
                <span className="text-muted-foreground">Previous p95</span>
                <span className="font-semibold tabular-nums">
                  {formatMetric("p95Ms", report.regression.previousP95Ms)}
                </span>
              </div>
              <div className="flex items-baseline justify-between gap-4">
                <span className="text-muted-foreground">Current p95</span>
                <span className="font-semibold tabular-nums">
                  {formatMetric("p95Ms", report.regression.currentP95Ms)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4 border-t pt-3">
                <span className="text-muted-foreground">Change</span>
                <Badge variant={report.regression.regressionPct > 0 ? "destructive" : "secondary"}>
                  {report.regression.regressionPct > 0 ? "+" : ""}
                  {report.regression.regressionPct}%
                </Badge>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Run comparison</CardTitle>
              <CardDescription>No separate previous run is linked to this result.</CardDescription>
            </CardHeader>
            <CardContent className="pb-4 text-sm leading-relaxed text-muted-foreground">
              Create a later run to see whether a change improved or regressed performance.
            </CardContent>
          </Card>
        )}
      </div>

      {report.findings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Findings</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {report.findings.map((finding) => (
              <div key={finding.id} className="rounded-lg border bg-card p-4 text-sm">
                <div className="mb-2 flex items-center gap-2">
                  <SeverityBadge severity={finding.severity} />
                </div>
                <p className="leading-relaxed">{finding.summary}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {report.bottleneckAnalysis.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Bottleneck analysis</CardTitle>
            <CardDescription>
              Likely causes are interpretations of the measurements.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {report.bottleneckAnalysis.map((entry, i) => (
              <div key={i} className="flex flex-col gap-2 text-sm">
                <p className="font-medium">{entry.observation}</p>
                <p className="text-muted-foreground">
                  Likely cause: {entry.likelyCause} ({Math.round(entry.confidence * 100)}%
                  confidence)
                </p>
                <ul className="list-inside list-disc space-y-1 text-muted-foreground">
                  {entry.evidence.map((e, j) => (
                    <li key={j}>{e}</li>
                  ))}
                </ul>
                {i < report.bottleneckAnalysis.length - 1 && <Separator className="mt-2" />}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {report.findings.some((finding) => finding.severity !== "INFO") &&
        report.bottleneckAnalysis.length === 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Cause not established</CardTitle>
              <CardDescription>
                The run measured degradation, but its evidence does not identify a bottleneck.
              </CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Collect HTTP failure status codes, server and database metrics, and edge or access
              logs during an approved repeat test before assigning a cause.
            </CardContent>
          </Card>
        )}

      {report.recommendations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recommendations</CardTitle>
            <CardDescription>Suggested next steps based on this run.</CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="flex flex-col gap-3">
              {report.recommendations.map((rec, i) => (
                <li key={i} className="flex items-start gap-3 rounded-lg border p-3 text-sm">
                  <SeverityBadge severity={rec.priority} />
                  <span className="leading-relaxed">{rec.statement}</span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
