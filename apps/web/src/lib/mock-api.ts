/**
 * Mock API client — every function here mirrors one docs/api/api-contract.md
 * operation (same name, same shape, same async signature a real `fetch()`
 * call would have) but is backed by localStorage + the fixtures in
 * lib/fixtures.ts instead of a network call, since apps/api doesn't exist
 * yet (see docs/development/next-steps.md: "build the dashboard against a
 * mocked API ... don't wait on a real investigation ever having run").
 *
 * This is the single seam: once apps/api exists, swapping these function
 * bodies for real `fetch("/api/...")` calls should not require touching any
 * component that imports from here — same pattern as the
 * `# BLOCKED-ON: #1` seam in agents/reporting/report_builder.py.
 *
 * "use client" because localStorage only exists in the browser — every
 * caller of this module must be a client component.
 */
"use client";

import type {
  ExpectedTraffic,
  InvestigationObjective,
  InvestigationState,
  Report,
  Target,
} from "@perfpilot/schemas/types";

import {
  DEMO_FINDING,
  DEMO_HYPOTHESIS,
  DEMO_TARGET,
  DEMO_TICKS,
  buildDemoReport,
} from "./fixtures";

const STORAGE_KEY = "perfpilot.mockDb.v1";

interface StoredInvestigation extends InvestigationState {
  tickIndex: number; // -1 = not yet started (planning), else index into DEMO_TICKS
}

interface MockDb {
  targets: Target[];
  investigations: Record<string, StoredInvestigation>;
  reports: Record<string, Report>;
}

function emptyDb(): MockDb {
  return { targets: [], investigations: {}, reports: {} };
}

function loadDb(): MockDb {
  if (typeof window === "undefined") return emptyDb();
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return emptyDb();
  try {
    return JSON.parse(raw) as MockDb;
  } catch {
    // Malformed/stale localStorage content shouldn't crash the app — start fresh.
    return emptyDb();
  }
}

function saveDb(db: MockDb): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(db));
}

function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

// Simulated network latency — small and constant, just enough that the UI's
// loading states are exercised the same way they will be against a real API.
const LATENCY_MS = 250;
function delay(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, LATENCY_MS));
}

// ---------------------------------------------------------------------------
// Targets — mirrors POST /api/projects/{id}/targets, GET-equivalent listing
// ---------------------------------------------------------------------------

export async function listTargets(): Promise<Target[]> {
  await delay();
  const db = loadDb();
  return db.targets;
}

export interface CreateTargetInput {
  name: string;
  baseUrl: string;
  authorizationConfirmed: boolean;
  authorizationConfirmedBy: string;
}

export async function createTarget(input: CreateTargetInput): Promise<Target> {
  await delay();
  // Mirrors the API's real rejection per api-contract.md: no "confirm
  // later" state — creation is refused outright without confirmation.
  if (!input.authorizationConfirmed) {
    throw new Error(
      "authorizationConfirmed must be true — PerfPilot never creates an unconfirmed target.",
    );
  }
  const db = loadDb();
  const target: Target = {
    id: uid("tgt"),
    projectId: DEMO_TARGET.projectId,
    baseUrl: input.baseUrl,
    name: input.name,
    authorizationConfirmed: true,
    authorizationConfirmedBy: input.authorizationConfirmedBy,
    authorizationConfirmedAt: new Date().toISOString(),
  };
  db.targets.push(target);
  saveDb(db);
  return target;
}

// ---------------------------------------------------------------------------
// Investigations — mirrors POST /api/investigations, GET /api/investigations/{id}
// ---------------------------------------------------------------------------

export interface CreateInvestigationInput {
  targetId: string;
  objective: InvestigationObjective;
  expectedTraffic: ExpectedTraffic;
}

export async function createInvestigation(
  input: CreateInvestigationInput,
): Promise<InvestigationState> {
  await delay();
  const db = loadDb();
  const id = uid("inv");
  const state: StoredInvestigation = {
    investigationId: id,
    targetId: input.targetId,
    status: "planning",
    observations: [],
    findings: [],
    hypotheses: [],
    experiments: [],
    decisions: [
      {
        step: "create",
        decision:
          `Investigation created — objective: ${input.objective}, peak traffic: ` +
          `${input.expectedTraffic.peakConcurrentUsers} concurrent users.`,
        madeBy: "orchestrator",
      },
    ],
    tickIndex: -1,
  };
  db.investigations[id] = state;
  saveDb(db);
  return state;
}

export async function getInvestigation(id: string): Promise<InvestigationState> {
  await delay();
  const db = loadDb();
  const investigation = db.investigations[id];
  if (!investigation) throw new Error(`investigation ${id} not found`);
  return investigation;
}

/** Advances the mock investigation by one tick (see fixtures.ts's
 * DEMO_TICKS) — mirrors what a real Celery worker's completion callback +
 * `POST /api/investigations/{id}/continue` would do over time, compressed
 * into something a page can drive with a plain interval for the demo. */
export async function advanceInvestigation(id: string): Promise<InvestigationState> {
  await delay();
  const db = loadDb();
  const investigation = db.investigations[id];
  if (!investigation) throw new Error(`investigation ${id} not found`);

  const nextTickIndex = investigation.tickIndex + 1;
  if (nextTickIndex >= DEMO_TICKS.length) {
    return investigation; // already fully advanced
  }
  const tick = DEMO_TICKS[nextTickIndex];

  investigation.tickIndex = nextTickIndex;
  investigation.status = tick.status;
  investigation.currentTestRunId ??= uid("run");
  investigation.decisions.push({
    step: `tick-${nextTickIndex}`,
    decision: tick.label,
    madeBy: "orchestrator",
  });

  // At the anomaly stage, the Investigator's finding/hypothesis appear —
  // mirrors docs/demo-scenario.md's narrative.
  if (tick.status === "investigating" && investigation.findings.length === 0) {
    investigation.findings = [DEMO_FINDING];
    investigation.hypotheses = [{ ...DEMO_HYPOTHESIS, status: "testing", confidence: 0.6 }];
  }
  // After the follow-up experiment, the hypothesis is confirmed at higher confidence.
  if (tick.status === "reporting") {
    investigation.hypotheses = [DEMO_HYPOTHESIS]; // status: "supported", confidence: 0.87
    investigation.status = "complete";
    db.reports[id] = buildDemoReport(id);
  }

  db.investigations[id] = investigation;
  saveDb(db);
  return investigation;
}

// ---------------------------------------------------------------------------
// Reports — mirrors GET /api/reports/{id}
// ---------------------------------------------------------------------------

export async function getReport(investigationId: string): Promise<Report | null> {
  await delay();
  const db = loadDb();
  return db.reports[investigationId] ?? null;
}

// ---------------------------------------------------------------------------
// Demo seed — lets the UI offer "use the demo target" instead of forcing a
// first-time visitor to type in a URL before they can see anything work.
// ---------------------------------------------------------------------------

export async function ensureDemoTargetSeeded(): Promise<Target> {
  await delay();
  const db = loadDb();
  const existing = db.targets.find((t) => t.id === DEMO_TARGET.id);
  if (existing) return existing;
  db.targets.push(DEMO_TARGET);
  saveDb(db);
  return DEMO_TARGET;
}
