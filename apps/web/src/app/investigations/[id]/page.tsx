"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type { InvestigationState, Report } from "@perfpilot/schemas/types";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { InvestigationProgress } from "@/components/dashboard/investigation-progress";
import { ReportView } from "@/components/dashboard/report-view";
import { advanceInvestigation, getInvestigation, getReport } from "@/lib/mock-api";
import { DEMO_TICKS } from "@/lib/fixtures";

// How often the mock investigation advances one tick. A real dashboard
// would poll GET /api/investigations/{id} (or use SSE/websockets) at a
// similar cadence — this constant is the one place that changes when this
// swaps to a real API.
const TICK_INTERVAL_MS = 1500;

export default function InvestigationPage() {
  const params = useParams<{ id: string }>();
  const investigationId = params.id;

  const [investigation, setInvestigation] = useState<InvestigationState | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getInvestigation(investigationId)
      .then((loaded) => {
        if (!cancelled) setInvestigation(loaded);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Failed to load investigation.");
      });
    return () => {
      cancelled = true;
    };
  }, [investigationId]);

  useEffect(() => {
    if (
      !investigation ||
      investigation.status === "complete" ||
      investigation.status === "failed"
    ) {
      return;
    }
    const timer = setInterval(async () => {
      const updated = await advanceInvestigation(investigationId);
      setInvestigation(updated);
      if (updated.status === "complete") {
        const finalReport = await getReport(investigationId);
        setReport(finalReport);
      }
    }, TICK_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [investigation, investigationId]);

  if (error) {
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
        <p className="text-sm text-muted-foreground">Loading investigation…</p>
      </main>
    );
  }

  // tickIndex isn't part of the public InvestigationState shape (it's a
  // mock-api-internal bookkeeping field on StoredInvestigation) — derive
  // the progress bar's VU count from the ticks table by status/order
  // instead of reaching into that internal field.
  const tickForCurrentVus = [...DEMO_TICKS]
    .reverse()
    .find((t) => t.status === investigation.status);
  const currentVus = investigation.status === "complete" ? 1000 : (tickForCurrentVus?.vus ?? 0);

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Investigation</h1>
        <Link href="/" className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>
          ← Back home
        </Link>
      </div>

      <InvestigationProgress investigation={investigation} currentVus={currentVus} />

      {report && <ReportView report={report} />}
    </main>
  );
}
