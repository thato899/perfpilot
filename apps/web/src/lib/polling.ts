import type { InvestigationState, TestRunStatus } from "@perfpilot/schemas/types";

export const POLL_INTERVAL_MS = 1500;
export const MAX_CONSECUTIVE_POLL_ERRORS = 3;

export function isTerminalInvestigationStatus(status: InvestigationState["status"]): boolean {
  return status === "complete" || status === "failed";
}

export function isTerminalTestRunStatus(status: TestRunStatus): boolean {
  return status === "succeeded" || status === "failed" || status === "aborted_over_limit";
}
