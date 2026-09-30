"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Activity, Plus } from "lucide-react";
import type { Project, Target } from "@perfpilot/schemas/types";

import { InvestigationForm } from "@/components/dashboard/investigation-form";
import { TargetForm } from "@/components/dashboard/target-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiRequestError, createProject, getProject } from "@/lib/api";

const PROJECT_ID_KEY = "perfpilot.projectId.v1";
const TARGET_CACHE_KEY = "perfpilot.targets.v1";

function loadCachedTargets(projectId: string): Target[] {
  try {
    const raw = window.localStorage.getItem(TARGET_CACHE_KEY);
    const targets = raw ? (JSON.parse(raw) as Target[]) : [];
    return targets.filter((target) => target.projectId === projectId);
  } catch {
    return [];
  }
}

function cacheTarget(target: Target): void {
  try {
    const raw = window.localStorage.getItem(TARGET_CACHE_KEY);
    const targets = raw ? (JSON.parse(raw) as Target[]) : [];
    const next = [...targets.filter((item) => item.id !== target.id), target];
    window.localStorage.setItem(TARGET_CACHE_KEY, JSON.stringify(next));
  } catch {
    // The API result remains authoritative even when browser storage is unavailable.
  }
}

async function loadOrCreateProject(): Promise<Project> {
  const configuredId = process.env.NEXT_PUBLIC_PERFPILOT_PROJECT_ID;
  const storedId = window.localStorage.getItem(PROJECT_ID_KEY);
  const projectId = configuredId || storedId;

  if (projectId) {
    try {
      return await getProject(projectId);
    } catch (error) {
      if (!(error instanceof ApiRequestError) || error.status !== 404) throw error;
    }
  }

  const project = await createProject({
    name: "PerfPilot demo project",
    description: "Created by the Phase 1 dashboard for the configured workspace.",
  });
  window.localStorage.setItem(PROJECT_ID_KEY, project.id);
  return project;
}

export default function Home() {
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addingTarget, setAddingTarget] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadOrCreateProject()
      .then((loadedProject) => {
        if (cancelled) return;
        const loadedTargets = loadCachedTargets(loadedProject.id);
        setProject(loadedProject);
        setTargets(loadedTargets);
        setSelectedTargetId(loadedTargets[0]?.id ?? null);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(
            reason instanceof Error ? reason.message : "Unable to connect to PerfPilot API.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleTargetCreated(target: Target) {
    cacheTarget(target);
    setTargets((prev) => [...prev.filter((item) => item.id !== target.id), target]);
    setSelectedTargetId(target.id);
    setAddingTarget(false);
  }

  const selectedTarget = targets.find((target) => target.id === selectedTargetId) ?? null;

  return (
    <main className="min-h-screen bg-background px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8">
        <header className="flex items-center justify-between border-b border-border/70 pb-5">
          <Link
            href="/"
            className="flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
              <Activity aria-hidden="true" className="size-5" />
            </span>
            <span className="flex flex-col">
              <span className="text-sm font-semibold tracking-tight">PerfPilot</span>
              <span className="text-xs text-muted-foreground">Performance workspace</span>
            </span>
          </Link>
          <span className="hidden items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground sm:inline-flex">
            <span className="size-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
            Local workspace
          </span>
        </header>

        <section className="flex flex-col gap-2">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">Overview</p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Your performance workspace
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
            Choose an authorized application, run an investigation, and review its measured results.
          </p>
        </section>

        {loading ? (
          <Card aria-label="Loading workspace">
            <CardContent className="flex items-center gap-3 py-6">
              <span
                className="size-4 animate-spin rounded-full border-2 border-primary border-r-transparent"
                aria-hidden="true"
              />
              <p role="status" className="text-sm text-muted-foreground">
                Loading your workspace...
              </p>
            </CardContent>
          </Card>
        ) : error ? (
          <Card className="border-destructive/30">
            <CardHeader>
              <CardTitle>Couldn&apos;t connect to PerfPilot</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <p className="text-sm text-muted-foreground">{error}</p>
              <Button
                variant="secondary"
                onClick={() => window.location.reload()}
                className="w-fit"
              >
                Try again
              </Button>
            </CardContent>
          </Card>
        ) : !project ? (
          <p className="text-sm text-destructive">Project setup did not complete.</p>
        ) : (
          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <div className="flex flex-col gap-6">
              {targets.length === 0 || addingTarget ? (
                <TargetForm
                  projectId={project.id}
                  onCreated={handleTargetCreated}
                  onCancel={targets.length > 0 ? () => setAddingTarget(false) : undefined}
                />
              ) : (
                <Card>
                  <CardHeader className="flex flex-row items-start justify-between gap-4">
                    <div>
                      <CardTitle>Your targets</CardTitle>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Select the application to investigate.
                      </p>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => setAddingTarget(true)}>
                      <Plus aria-hidden="true" /> Add target
                    </Button>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2">
                    {targets.map((target) => {
                      const selected = target.id === selectedTargetId;
                      return (
                        <button
                          key={target.id}
                          type="button"
                          aria-pressed={selected}
                          onClick={() => setSelectedTargetId(target.id)}
                          className={`group rounded-xl border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                            selected
                              ? "border-primary/60 bg-accent/70"
                              : "bg-card hover:bg-muted/70"
                          }`}
                        >
                          <span className="flex items-start justify-between gap-3">
                            <span className="min-w-0">
                              <span className="block truncate text-sm font-semibold">
                                {target.name}
                              </span>
                              <span className="mt-1 block truncate text-sm text-muted-foreground">
                                {target.baseUrl}
                              </span>
                            </span>
                            <span
                              className={`mt-1 size-2.5 shrink-0 rounded-full ${
                                selected ? "bg-primary" : "border border-muted-foreground/50"
                              }`}
                              aria-hidden="true"
                            />
                          </span>
                        </button>
                      );
                    })}
                  </CardContent>
                </Card>
              )}

              <div className="rounded-xl border border-dashed bg-card/70 p-4 text-sm text-muted-foreground">
                <p className="font-medium text-foreground">Before you run a test</p>
                <p className="mt-1 leading-relaxed">
                  Only test systems you own or have explicit permission to assess. Start with a low,
                  controlled load.
                </p>
              </div>
            </div>

            {selectedTarget && !addingTarget && (
              <InvestigationForm
                target={selectedTarget}
                onCreated={(investigation) =>
                  router.push(`/investigations/${investigation.investigationId}`)
                }
              />
            )}
          </div>
        )}
      </div>
    </main>
  );
}
