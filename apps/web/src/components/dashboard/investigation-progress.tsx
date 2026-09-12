import type { InvestigationState } from "@perfpilot/schemas/types";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { SeverityBadge } from "@/components/dashboard/severity-badge";
import { InvestigationStatusBadge } from "@/components/dashboard/status-badge";

const MAX_VUS_SHOWN = 1000; // matches docs/demo-scenario.md's peak traffic

/** "Watch a test run's progress" — renders live `InvestigationState`
 * exactly as `GET /api/investigations/{id}` will return it once apps/api
 * exists (docs/api/api-contract.md). This component owns none of the
 * ticking/polling itself — the page passes in whatever state it currently
 * has, same as it would after each `fetch`. */
export function InvestigationProgress({
  investigation,
  currentVus,
}: {
  investigation: InvestigationState;
  currentVus: number;
}) {
  const latestDecisions = [...investigation.decisions].reverse();

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Investigation progress</CardTitle>
          <InvestigationStatusBadge status={investigation.status} />
        </div>
        <CardDescription>Investigation {investigation.investigationId}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>Concurrent users</span>
            <span>
              {currentVus} / {MAX_VUS_SHOWN}
            </span>
          </div>
          <Progress value={(currentVus / MAX_VUS_SHOWN) * 100} />
        </div>

        {investigation.findings.length > 0 && (
          <div className="flex flex-col gap-2">
            <h3 className="text-sm font-medium">Findings</h3>
            {investigation.findings.map((finding) => {
              const hypothesis = investigation.hypotheses.find((h) => h.findingId === finding.id);
              return (
                <div key={finding.id} className="rounded-md border p-3 text-sm">
                  <div className="mb-1 flex items-center gap-2">
                    <SeverityBadge severity={finding.severity} />
                    <span className="font-medium">{finding.summary}</span>
                  </div>
                  {hypothesis && (
                    <p className="text-muted-foreground">
                      Hypothesis: {hypothesis.statement} ({Math.round(hypothesis.confidence * 100)}%
                      confidence, {hypothesis.status})
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">Timeline</h3>
          <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
            {latestDecisions.map((decision, i) => (
              <li key={`${decision.step}-${i}`}>{decision.decision}</li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
