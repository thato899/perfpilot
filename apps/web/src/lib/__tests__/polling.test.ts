import { describe, expect, it } from "vitest";

import {
  isStale,
  isTerminalInvestigationStatus,
  isTerminalTestRunStatus,
  MAX_CONSECUTIVE_POLL_ERRORS,
  POLL_INTERVAL_MS,
  STALE_AFTER_MS,
} from "../polling";

describe("safe polling boundaries", () => {
  it("stops at complete and failed investigation states", () => {
    expect(isTerminalInvestigationStatus("complete")).toBe(true);
    expect(isTerminalInvestigationStatus("failed")).toBe(true);
    expect(isTerminalInvestigationStatus("investigating")).toBe(false);
  });

  it("stops at successful, failed, and safety-aborted test runs", () => {
    expect(isTerminalTestRunStatus("succeeded")).toBe(true);
    expect(isTerminalTestRunStatus("failed")).toBe(true);
    expect(isTerminalTestRunStatus("aborted_over_limit")).toBe(true);
    expect(isTerminalTestRunStatus("running")).toBe(false);
  });

  it("bounds consecutive polling errors", () => {
    expect(MAX_CONSECUTIVE_POLL_ERRORS).toBe(3);
  });
});

describe("staleness window", () => {
  it("allows several poll intervals before calling the view stale", () => {
    // One slow response should not flip the UI into a warning state.
    expect(STALE_AFTER_MS).toBeGreaterThan(POLL_INTERVAL_MS);
  });

  it("is not stale before the window elapses", () => {
    expect(isStale(1_000, 1_000 + STALE_AFTER_MS)).toBe(false);
  });

  it("is stale once the window elapses", () => {
    expect(isStale(1_000, 1_000 + STALE_AFTER_MS + 1)).toBe(true);
  });

  it("is never stale before the first successful poll", () => {
    // Nothing has been received yet, so there is no old state to warn about
    // — that is the loading state, not the stale state.
    expect(isStale(null, Date.now())).toBe(false);
  });
});
