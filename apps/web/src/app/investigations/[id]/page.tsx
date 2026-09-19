"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { InvestigationState, Report, TestRun } from "@perfpilot/schemas/types";

import { InvestigationProgress } from "@/components/dashboard/investigation-progress";
import { ReportView } from "@/components/dashboard/report-view";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiRequestError, getInvestigation, getReport, getTestRun } from "@/lib/api";
import {
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
          if (consecutiveErrors < MAX_CONSECUTIVE_POLL_ERRORS) schedule();
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

  if (error && !investigation) {
    return (
      <main className="mx-auto flex max-w-3xl flex-col gap-4 p-8">
        <p className="text-sm text-destructive">{error}</p>
        <Link href="/" className={cn(buttonVariants({ variant: "secondary" }), "w-fit")}>
          Back home
        </Link>
      </main>
    );
  }

  if (!investigation) {
    return (
      <main className="mx-auto flex max-w-3xl p-8">
        <p className="text-sm text-muted-foreground">Loading investigationâ€¦</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Investigation</h1>
        <Link href="/" className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>
          â† Back home
        </Link>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      <InvestigationProgress investigation={investigation} testRun={testRun} />
      {reportError && <p className="text-sm text-destructive">{reportError}</p>}
      {report && <ReportView report={report} />}

      {investigation.status === "planning" && !investigation.currentTestRunId && (
        <Card>
          <CardHeader>
            <CardTitle>Waiting for backend execution</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            This page is reading persisted API state. The current backend contract does not yet
            expose the initial plan/run link or a worker continuation trigger, so the UI will not
            simulate progress or show a fabricated report.
          </CardContent>
        </Card>
      )}
    </main>
  );
}
