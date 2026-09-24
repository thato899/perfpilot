/**
 * Investigation timeline — issue #37 (P2-UI-1).
 *
 * Renders the ordered event history #35 persists, plus the run state and
 * experiment budget that go with it. Every state this component can be in is
 * explicit and labelled: first load, empty, stale, API error, reconnecting,
 * terminal, and failed. There is no branch that guesses at progress.
 *
 * All text is rendered as React children, never through
 * dangerouslySetInnerHTML, so target-controlled strings that reach the payload
 * (a target name, an objective) are escaped by React rather than by a hand-
 * rolled sanitiser.
 */

import type { InvestigationState } from "@perfpilot/schemas/types";

import { InvestigationStatusBadge } from "@/components/dashboard/status-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  currentAction,
  formatTimestamp,
  hasSequenceGap,
  isTerminalStatus,
  toTimeline,
  type TimelineEntry,
} from "@/lib/investigation-events";

export interface InvestigationTimelineProps {
  /** null before the first successful load. */
  investigation: InvestigationState | null;
  /** True while the first request is still in flight. */
  loading?: boolean;
  /** The current polling error, or null when the last poll succeeded. */
  error?: string | null;
  /**
   * True when polling is failing but an earlier snapshot is still on screen.
   * The distinction matters: the data is real, it is just not current, and
   * saying so is different from either hiding it or implying it is live.
   */
  stale?: boolean;
  /** Epoch ms of the last successful poll, used for the stale notice. */
  lastUpdatedAt?: number | null;
  /** True while a retry is in flight after a failure. */
  reconnecting?: boolean;
}

function PhaseBadge({ entry }: { entry: TimelineEntry }) {
  return (
    <Badge variant="outline" className="shrink-0">
      {entry.phase}
    </Badge>
  );
}

function TimelineRow({ entry }: { entry: TimelineEntry }) {
  return (
    <li className="border-l-2 py-2 pl-4" data-testid={`timeline-entry-${entry.sequence}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span
          className="text-xs font-mono text-muted-foreground"
          aria-label={`Sequence ${entry.sequence}`}
        >
          #{entry.sequence}
        </span>
        <span className="font-medium">{entry.label}</span>
        <PhaseBadge entry={entry} />
        {!entry.known && (
          <Badge variant="outline" className="border-amber-500 text-amber-700 dark:text-amber-300">
            unrecognised event type
          </Badge>
        )}
      </div>

      <time
        dateTime={entry.occurredAt}
        className="mt-1 block text-xs text-muted-foreground"
        suppressHydrationWarning
      >
        {formatTimestamp(entry.occurredAt)}
      </time>

      {entry.detail && <p className="mt-1 text-sm text-muted-foreground">{entry.detail}</p>}

      {entry.relatedIds.length > 0 && (
        <dl className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {entry.relatedIds.map((related) => (
            <div key={`${entry.id}-${related.label}`}>
              <dt className="inline font-medium">{related.label}: </dt>
              <dd className="inline font-mono">{related.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </li>
  );
}

function BudgetSummary({ investigation }: { investigation: InvestigationState }) {
  const budget = investigation.experimentBudget;

  // No budget in the payload is its own state. A default of "0 of 0" would be
  // a number the server never sent.
  if (!budget) {
    return (
      <p className="text-sm text-muted-foreground">
        The API did not report an experiment budget for this investigation.
      </p>
    );
  }

  return (
    <p className="text-sm text-muted-foreground" data-testid="experiment-budget">
      Experiments: {budget.consumed} used, {budget.remaining} remaining of {budget.maxExperiments}
      {budget.exhausted && (
        <span className="ml-2 font-medium text-amber-700 dark:text-amber-300">
          budget exhausted
        </span>
      )}
    </p>
  );
}

export function InvestigationTimeline({
  investigation,
  loading = false,
  error = null,
  stale = false,
  lastUpdatedAt = null,
  reconnecting = false,
}: InvestigationTimelineProps) {
  // First load. Distinct from "empty": nothing is known yet, as opposed to
  // known-and-there-is-nothing.
  if (loading && !investigation) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Investigation timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <p role="status" className="text-sm text-muted-foreground">
            Loading the investigation timeline…
          </p>
        </CardContent>
      </Card>
    );
  }

  // Failed before anything arrived. Showing an empty timeline here would imply
  // an investigation with no history, which is a different claim.
  //
  // The reconnect notice belongs in this branch too. Without it the very case
  // it exists for — the first request failed and the page is still retrying —
  // rendered as a bare error, which reads as "this is over" rather than "we
  // are still trying".
  if (!investigation) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Investigation timeline</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          <p role="alert" className="text-sm text-destructive" data-testid="timeline-error">
            {error ?? "The investigation timeline is unavailable."}
          </p>
          {reconnecting && (
            <p
              role="status"
              className="text-sm text-muted-foreground"
              data-testid="timeline-reconnecting"
            >
              Reconnecting to the investigation API…
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  const entries = toTimeline(investigation.events);
  const gap = hasSequenceGap(entries);
  const terminal = isTerminalStatus(investigation.status);
  const failed = investigation.status === "failed";

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle id="investigation-timeline-heading">Investigation timeline</CardTitle>
          <InvestigationStatusBadge status={investigation.status} />
        </div>
        <CardDescription>
          {/* Server truth, announced politely rather than assertively: this
              region updates on every poll and an assertive live region would
              interrupt a screen-reader user mid-sentence. */}
          <span aria-live="polite" data-testid="current-action">
            {terminal ? currentAction(investigation) : `Now: ${currentAction(investigation)}`}
          </span>
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <BudgetSummary investigation={investigation} />

        {error && (
          <p role="alert" className="text-sm text-destructive" data-testid="timeline-error">
            {error}
          </p>
        )}

        {stale && (
          <p
            role="status"
            className="text-sm text-amber-700 dark:text-amber-300"
            data-testid="timeline-stale"
          >
            Showing the last state the API returned
            {lastUpdatedAt ? ` at ${formatTimestamp(new Date(lastUpdatedAt).toISOString())}` : ""}.
            It may be out of date.
          </p>
        )}

        {reconnecting && (
          <p
            role="status"
            className="text-sm text-muted-foreground"
            data-testid="timeline-reconnecting"
          >
            Reconnecting to the investigation API…
          </p>
        )}

        {gap && (
          <p
            role="status"
            className="text-sm text-amber-700 dark:text-amber-300"
            data-testid="timeline-gap"
          >
            Some events are missing from this history, so the timeline below is incomplete.
          </p>
        )}

        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground" data-testid="timeline-empty">
            No events have been recorded for this investigation yet.
          </p>
        ) : (
          <ol
            aria-labelledby="investigation-timeline-heading"
            className="flex flex-col"
            data-testid="timeline-list"
          >
            {entries.map((entry) => (
              <TimelineRow key={entry.id} entry={entry} />
            ))}
          </ol>
        )}

        {failed && (
          <p role="alert" className="text-sm text-destructive" data-testid="timeline-failed">
            The backend reported this investigation as failed. The history above is what it recorded
            before it stopped.
          </p>
        )}

        {terminal && !failed && (
          <p className="text-sm text-muted-foreground" data-testid="timeline-terminal">
            This investigation reached a terminal state; no further events will be recorded.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
