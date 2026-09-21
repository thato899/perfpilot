"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
  }

  const selectedTarget = targets.find((target) => target.id === selectedTargetId) ?? null;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 p-8">
      <div>
        <h1 className="text-2xl font-semibold">PerfPilot</h1>
        <p className="text-sm text-muted-foreground">
          Create an authorized target, start an investigation, and watch the persisted FastAPI
          state.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : error ? (
        <Card>
          <CardHeader>
            <CardTitle>API unavailable</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="text-sm text-destructive">{error}</p>
            <Button variant="secondary" onClick={() => window.location.reload()} className="w-fit">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : !project ? (
        <p className="text-sm text-destructive">Project setup did not complete.</p>
      ) : targets.length === 0 ? (
        <TargetForm projectId={project.id} onCreated={handleTargetCreated} />
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
