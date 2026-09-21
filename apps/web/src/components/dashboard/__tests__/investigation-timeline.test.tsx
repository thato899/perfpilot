import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { InvestigationEvent, InvestigationState } from "@perfpilot/schemas/types";
import { InvestigationTimeline } from "../investigation-timeline";

function baseState(overrides: Partial<InvestigationState> = {}): InvestigationState {
  return {
    investigationId: "inv-1",
    targetId: "target-1",
    status: "investigating",
    observations: [],
    findings: [],
    hypotheses: [],
    experiments: [],
    decisions: [],
    experimentBudget: { maxExperiments: 3, consumed: 1, remaining: 2, exhausted: false },
    events: [],
    ...overrides,
  };
}

function event(
  sequence: number,
  type: string,
  payload: Record<string, unknown> = {},
): InvestigationEvent {
  return {
    id: `event-${sequence}`,
    sequence,
    type,
    payload,
    occurredAt: `2026-09-21T08:${String(sequence).padStart(2, "0")}:00Z`,
  };
}

const FULL_HISTORY: InvestigationEvent[] = [
  event(1, "investigation_created", { objective: "determine_capacity", target_id: "target-1" }),
  event(2, "test_run_queued", { test_run_id: "run-1", kind: "baseline" }),
  event(3, "test_run_started", { test_run_id: "run-1" }),
  event(4, "test_run_completed", { test_run_id: "run-1", status: "succeeded" }),
  event(5, "finding_recorded", { finding_id: "finding-1" }),
  event(6, "hypothesis_recorded", { hypothesis_id: "hyp-1" }),
  event(7, "experiment_proposed", { experiment_id: "exp-1", hypothesis_id: "hyp-1" }),
  event(8, "experiment_approved", { experiment_id: "exp-1", hypothesis_id: "hyp-1" }),
  event(9, "experiment_started", { experiment_id: "exp-1" }),
  event(10, "experiment_completed", {
    experiment_id: "exp-1",
    test_run_id: "run-2",
    status: "succeeded",
  }),
  event(11, "recommendation_recorded", { recommendation_id: "rec-1", hypothesis_id: "hyp-1" }),
  event(12, "budget_exhausted", { consumed: 3, max_experiments: 3 }),
  event(13, "continue_requested", { test_run_id: "run-2", next_action: "invoke_reporting_agent" }),
  event(14, "report_persisted", { investigation_id: "inv-1" }),
];

describe("InvestigationTimeline — required states", () => {
  it("shows a loading state before anything has arrived", () => {
    render(<InvestigationTimeline investigation={null} loading />);
    expect(screen.getByRole("status")).toHaveTextContent(/Loading the investigation timeline/);
  });

  it("shows an error state when the first load failed", () => {
    render(
      <InvestigationTimeline investigation={null} error="The investigation API is unavailable." />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("The investigation API is unavailable.");
  });

  it("shows an explicit empty state rather than an empty list", () => {
    render(<InvestigationTimeline investigation={baseState({ events: [] })} />);
    expect(screen.getByTestId("timeline-empty")).toHaveTextContent(/No events have been recorded/);
    expect(screen.queryByTestId("timeline-list")).not.toBeInTheDocument();
  });

  it("shows a stale notice while keeping the last known history on screen", () => {
    render(
      <InvestigationTimeline
        investigation={baseState({ events: FULL_HISTORY })}
        stale
        lastUpdatedAt={Date.parse("2026-09-21T08:15:00Z")}
      />,
    );
    const stale = screen.getByTestId("timeline-stale");
    expect(stale).toHaveTextContent(/may be out of date/);
    expect(stale).toHaveTextContent("2026-09-21 08:15:00 UTC");
    expect(screen.getByTestId("timeline-list")).toBeInTheDocument();
  });

  it("shows a reconnecting notice", () => {
    render(<InvestigationTimeline investigation={baseState()} reconnecting />);
    expect(screen.getByTestId("timeline-reconnecting")).toHaveTextContent(/Reconnecting/);
  });

  it("surfaces an API error alongside a history it already has", () => {
    render(
      <InvestigationTimeline
        investigation={baseState({ events: FULL_HISTORY })}
        error="Temporary API failure."
      />,
    );
    expect(screen.getByTestId("timeline-error")).toHaveTextContent("Temporary API failure.");
    expect(screen.getByTestId("timeline-list")).toBeInTheDocument();
  });

  it("marks a failed investigation without discarding its history", () => {
    render(
      <InvestigationTimeline
        investigation={baseState({ status: "failed", events: FULL_HISTORY })}
      />,
    );
    expect(screen.getByTestId("timeline-failed")).toHaveTextContent(
      /reported this investigation as failed/,
    );
    expect(screen.getAllByRole("listitem")).toHaveLength(FULL_HISTORY.length);
  });

  it("marks a completed investigation as terminal", () => {
    render(
      <InvestigationTimeline
        investigation={baseState({ status: "complete", events: FULL_HISTORY })}
      />,
    );
    expect(screen.getByTestId("timeline-terminal")).toHaveTextContent(/terminal state/);
    expect(screen.getByTestId("current-action")).toHaveTextContent("Complete");
  });
});

describe("InvestigationTimeline — server truth", () => {
  it("renders every documented event type in sequence order", () => {
    render(<InvestigationTimeline investigation={baseState({ events: FULL_HISTORY })} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(14);
    expect(items.map((item) => item.getAttribute("data-testid"))).toEqual(
      FULL_HISTORY.map((entry) => `timeline-entry-${entry.sequence}`),
    );
  });

  it("orders by sequence even when the API returns them shuffled", () => {
    const shuffled = [FULL_HISTORY[3], FULL_HISTORY[0], FULL_HISTORY[2], FULL_HISTORY[1]];
    render(<InvestigationTimeline investigation={baseState({ events: shuffled })} />);
    expect(screen.getAllByRole("listitem").map((item) => item.getAttribute("data-testid"))).toEqual(
      ["timeline-entry-1", "timeline-entry-2", "timeline-entry-3", "timeline-entry-4"],
    );
  });

  it("shows the timestamp and the stable ids each event carries", () => {
    render(<InvestigationTimeline investigation={baseState({ events: [FULL_HISTORY[9]] })} />);
    const row = screen.getByTestId("timeline-entry-10");
    expect(within(row).getByText("2026-09-21 08:10:00 UTC")).toBeInTheDocument();
    expect(within(row).getByText("exp-1")).toBeInTheDocument();
    expect(within(row).getByText("run-2")).toBeInTheDocument();
    expect(within(row).getByText(/Reported succeeded/)).toBeInTheDocument();
  });

  it("flags an incomplete history instead of presenting it as whole", () => {
    render(
      <InvestigationTimeline
        investigation={baseState({ events: [FULL_HISTORY[0], FULL_HISTORY[4]] })}
      />,
    );
    expect(screen.getByTestId("timeline-gap")).toHaveTextContent(/Some events are missing/);
  });

  it("renders an event type it does not recognise and says so", () => {
    render(
      <InvestigationTimeline
        investigation={baseState({
          events: [FULL_HISTORY[0], event(2, "hypothesis_weakened", { hypothesis_id: "hyp-9" })],
        })}
      />,
    );
    const row = screen.getByTestId("timeline-entry-2");
    expect(within(row).getByText("Hypothesis weakened")).toBeInTheDocument();
    expect(within(row).getByText("unrecognised event type")).toBeInTheDocument();
  });

  it("reports the server's experiment budget, and says so when there isn't one", () => {
    const { unmount } = render(<InvestigationTimeline investigation={baseState()} />);
    expect(screen.getByTestId("experiment-budget")).toHaveTextContent(
      "Experiments: 1 used, 2 remaining of 3",
    );
    unmount();

    render(<InvestigationTimeline investigation={baseState({ experimentBudget: undefined })} />);
    expect(screen.getByText(/did not report an experiment budget/)).toBeInTheDocument();
  });

  it("marks an exhausted budget", () => {
    render(
      <InvestigationTimeline
        investigation={baseState({
          experimentBudget: { maxExperiments: 3, consumed: 3, remaining: 0, exhausted: true },
        })}
      />,
    );
    expect(screen.getByTestId("experiment-budget")).toHaveTextContent("budget exhausted");
  });

  it("reports the current action from the server status, not from the last event", () => {
    // The last event here is a baseline run being queued; the server says the
    // investigation is experimenting. The status wins.
    render(
      <InvestigationTimeline
        investigation={baseState({ status: "experimenting", events: FULL_HISTORY.slice(0, 2) })}
      />,
    );
    expect(screen.getByTestId("current-action")).toHaveTextContent(
      "Now: Running an approved experiment",
    );
  });
});

describe("InvestigationTimeline — accessibility", () => {
  it("names the ordered list after the card heading", () => {
    render(<InvestigationTimeline investigation={baseState({ events: FULL_HISTORY })} />);
    expect(screen.getByRole("list", { name: "Investigation timeline" })).toBeInTheDocument();
  });

  it("announces the current action politely rather than assertively", () => {
    render(<InvestigationTimeline investigation={baseState()} />);
    expect(screen.getByTestId("current-action")).toHaveAttribute("aria-live", "polite");
  });

  it("gives each row's sequence an accessible label", () => {
    render(<InvestigationTimeline investigation={baseState({ events: [FULL_HISTORY[0]] })} />);
    expect(screen.getByLabelText("Sequence 1")).toBeInTheDocument();
  });

  it("exposes machine-readable timestamps", () => {
    render(<InvestigationTimeline investigation={baseState({ events: [FULL_HISTORY[0]] })} />);
    const time = screen.getByTestId("timeline-entry-1").querySelector("time");
    expect(time).toHaveAttribute("dateTime", "2026-09-21T08:01:00Z");
  });

  it("uses alert for failures and status for non-urgent notices", () => {
    render(
      <InvestigationTimeline
        investigation={baseState({ status: "failed", events: FULL_HISTORY })}
        error="Backend failure."
        stale
      />,
    );
    const alerts = screen.getAllByRole("alert").map((node) => node.textContent);
    expect(alerts).toEqual(
      expect.arrayContaining([
        expect.stringContaining("Backend failure."),
        expect.stringContaining("reported this investigation as failed"),
      ]),
    );
    expect(screen.getByTestId("timeline-stale")).toHaveAttribute("role", "status");
  });
});
