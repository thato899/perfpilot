import type { InvestigationState, TestRun } from "@perfpilot/schemas/types";

import { SeverityBadge } from "@/components/dashboard/severity-badge";
import { InvestigationStatusBadge } from "@/components/dashboard/status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

export function InvestigationProgress({
  investigation,
  testRun,
}: {
  investigation: InvestigationState;
  testRun: TestRun | null;
}) {
  const latestDecisions = [...investigation.decisions].reverse();
  const progress = testRun?.progress;
  const progressPercent =
    progress && progress.targetVus > 0
      ? Math.min(100, (progress.currentVus / progress.targetVus) * 100)
      : 0;

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
        {testRun ? (
          <div className="flex flex-col gap-2">
            <div className="flex justify-between text-sm text-muted-foreground">
              <span>Test run: {testRun.status}</span>
              <span>
                {progress?.currentVus ?? 0} / {progress?.targetVus ?? 0} concurrent users
              </span>
            </div>
            <Progress value={progressPercent} />
            {testRun.clamped && (
              <p className="text-xs text-amber-700 dark:text-amber-300">{testRun.clamped.reason}</p>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No test run is linked to this investigation yet. Progress is reported only from the
            backend state; no client-side completion is fabricated.
          </p>
        )}

        {investigation.findings.length > 0 && (
          <div className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">Findings and hypotheses</h3>
            {investigation.findings.map((finding) => {
              const hypotheses = investigation.hypotheses.filter(
                (hypothesis) => hypothesis.findingId === finding.id,
              );
              return (
                <div key={finding.id} className="rounded-md border p-3 text-sm">
                  <div className="mb-1 flex items-center gap-2">
                    <SeverityBadge severity={finding.severity} />
                    <span className="font-medium">{finding.summary}</span>
                  </div>
                  {finding.observations.map((observation) => (
                    <p key={observation.id} className="text-muted-foreground">
                      {observation.statement}{" "}
                      <span className="text-xs">({observation.metricRef})</span>
                    </p>
                  ))}
                  {hypotheses.map((hypothesis) => (
                    <div key={hypothesis.id} className="mt-2 border-t pt-2">
                      <p className="text-muted-foreground">
                        Hypothesis: {hypothesis.statement} (
                        {Math.round(hypothesis.confidence * 100)}% confidence, {hypothesis.status})
                      </p>
                      {hypothesis.evidence.map((evidence) => (
                        <p key={evidence.sourceRef} className="text-xs text-muted-foreground">
                          Evidence: {evidence.statement} ({evidence.sourceRef})
                        </p>
                      ))}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}

        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">Timeline</h3>
          {latestDecisions.length > 0 ? (
            <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
              {latestDecisions.map((decision, index) => (
                <li key={`${decision.step}-${index}`}>{decision.decision}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No orchestrator decisions recorded.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
