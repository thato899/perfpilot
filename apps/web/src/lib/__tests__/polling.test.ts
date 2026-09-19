import { describe, expect, it } from "vitest";

import {
  isTerminalInvestigationStatus,
  isTerminalTestRunStatus,
  MAX_CONSECUTIVE_POLL_ERRORS,
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
