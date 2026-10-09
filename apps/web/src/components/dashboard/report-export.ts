import type { Report } from "@perfpilot/schemas/types";

function csvCell(value: string | number | undefined): string {
  let text = value == null ? "" : String(value);
  if (typeof value === "string" && /^[\s]*[=+@-]/.test(text)) {
    text = `'${text}`;
  }
  return `"${text.replaceAll('"', '""')}"`;
}

export function reportExportCsv(report: Report, hasPreviousRun: boolean): string {
  const rows: Array<Array<string | number | undefined>> = [
    ["section", "item", "value", "unit", "evidence", "confidence", "priority", "reference_id"],
    ["metadata", "report_id", report.id],
    ["metadata", "investigation_id", report.investigationId],
    ["summary", "executive_summary", report.executiveSummary],
    ["metric", "throughput", report.keyMetrics.throughputRps, "requests/second"],
    ["metric", "p50", report.keyMetrics.p50Ms, "ms"],
    ["metric", "p95", report.keyMetrics.p95Ms, "ms"],
    ["metric", "p99", report.keyMetrics.p99Ms, "ms"],
    ["metric", "error_rate", report.keyMetrics.errorRate, "fraction"],
    ["metric", "peak_concurrency_tested", report.keyMetrics.peakConcurrencyTested, "virtual users"],
  ];

  if (report.keyMetrics.peakConcurrencyTested <= 1) {
    rows.push(["capacity_estimate", "status", "not established by a one-user run"]);
  } else {
    rows.push(
      [
        "capacity_estimate",
        "sustainable_users",
        report.capacity.estimatedSustainableUsers,
        "virtual users",
      ],
      [
        "capacity_estimate",
        "recommended_operating_users",
        report.capacity.recommendedOperatingUsers,
        "virtual users",
      ],
    );
  }

  if (hasPreviousRun) {
    rows.push(
      ["regression", "previous_p95", report.regression.previousP95Ms, "ms"],
      ["regression", "current_p95", report.regression.currentP95Ms, "ms"],
      ["regression", "change", report.regression.regressionPct, "percent"],
    );
  }

  for (const finding of report.findings) {
    rows.push(["finding", "summary", finding.summary, "", "", "", finding.severity, finding.id]);
  }
  for (const cause of report.bottleneckAnalysis) {
    rows.push([
      "hypothesis",
      "likely_cause",
      cause.likelyCause,
      "",
      [cause.observation, ...cause.evidence].join(" | "),
      cause.confidence,
    ]);
  }
  for (const recommendation of report.recommendations) {
    rows.push([
      "recommendation",
      "statement",
      recommendation.statement,
      "",
      "",
      "",
      recommendation.priority,
      recommendation.findingId,
    ]);
  }

  return `${rows.map((row) => row.map(csvCell).join(",")).join("\r\n")}\r\n`;
}

export function downloadReportCsv(report: Report, hasPreviousRun: boolean): void {
  const content = reportExportCsv(report, hasPreviousRun);
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `perfpilot-report-${report.investigationId.replace(/[^A-Za-z0-9_-]/g, "_")}.csv`;
  anchor.style.display = "none";
  document.body.append(anchor);

  try {
    anchor.click();
  } finally {
    anchor.remove();
    window.setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
  }
}
