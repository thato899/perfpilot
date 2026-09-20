import type {
  ExperimentRecord,
  Finding,
  Hypothesis,
  InvestigationState,
} from "@perfpilot/schemas/types";

import { SeverityBadge } from "@/components/dashboard/severity-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

function stateLabel(value: string): string {
  return value.replaceAll("_", " ");
}

function ExperimentStatus({ experiment }: { experiment: ExperimentRecord }) {
  return (
    <div className="rounded-md border bg-muted/30 p-3 text-sm">
      <p className="font-medium">Experiment {experiment.id}</p>
      <dl className="mt-2 grid gap-1 text-muted-foreground sm:grid-cols-2">
        <div>
          <dt className="inline font-medium">Approval / execution state: </dt>
          <dd className="inline">{stateLabel(experiment.status)}</dd>
        </div>
        <div>
          <dt className="inline font-medium">Variable: </dt>
          <dd className="inline">{experiment.variableChanged}</dd>
        </div>
        {experiment.testRunId && (
          <div>
            <dt className="inline font-medium">Related run: </dt>
            <dd className="inline">{experiment.testRunId}</dd>
          </div>
        )}
        {experiment.testPlanId && (
          <div>
            <dt className="inline font-medium">Test plan: </dt>
            <dd className="inline">{experiment.testPlanId}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}

function HypothesisCard({
  hypothesis,
  experiment,
}: {
  hypothesis: Hypothesis;
  experiment?: ExperimentRecord;
}) {
  return (
    <article className="rounded-md border p-4" aria-labelledby={`hypothesis-${hypothesis.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h4 id={`hypothesis-${hypothesis.id}`} className="font-medium">
          Hypothesis
        </h4>
        <Badge variant="outline">{stateLabel(hypothesis.status)}</Badge>
        <span className="text-sm text-muted-foreground">
          AI confidence: {hypothesis.confidence}
        </span>
      </div>
      <p className="mt-2 text-sm">{hypothesis.statement}</p>
      <div className="mt-3 border-l-2 pl-3 text-sm">
        <p className="font-medium">Evidence</p>
        {hypothesis.evidence.length ? (
          <ul className="mt-1 list-inside list-disc text-muted-foreground">
            {hypothesis.evidence.map((item, index) => (
              <li key={`${item.sourceRef}-${index}`}>
                {item.statement} <span>({item.sourceRef})</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted-foreground">No evidence supplied by the API.</p>
        )}
      </div>
      {hypothesis.recommendedExperiment && (
        <div className="mt-3 text-sm text-muted-foreground">
          <p className="font-medium text-foreground">Recommended experiment</p>
          <p>
            Isolate {hypothesis.recommendedExperiment.variableToIsolate}:{" "}
            {hypothesis.recommendedExperiment.change}
          </p>
          <p>Expected signal: {hypothesis.recommendedExperiment.expectedSignal}</p>
        </div>
      )}
      {experiment && (
        <div className="mt-3">
          <ExperimentStatus experiment={experiment} />
        </div>
      )}
    </article>
  );
}

function FindingCard({
  finding,
  hypotheses,
  experiments,
}: {
  finding: Finding;
  hypotheses: Hypothesis[];
  experiments: ExperimentRecord[];
}) {
  return (
    <article className="rounded-lg border p-4" aria-labelledby={`finding-${finding.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 id={`finding-${finding.id}`} className="font-medium">
          {finding.summary}
        </h3>
        <SeverityBadge severity={finding.severity} />
        <span className="text-xs text-muted-foreground">ID: {finding.id}</span>
      </div>
      <section
        className="mt-4 rounded-md bg-muted/30 p-3"
        aria-labelledby={`measurement-${finding.id}`}
      >
        <h4 id={`measurement-${finding.id}`} className="text-sm font-medium">
          Deterministic measurement
        </h4>
        {finding.observations.length ? (
          <ul className="mt-1 list-inside list-disc text-sm text-muted-foreground">
            {finding.observations.map((observation) => (
              <li key={observation.id}>
                {observation.statement} <span>(metric: {observation.metricRef})</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            No metric evidence supplied by the API.
          </p>
        )}
      </section>
      <section className="mt-4" aria-labelledby={`interpretation-${finding.id}`}>
        <h4 id={`interpretation-${finding.id}`} className="text-sm font-medium">
          AI interpretation — hypotheses
        </h4>
        <div className="mt-2 flex flex-col gap-3">
          {hypotheses.length ? (
            hypotheses.map((hypothesis) => (
              <HypothesisCard
                key={hypothesis.id}
                hypothesis={hypothesis}
                experiment={experiments.find((item) => item.hypothesisId === hypothesis.id)}
              />
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No hypotheses are currently recorded.</p>
          )}
        </div>
      </section>
    </article>
  );
}

export function FindingsPanel({ investigation }: { investigation: InvestigationState }) {
  const findings = [...investigation.findings].sort(
    (a, b) => (a.sequenceIndex ?? 0) - (b.sequenceIndex ?? 0),
  );
  return (
    <Card>
      <CardHeader>
        <CardTitle>Findings and hypotheses</CardTitle>
        <CardDescription>
          Measurements are deterministic API observations. Hypotheses and confidence are AI
          interpretations.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {investigation.experimentBudget && (
          <div className="rounded-md border p-3 text-sm" aria-label="Experiment budget">
            <span className="font-medium">Experiment budget:</span>{" "}
            {investigation.experimentBudget.consumed} used of{" "}
            {investigation.experimentBudget.maxExperiments};{" "}
            {investigation.experimentBudget.remaining} remaining
            {investigation.experimentBudget.exhausted ? " — exhausted" : ""}.
          </div>
        )}
        {findings.length ? (
          findings.map((finding) => (
            <FindingCard
              key={finding.id}
              finding={finding}
              hypotheses={investigation.hypotheses.filter((item) => item.findingId === finding.id)}
              experiments={investigation.experiments}
            />
          ))
        ) : (
          <p className="text-sm text-muted-foreground">
            No findings were recorded. The investigation may be healthy or still in progress.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
