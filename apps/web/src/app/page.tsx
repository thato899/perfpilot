"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Target } from "@perfpilot/schemas/types";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InvestigationForm } from "@/components/dashboard/investigation-form";
import { TargetForm } from "@/components/dashboard/target-form";
import { ensureDemoTargetSeeded, listTargets } from "@/lib/mock-api";

export default function Home() {
  const router = useRouter();
  const [targets, setTargets] = useState<Target[]>([]);
  const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listTargets().then((loaded) => {
      setTargets(loaded);
      setSelectedTargetId(loaded[0]?.id ?? null);
      setLoading(false);
    });
  }, []);

  async function handleUseDemoTarget() {
    const target = await ensureDemoTargetSeeded();
    setTargets((prev) => (prev.some((t) => t.id === target.id) ? prev : [...prev, target]));
    setSelectedTargetId(target.id);
  }

  const selectedTarget = targets.find((t) => t.id === selectedTargetId) ?? null;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 p-8">
      <div>
        <h1 className="text-2xl font-semibold">PerfPilot</h1>
        <p className="text-sm text-muted-foreground">
          Create a target, trigger an investigation, and watch it run. Backed by a mocked API (see{" "}
          <code>src/lib/mock-api.ts</code>) until <code>apps/api</code> exists — see{" "}
          <a
            className="underline"
            href="https://github.com/thato899/perfpilot/blob/main/docs/demo-scenario.md"
          >
            docs/demo-scenario.md
          </a>{" "}
          for the reference walkthrough this mock replays.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : targets.length === 0 ? (
        <div className="flex flex-col gap-4">
          <TargetForm onCreated={(t) => setTargets([t])} />
          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs text-muted-foreground">or</span>
            <div className="h-px flex-1 bg-border" />
          </div>
          <Button variant="secondary" onClick={handleUseDemoTarget}>
            Use the demo target ({"“"}Demo e-commerce app{"”"})
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Targets</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {targets.map((target) => (
                <button
                  key={target.id}
                  onClick={() => setSelectedTargetId(target.id)}
                  className={`rounded-md border p-3 text-left text-sm transition-colors ${
                    target.id === selectedTargetId
                      ? "border-primary bg-accent"
                      : "hover:bg-accent/50"
                  }`}
                >
                  <div className="font-medium">{target.name}</div>
                  <div className="text-muted-foreground">{target.baseUrl}</div>
                </button>
              ))}
            </CardContent>
          </Card>

          {selectedTarget && (
            <InvestigationForm
              target={selectedTarget}
              onCreated={(investigation) =>
                router.push(`/investigations/${investigation.investigationId}`)
              }
            />
          )}
        </div>
      )}
    </main>
  );
}
