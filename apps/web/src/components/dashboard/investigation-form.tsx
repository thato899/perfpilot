"use client";

import { useState } from "react";
import type { InvestigationObjective, InvestigationState, Target } from "@perfpilot/schemas/types";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiRequestError, createInvestigation } from "@/lib/api";

export function investigationErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError && error.code === "vus_over_limit") {
    const requested = error.detail.requested_vus;
    const maximum = error.detail.max_virtual_users;
    if (typeof requested === "number" && typeof maximum === "number") {
      return `Requested ${requested} simulated users; this instance permits at most ${maximum}. For an approved larger test, update MAX_VIRTUAL_USERS in .env and restart PerfPilot.`;
    }
  }
  if (error instanceof ApiRequestError && error.code === "duration_over_limit") {
    const requested = error.detail.requested_seconds;
    const maximum = error.detail.max_test_duration_seconds;
    if (typeof requested === "number" && typeof maximum === "number") {
      return `The planned run needs ${requested} seconds; this instance permits at most ${maximum}. For an approved longer test, update MAX_TEST_DURATION_SECONDS in .env and restart PerfPilot.`;
    }
  }
  return error instanceof Error ? error.message : "Failed to start investigation.";
}

const OBJECTIVES: { value: InvestigationObjective; label: string }[] = [
  { value: "determine_capacity", label: "Determine capacity — “what can this handle?”" },
  { value: "diagnose_regression", label: "Diagnose regression — “why did this get slower?”" },
  { value: "validate_fix", label: "Validate fix — “did the optimization work?”" },
  { value: "baseline", label: "Baseline — record current performance" },
];

/** "Trigger an investigation" — POST /api/investigations
 * (docs/api/api-contract.md). Kicks off UNDERSTAND -> PLAN per
 * docs/architecture/data-flow.md; the resulting page watches it progress. */
export function InvestigationForm({
  target,
  onCreated,
}: {
  target: Target;
  onCreated: (investigation: InvestigationState) => void;
}) {
  const [objective, setObjective] = useState<InvestigationObjective>("baseline");
  const [normalUsers, setNormalUsers] = useState("1");
  const [peakUsers, setPeakUsers] = useState("1");
  const [peakDescription, setPeakDescription] = useState("");
  const [requestPath, setRequestPath] = useState("/");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const path = requestPath.trim();
    if (!/^\/(?!\/)[^\s?#]*$/.test(path)) {
      setError("Enter a path beginning with /, without a query, fragment, or spaces.");
      return;
    }
    setSubmitting(true);
    try {
      const investigation = await createInvestigation({
        targetId: target.id,
        objective,
        userJourneys: [path],
        expectedTraffic: {
          normalConcurrentUsers: Number(normalUsers),
          peakConcurrentUsers: Number(peakUsers),
          peakDescription: peakDescription || undefined,
        },
      });
      onCreated(investigation);
    } catch (err) {
      setError(investigationErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Start an investigation</CardTitle>
        <CardDescription>
          Against <span className="font-medium">{target.name}</span> ({target.baseUrl}).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="objective">Objective</Label>
            <Select
              value={objective}
              onValueChange={(v) => setObjective(v as InvestigationObjective)}
            >
              <SelectTrigger id="objective" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {OBJECTIVES.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="request-path">Request path</Label>
            <Input
              id="request-path"
              value={requestPath}
              onChange={(e) => setRequestPath(e.target.value)}
              placeholder="/login.php"
              required
            />
            <p className="text-xs leading-relaxed text-muted-foreground">
              Each simulated user repeats an unauthenticated GET to this path. Use a safe, read-only
              page; /login.php tests the public login page, not a signed-in session.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="normal-users">Normal concurrent users</Label>
              <Input
                id="normal-users"
                type="number"
                min={1}
                value={normalUsers}
                onChange={(e) => setNormalUsers(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="peak-users">Peak concurrent users</Label>
              <Input
                id="peak-users"
                type="number"
                min={1}
                value={peakUsers}
                onChange={(e) => setPeakUsers(e.target.value)}
                required
              />
            </div>
          </div>
          <p className="-mt-2 text-xs leading-relaxed text-muted-foreground">
            These describe expected traffic. The server may apply a lower safety cap; the results
            show the concurrency actually tested.
          </p>
          <div className="flex flex-col gap-2">
            <Label htmlFor="peak-description">Peak description (optional)</Label>
            <Input
              id="peak-description"
              value={peakDescription}
              onChange={(e) => setPeakDescription(e.target.value)}
              placeholder="Product launch, registration window..."
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" disabled={submitting}>
            {submitting ? "Starting…" : "Start investigation"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
