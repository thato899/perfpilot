/**
 * Contract tests — issue #37 against issue #35's real output.
 *
 * The two fixtures in ./fixtures were not written by hand. They are the
 * verbatim body of `GET /api/investigations/{id}` captured from a running
 * apps/api (real Postgres, real Redis, a real Celery worker) after driving an
 * investigation to a terminal state on 2026-09-21, against `main` at commit
 * 9c3c7e1. Regenerating them means running that flow again, not editing them.
 *
 * The point of pinning real output rather than hand-written fixtures: a
 * hand-written fixture only ever proves the mapper agrees with my own reading
 * of the contract doc. These prove it agrees with what the server actually
 * sends — field names, timestamp format, sequence numbering and all.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { InvestigationState } from "@perfpilot/schemas/types";

import completed from "./fixtures/real-investigation-complete.json";
import failed from "./fixtures/real-investigation-failed.json";
import { getInvestigation } from "../api";
import { currentAction, hasSequenceGap, toTimeline } from "../investigation-events";

afterEach(() => {
  vi.unstubAllGlobals();
});

/**
 * Run a captured response through the real client rather than through an
 * exported internal, so the wire mapper in api.ts is exercised too — that is
 * the layer a server-side rename would break first.
 */
async function load(fixture: unknown): Promise<InvestigationState> {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(fixture), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    ),
  );
  return getInvestigation("irrelevant-for-this-test");
}

describe("real completed investigation", () => {
  let state: InvestigationState;

  beforeEach(async () => {
    state = await load(completed);
  });

  it("maps every event the server recorded", () => {
    const entries = toTimeline(state.events);
    expect(entries).toHaveLength(6);
    expect(entries.every((entry) => entry.known)).toBe(true);
  });

  it("preserves the server's ordering, which is not the intuitive one", () => {
    // The server records `finding_recorded` (4) *before* `test_run_completed`
    // (5). Reading the lifecycle prose you would expect the opposite. This is
    // exactly why the UI orders on `sequence` instead of reasoning about what
    // "should" come next.
    const entries = toTimeline(state.events);
    expect(entries.map((entry) => entry.type)).toEqual([
      "investigation_created",
      "test_run_queued",
      "test_run_started",
      "finding_recorded",
      "test_run_completed",
      "report_persisted",
    ]);
  });

  it("finds no gap in a complete history", () => {
    expect(hasSequenceGap(toTimeline(state.events))).toBe(false);
  });

  it("reads the real payload field names", () => {
    const entries = toTimeline(state.events);
    const created = entries[0];
    expect(created.detail).toBe("Objective: determine capacity");
    expect(created.relatedIds).toContainEqual({
      label: "Target",
      value: expect.stringMatching(/^[0-9a-f-]{36}$/) as unknown as string,
    });

    const queued = entries[1];
    expect(queued.detail).toBe("Queued as the baseline run");

    const completedRun = entries[4];
    expect(completedRun.detail).toBe("Reported succeeded");
  });

  it("parses the server's timestamp format", () => {
    // The API serialises as "...Z" with microseconds. Date must accept it, or
    // every row would fall back to the raw string.
    for (const entry of toTimeline(state.events)) {
      expect(Number.isNaN(new Date(entry.occurredAt).getTime())).toBe(false);
    }
  });

  it("carries the server's idempotency keys through", () => {
    const entries = toTimeline(state.events);
    expect(entries[0].idempotencyKey).toMatch(/^investigation-created:/);
  });

  it("reports the real experiment budget", () => {
    expect(state.experimentBudget).toEqual({
      maxExperiments: 3,
      consumed: 0,
      remaining: 3,
      exhausted: false,
    });
  });

  it("describes the terminal status", () => {
    expect(state.status).toBe("complete");
    expect(currentAction(state.status)).toBe("Complete");
  });
});

describe("real failed investigation", () => {
  let state: InvestigationState;

  beforeEach(async () => {
    state = await load(failed);
  });

  it("stops at the last event the server actually recorded", () => {
    const entries = toTimeline(state.events);
    expect(entries.map((entry) => entry.type)).toEqual([
      "investigation_created",
      "test_run_queued",
      "test_run_started",
    ]);
  });

  it("does not invent a completion event for a failed run", () => {
    // Worth stating explicitly, because it is a real property of #35's
    // implementation: apps/api/tasks.py appends `test_run_completed` only on
    // the success path, so a failed run leaves the history ending at
    // `test_run_started`. The failure is visible through the investigation's
    // status, and the UI must not paper over the missing event by
    // synthesising one.
    const entries = toTimeline(state.events);
    expect(entries.map((entry) => entry.type)).not.toContain("test_run_completed");
    expect(state.status).toBe("failed");
    expect(currentAction(state.status)).toBe("Failed");
  });

  it("does not report a gap just because the history is short", () => {
    // A truncated-by-failure history is still 1..n with no holes. Flagging it
    // as incomplete would cry wolf on every failed investigation.
    expect(hasSequenceGap(toTimeline(state.events))).toBe(false);
  });
});
