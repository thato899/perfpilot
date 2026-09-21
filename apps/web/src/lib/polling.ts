import type { InvestigationState, TestRunStatus } from "@perfpilot/schemas/types";

export const POLL_INTERVAL_MS = 1500;
export const MAX_CONSECUTIVE_POLL_ERRORS = 3;

export function isTerminalInvestigationStatus(status: InvestigationState["status"]): boolean {
  return status === "complete" || status === "failed";
}

export function isTerminalTestRunStatus(status: TestRunStatus): boolean {
  return status === "succeeded" || status === "failed" || status === "aborted_over_limit";
}

/**
 * How long a successful poll stays "current" before the timeline calls it
 * stale (issue #37).
 *
 * Deliberately a multiple of the poll interval rather than equal to it: one
 * slow response should not flip the UI into a warning state, but a stretch of
 * silence long enough that several polls should have landed is genuinely
 * something the user needs told about.
 */
export const STALE_AFTER_MS = POLL_INTERVAL_MS * 4;

export function isStale(lastUpdatedAt: number | null, now: number): boolean {
  if (lastUpdatedAt === null) return false;
  return now - lastUpdatedAt > STALE_AFTER_MS;
}
