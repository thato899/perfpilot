/**
 * Page-level regression tests for issue #37's required UI states.
 *
 * These exist because the component tests were not enough. The timeline
 * component implemented and tested loading, first-failure and reconnecting
 * states, but the page returned early while `investigation` was null, so none
 * of them ever reached the browser — the documented accessibility behaviour
 * was real only in isolation. Everything here drives the actual page.
 */

import type { InvestigationState, TestRun } from "@perfpilot/schemas/types";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getInvestigation: vi.fn(),
  getReport: vi.fn(),
  getTestRun: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getInvestigation: api.getInvestigation,
    getReport: api.getReport,
    getTestRun: api.getTestRun,
  };
});

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "inv-1" }),
}));

import { STALE_AFTER_MS } from "@/lib/polling";

import InvestigationPage from "./page";

function investigation(
  status: InvestigationState["status"],
  overrides: Partial<InvestigationState> = {},
): InvestigationState {
  return {
    investigationId: "inv-1",
    targetId: "target-1",
    status,
    currentTestRunId: "run-1",
    observations: [],
    findings: [],
    hypotheses: [],
    experiments: [],
    decisions: [],
    experimentBudget: { maxExperiments: 3, consumed: 0, remaining: 3, exhausted: false },
    events: [
      {
        id: "event-1",
        sequence: 1,
        type: "investigation_created",
        payload: { objective: "determine_capacity" },
        occurredAt: "2026-09-21T08:00:00Z",
      },
    ],
    ...overrides,
  };
}

const run: TestRun = {
  id: "run-1",
  testPlanId: "plan-1",
  targetId: "target-1",
  status: "running",
  progress: { currentVus: 0, targetVus: 1 },
};

/** Never settles, so the page stays in its first-load state. */
function pending<T>(): Promise<T> {
  return new Promise<T>(() => {});
}

beforeEach(() => {
  api.getInvestigation.mockReset();
  api.getReport.mockReset();
  api.getTestRun.mockReset();
  api.getTestRun.mockResolvedValue(run);
  api.getReport.mockRejectedValue(new Error("no report"));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("first load", () => {
  it("announces loading with role=status while the first request is in flight", async () => {
    api.getInvestigation.mockReturnValue(pending<InvestigationState>());

    render(<InvestigationPage />);

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/Loading the investigation timeline/),
    );
  });

  it("does not render the timeline list before any data has arrived", async () => {
    api.getInvestigation.mockReturnValue(pending<InvestigationState>());

    render(<InvestigationPage />);

    await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
    expect(screen.queryByTestId("timeline-list")).not.toBeInTheDocument();
  });
});

describe("first request fails", () => {
  it("shows a role=alert and a reconnect notice while retries remain", async () => {
    // One failure, then a hang: the page has retried and is waiting, which is
    // exactly the state the user needs told about.
    api.getInvestigation
      .mockRejectedValueOnce(new Error("network down"))
      .mockReturnValue(pending<InvestigationState>());

    render(<InvestigationPage />);

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("network down"));
    expect(screen.getByTestId("timeline-reconnecting")).toHaveTextContent(/Reconnecting/);
  });

  it("recovers to real content once a retry succeeds", async () => {
    api.getInvestigation
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValue(investigation("running"));

    render(<InvestigationPage />);

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId("timeline-list")).toBeInTheDocument(), {
      timeout: 4000,
    });
    expect(screen.queryByTestId("timeline-reconnecting")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("stops promising a reconnect once the retry budget is exhausted", async () => {
    api.getInvestigation.mockRejectedValue(new Error("network down"));

    render(<InvestigationPage />);

    await waitFor(
      () =>
        expect(screen.getByRole("alert")).toHaveTextContent(
          "The investigation API is unavailable.",
        ),
      { timeout: 6000 },
    );
    await waitFor(() =>
      expect(screen.queryByTestId("timeline-reconnecting")).not.toBeInTheDocument(),
    );
  });
});

describe("staleness", () => {
  it(
    "marks a non-terminal investigation stale once updates stop arriving",
    async () => {
      // Succeed once so there is real state on screen, then fail: the history
      // stays, but it is no longer current.
      api.getInvestigation
        .mockResolvedValueOnce(investigation("running"))
        .mockRejectedValue(new Error("network down"));

      render(<InvestigationPage />);
      await waitFor(() => expect(screen.getByTestId("timeline-list")).toBeInTheDocument());

      await waitFor(() => expect(screen.getByTestId("timeline-stale")).toBeInTheDocument(), {
        timeout: STALE_AFTER_MS + 4000,
      });
      expect(screen.getByTestId("timeline-list")).toBeInTheDocument();
    },
    STALE_AFTER_MS + 10000,
  );

  it.each(["complete", "failed"] as const)(
    "never marks a %s investigation stale",
    async (status) => {
      // Polling stops at a terminal status by design. A final result is
      // finished, not out of date, and saying otherwise contradicts the
      // terminal notice rendered right next to it.
      api.getInvestigation.mockResolvedValue(investigation(status));

      render(<InvestigationPage />);
      await waitFor(() => expect(screen.getByTestId("timeline-list")).toBeInTheDocument());

      await new Promise((resolve) => setTimeout(resolve, STALE_AFTER_MS + 2000));

      expect(screen.queryByTestId("timeline-stale")).not.toBeInTheDocument();
      // Both terminal statuses render their own closing notice; neither
      // should be accompanied by an "out of date" warning.
      const notice = status === "failed" ? "timeline-failed" : "timeline-terminal";
      expect(screen.getByTestId(notice)).toBeInTheDocument();
    },
    STALE_AFTER_MS + 10000,
  );
});

describe("experiment stage wording", () => {
  it("does not claim an approval the server has not recorded", async () => {
    // `experimenting` is set when the Test Planner is invoked, before the
    // human approval boundary. With only a proposed experiment on file the
    // page must not say an approved one is running.
    api.getInvestigation.mockResolvedValue(
      investigation("experimenting", {
        experiments: [
          {
            id: "exp-1",
            hypothesisId: "hyp-1",
            variableChanged: "pool size",
            baselineValue: 10,
            experimentValue: 40,
            status: "proposed",
            sequenceIndex: 0,
          },
        ],
      }),
    );

    render(<InvestigationPage />);

    await waitFor(
      () =>
        expect(screen.getByTestId("current-action")).toHaveTextContent(
          "Now: Experiment proposed, waiting for approval",
        ),
      { timeout: 5000 },
    );
  });

  it("says an approved experiment is running only when one is", async () => {
    api.getInvestigation.mockResolvedValue(
      investigation("experimenting", {
        experiments: [
          {
            id: "exp-1",
            hypothesisId: "hyp-1",
            variableChanged: "pool size",
            baselineValue: 10,
            experimentValue: 40,
            status: "running",
            sequenceIndex: 0,
          },
        ],
      }),
    );

    render(<InvestigationPage />);

    await waitFor(
      () =>
        expect(screen.getByTestId("current-action")).toHaveTextContent(
          "Now: Running an approved experiment",
        ),
      { timeout: 5000 },
    );
  });
});
