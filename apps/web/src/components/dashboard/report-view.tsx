import type { Report } from "@perfpilot/schemas/types";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SeverityBadge } from "@/components/dashboard/severity-badge";

const KEY_METRIC_LABELS: Record<keyof Report["keyMetrics"], string> = {
  throughputRps: "Throughput (req/s)",
  p50Ms: "p50 latency (ms)",
  p95Ms: "p95 latency (ms)",
  p99Ms: "p99 latency (ms)",
  errorRate: "Error rate",
  peakConcurrencyTested: "Peak concurrency tested",
};

/** "View the resulting report" — GET /api/reports/{id}
 * (docs/api/api-contract.md), rendering exactly the `Report` shape
 * docs/agents/reporting-agent.md's output schema defines. Every number
 * here came from the agent unaltered from packages/metrics/the Reporting
 * Agent's input — this component only formats, it doesn't compute. */
export function ReportView({ report }: { report: Report }) {
  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Executive summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed">{report.executiveSummary}</p>
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Capacity</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Estimated sustainable</span>
              <span className="font-medium">
                ~{report.capacity.estimatedSustainableUsers} concurrent users
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Recommended operating</span>
              <span className="font-medium">
                {report.capacity.recommendedOperatingUsers} concurrent users
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Regression vs. previous run</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Previous p95</span>
              <span className="font-medium">{report.regression.previousP95Ms} ms</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Current p95</span>
              <span className="font-medium">{report.regression.currentP95Ms} ms</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Change</span>
              <Badge variant={report.regression.regressionPct > 0 ? "destructive" : "secondary"}>
                {report.regression.regressionPct > 0 ? "+" : ""}
                {report.regression.regressionPct}%
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Key metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Metric</TableHead>
                <TableHead className="text-right">Value</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(Object.keys(KEY_METRIC_LABELS) as (keyof Report["keyMetrics"])[]).map((key) => (
                <TableRow key={key}>
                  <TableCell>{KEY_METRIC_LABELS[key]}</TableCell>
                  <TableCell className="text-right">{report.keyMetrics[key]}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {report.findings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Findings</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {report.findings.map((finding) => (
              <div key={finding.id} className="rounded-md border p-3 text-sm">
                <div className="mb-1 flex items-center gap-2">
                  <SeverityBadge severity={finding.severity} />
                </div>
                <p>{finding.summary}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {report.bottleneckAnalysis.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Bottleneck analysis</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {report.bottleneckAnalysis.map((entry, i) => (
              <div key={i} className="flex flex-col gap-1 text-sm">
                <p className="font-medium">{entry.observation}</p>
                <p>
                  Likely cause: {entry.likelyCause} ({Math.round(entry.confidence * 100)}%
                  confidence)
                </p>
                <ul className="list-inside list-disc text-muted-foreground">
                  {entry.evidence.map((e, j) => (
                    <li key={j}>{e}</li>
                  ))}
                </ul>
                {i < report.bottleneckAnalysis.length - 1 && <Separator className="mt-3" />}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {report.recommendations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recommendations</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="flex flex-col gap-2 text-sm">
              {report.recommendations.map((rec, i) => (
                <li key={i} className="flex items-start gap-2">
                  <SeverityBadge severity={rec.priority} />
                  <span>{rec.statement}</span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
