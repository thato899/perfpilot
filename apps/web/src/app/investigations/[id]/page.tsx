"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { InvestigationState, Report, TestRun } from "@perfpilot/schemas/types";

import { InvestigationProgress } from "@/components/dashboard/investigation-progress";
import { InvestigationTimeline } from "@/components/dashboard/investigation-timeline";
import { FindingsPanel } from "@/components/dashboard/findings-panel";
import { ReportView } from "@/components/dashboard/report-view";
import { buttonVariants } from "@/components/ui/button";
import { ApiRequestError, getInvestigation, getReport, getTestRun } from "@/lib/api";
import {
  isStale,
  isTerminalInvestigationStatus,
  MAX_CONSECUTIVE_POLL_ERRORS,
  POLL_INTERVAL_MS,
} from "@/lib/polling";
import { cn } from "@/lib/utils";

export default function InvestigationPage() {
  const params = useParams<{ id: string }>();
  const investigationId = params.id;
  const [investigation, setInvestigation] = useState<InvestigationState | null>(null);
  const [testRun, setTestRun] = useState<TestRun | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  // Timestamp of the last poll that actually returned state, so the timeline
  // can distinguish "this is live" from "this is the last thing we heard".
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  // A retry is in flight after at least one failure. Separate from `error`:
  // the user should be told we are still trying, not just that it broke.
  const [reconnecting, setReconnecting] = useState(false);
  // A clock in state, ticked by an interval, so staleness can be *derived*
  // during render from two pieces of state rather than computed by calling
  // Date.now() in the render body.
  //
  // Calling Date.now() while rendering is impure, and it would also only be
  // re-evaluated when React re-renders — which here happens when a poll
  // succeeds. The screen would never be marked stale at the one moment it
  // matters: when polling has given up entirely and nothing re-renders at all.
  const [now, setNow] = useState<number | null>(null);

  // A terminal investigation is finished, not out of date. Polling stops at
  // complete/failed by design, so a clock that kept running would eventually
  // put "It may be out of date" on a final result that is not going to change
  // — directly contradicting the timeline's own "no further events will be
  // recorded" notice. Staleness means "an update was expected and did not
  // arrive", which is only meaningful while updates are still expected.
  const expectingUpdates =
    investigation === null || !isTerminalInvestigationStatus(investigation.status);

  useEffect(() => {
    if (!expectingUpdates) return;
    const tick = setInterval(() => setNow(Date.now()), POLL_INTERVAL_MS);
    return () => clearInterval(tick);
  }, [expectingUpdates]);

  // Recomputes to false the moment a poll lands, because lastUpdatedAt moves.
  const stale = expectingUpdates && now !== null && isStale(lastUpdatedAt, now);

  useEffect(() => {
    let cancelled = false;
    let inFlight = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let consecutiveErrors = 0;

    const schedule = () => {
      if (!cancelled) timer = setTimeout(poll, POLL_INTERVAL_MS);
    };

    const poll = async () => {
      if (cancelled || inFlight) return;
      inFlight = true;
      try {
        const next = await getInvestigation(investigationId);
        if (cancelled) return;
        setInvestigation(next);
        setError(null);
        setLastUpdatedAt(Date.now());
        setReconnecting(false);
        consecutiveErrors = 0;

        let nextRun: TestRun | null = null;
        if (next.currentTestRunId) {
          nextRun = await getTestRun(next.currentTestRunId);
          if (!cancelled) setTestRun(nextRun);
        } else if (!cancelled) {
          setTestRun(null);
        }

        const investigationDone = isTerminalInvestigationStatus(next.status);
        const runFailed = nextRun?.status === "failed" || nextRun?.status === "aborted_over_limit";
        if (next.status === "failed" || nextRun?.status === "failed") {
          setError("The backend reported an investigation or test-run failure.");
        } else if (nextRun?.status === "aborted_over_limit") {
          setError("The test run was aborted by a configured safety limit.");
        }

        if (next.status === "complete") {
          try {
            const finalReport = await getReport(investigationId);
            if (!cancelled) {
              setReport(finalReport);
              setReportError(null);
            }
          } catch (reason) {
            if (!cancelled) {
              setReportError(
                reason instanceof ApiRequestError && reason.status === 404
                  ? "The investigation is complete, but its persisted report is unavailable."
                  : reason instanceof Error
                    ? reason.message
                    : "The persisted report could not be loaded.",
              );
            }
          }
        }

        if (!investigationDone && !runFailed) schedule();
      } catch (reason) {
        consecutiveErrors += 1;
        if (!cancelled) {
          setError(
            consecutiveErrors >= MAX_CONSECUTIVE_POLL_ERRORS
              ? "The investigation API is unavailable."
              : reason instanceof Error
                ? reason.message
                : "The investigation API is unavailable.",
          );
          const willRetry = consecutiveErrors < MAX_CONSECUTIVE_POLL_ERRORS;
          setReconnecting(willRetry);
          if (willRetry) schedule();
        }
      } finally {
        inFlight = false;
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [investigationId]);

  // No early return while `investigation` is null.
  //
  // The timeline component implements the loading, first-failure and
  // reconnecting states together with their aria roles, and returning a bare
  // paragraph here meant the page never rendered any of them: the documented
  // accessibility behaviour existed only in the component's own tests. The
  // page now always renders the timeline and lets it own those states.
  //
  // The cards that require a loaded investigation stay conditional, because
  // they have no meaningful empty rendering — that is a different thing from
  // suppressing the timeline.
  const loading = investigation === null && error === null;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Investigation</h1>
        <Link href="/" className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>
          ← Back home
        </Link>
      </div>

      {investigation && <InvestigationProgress investigation={investigation} testRun={testRun} />}

      {/* The polling/run error is presented once, by the timeline card, which
          gives it role="alert" next to the history it applies to. Rendering it
          on the page as well produced two identical alerts, which a screen
          reader announces twice. */}
      <InvestigationTimeline
        investigation={investigation}
        loading={loading}
        error={error}
        stale={stale}
        lastUpdatedAt={lastUpdatedAt}
        reconnecting={reconnecting}
      />

      {investigation && <FindingsPanel investigation={investigation} />}
      {reportError && <p className="text-sm text-destructive">{reportError}</p>}
      {report && <ReportView report={report} />}
    </main>
  );
}
