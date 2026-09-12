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
import { createInvestigation } from "@/lib/mock-api";

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
  const [objective, setObjective] = useState<InvestigationObjective>("determine_capacity");
  const [normalUsers, setNormalUsers] = useState("100");
  const [peakUsers, setPeakUsers] = useState("1000");
  const [peakDescription, setPeakDescription] = useState("Flash sale");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const investigation = await createInvestigation({
        targetId: target.id,
        objective,
        expectedTraffic: {
          normalConcurrentUsers: Number(normalUsers),
          peakConcurrentUsers: Number(peakUsers),
          peakDescription: peakDescription || undefined,
        },
      });
      onCreated(investigation);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start investigation.");
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
          <div className="flex flex-col gap-2">
            <Label htmlFor="peak-description">Peak description (optional)</Label>
            <Input
              id="peak-description"
              value={peakDescription}
              onChange={(e) => setPeakDescription(e.target.value)}
              placeholder="Flash sale, product launch, ..."
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={submitting}>
            {submitting ? "Starting…" : "Start investigation"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
