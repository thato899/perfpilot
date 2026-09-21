import { describe, expect, it } from "vitest";
import type {
  ExperimentRecord,
  InvestigationEvent,
  InvestigationState,
} from "@perfpilot/schemas/types";

import {
  currentAction,
  describeEvent,
  formatTimestamp,
  hasSequenceGap,
  isKnownEventType,
  KNOWN_EVENT_TYPES,
  latestSequence,
  toTimeline,
} from "../investigation-events";

function event(overrides: Partial<InvestigationEvent> & { sequence: number }): InvestigationEvent {
  return {
    id: overrides.id ?? `event-${overrides.sequence}`,
    sequence: overrides.sequence,
    type: overrides.type ?? "investigation_created",
    payload: overrides.payload ?? {},
    occurredAt: overrides.occurredAt ?? "2026-09-21T08:00:00Z",
    idempotencyKey: overrides.idempotencyKey,
  };
}

describe("event type coverage", () => {
  it("covers every type the #35 contract documents", () => {
    // docs/phase2/p2-api-2-investigation-state.md, "Event contract". If the
    // server grows a type, this is the test that should fail first.
    expect([...KNOWN_EVENT_TYPES].sort()).toEqual(
      [
        "budget_exhausted",
        "continue_requested",
        "experiment_approved",
        "experiment_completed",
        "experiment_proposed",
        "experiment_started",
        "finding_recorded",
        "hypothesis_recorded",
        "investigation_created",
        "recommendation_recorded",
        "report_persisted",
        "test_run_completed",
        "test_run_queued",
        "test_run_started",
      ].sort(),
    );
  });

  it("gives every known type a label and a phase", () => {
    for (const type of KNOWN_EVENT_TYPES) {
      const entry = describeEvent(event({ sequence: 1, type }));
      expect(entry.known).toBe(true);
      expect(entry.label).not.toHaveLength(0);
      expect(entry.phase).not.toHaveLength(0);
    }
  });

  it("recognises known types and rejects unknown ones", () => {
    expect(isKnownEventType("report_persisted")).toBe(true);
    expect(isKnownEventType("something_new")).toBe(false);
  });
});

describe("ordering", () => {
  it("orders by sequence, not by array position", () => {
    const entries = toTimeline([
      event({ sequence: 3, id: "c" }),
      event({ sequence: 1, id: "a" }),
      event({ sequence: 2, id: "b" }),
    ]);
    expect(entries.map((entry) => entry.sequence)).toEqual([1, 2, 3]);
    expect(entries.map((entry) => entry.id)).toEqual(["a", "b", "c"]);
  });

  it("collapses a duplicate delivery of the same event", () => {
    // Celery is at-least-once and a reconnect can overlap a poll, so the same
    // event id arriving twice must not render as two transitions.
    const entries = toTimeline([
      event({ sequence: 1, id: "a" }),
      event({ sequence: 1, id: "a" }),
      event({ sequence: 2, id: "b" }),
    ]);
    expect(entries).toHaveLength(2);
  });

  it("is stable when two events share a sequence", () => {
    const first = toTimeline([event({ sequence: 1, id: "zz" }), event({ sequence: 1, id: "aa" })]);
    const second = toTimeline([event({ sequence: 1, id: "aa" }), event({ sequence: 1, id: "zz" })]);
    expect(first.map((entry) => entry.id)).toEqual(second.map((entry) => entry.id));
  });

  it("returns an empty timeline for missing or empty events", () => {
    expect(toTimeline(undefined)).toEqual([]);
    expect(toTimeline([])).toEqual([]);
    expect(latestSequence([])).toBeUndefined();
  });

  it("reports the latest sequence", () => {
    expect(
      latestSequence(toTimeline([event({ sequence: 1 }), event({ sequence: 9, id: "x" })])),
    ).toBe(9);
  });
});

describe("gap detection", () => {
  it("accepts a complete run of sequences", () => {
    expect(
      hasSequenceGap(
        toTimeline([
          event({ sequence: 1, id: "a" }),
          event({ sequence: 2, id: "b" }),
          event({ sequence: 3, id: "c" }),
        ]),
      ),
    ).toBe(false);
  });

  it("flags a hole in the middle", () => {
    expect(
      hasSequenceGap(
        toTimeline([event({ sequence: 1, id: "a" }), event({ sequence: 3, id: "c" })]),
      ),
    ).toBe(true);
  });

  it("flags a history that does not start at one", () => {
    expect(hasSequenceGap(toTimeline([event({ sequence: 4, id: "d" })]))).toBe(true);
  });

  it("treats an empty history as ungapped", () => {
    expect(hasSequenceGap([])).toBe(false);
  });
});

describe("detail text", () => {
  it("reads the objective from an investigation_created payload", () => {
    const entry = describeEvent(
      event({
        sequence: 1,
        type: "investigation_created",
        payload: { objective: "determine_capacity" },
      }),
    );
    expect(entry.detail).toBe("Objective: determine capacity");
  });

  it("names the baseline run kind", () => {
    const entry = describeEvent(
      event({ sequence: 2, type: "test_run_queued", payload: { kind: "baseline" } }),
    );
    expect(entry.detail).toBe("Queued as the baseline run");
  });

  it("reports the budget split", () => {
    const entry = describeEvent(
      event({
        sequence: 9,
        type: "budget_exhausted",
        payload: { consumed: 3, max_experiments: 3 },
      }),
    );
    expect(entry.detail).toBe("3 of 3 experiments used");
  });

  it("reports the orchestrator's next action", () => {
    const entry = describeEvent(
      event({
        sequence: 8,
        type: "continue_requested",
        payload: { next_action: "invoke_reporting_agent" },
      }),
    );
    expect(entry.detail).toBe("Orchestrator chose: invoke reporting agent");
  });

  it("omits the detail line when the payload does not carry it", () => {
    // The alternative — inventing a sentence — is the failure mode this
    // ticket exists to prevent.
    expect(
      describeEvent(event({ sequence: 1, type: "test_run_queued", payload: {} })).detail,
    ).toBeUndefined();
    expect(
      describeEvent(event({ sequence: 1, type: "budget_exhausted", payload: { consumed: 1 } }))
        .detail,
    ).toBeUndefined();
    expect(describeEvent(event({ sequence: 1, type: "finding_recorded" })).detail).toBeUndefined();
  });
});

describe("related ids", () => {
  it("surfaces the stable entity ids the payload carries", () => {
    const entry = describeEvent(
      event({
        sequence: 5,
        type: "experiment_completed",
        payload: {
          experiment_id: "exp-1",
          test_run_id: "run-1",
          status: "succeeded",
        },
      }),
    );
    expect(entry.relatedIds).toEqual([
      { label: "Run", value: "run-1" },
      { label: "Experiment", value: "exp-1" },
    ]);
  });

  it("ignores id fields that are not strings", () => {
    const entry = describeEvent(
      event({ sequence: 1, type: "finding_recorded", payload: { finding_id: 42 } }),
    );
    expect(entry.relatedIds).toEqual([]);
  });
});

describe("unknown event types", () => {
  it("renders rather than drops an unrecognised type", () => {
    const entry = describeEvent(event({ sequence: 7, type: "hypothesis_weakened" }));
    expect(entry.known).toBe(false);
    expect(entry.label).toBe("Hypothesis weakened");
    expect(entry.sequence).toBe(7);
  });

  it("keeps an unknown event in sequence order with the known ones", () => {
    const entries = toTimeline([
      event({ sequence: 1, id: "a", type: "investigation_created" }),
      event({ sequence: 2, id: "b", type: "something_the_ui_has_not_seen" }),
      event({ sequence: 3, id: "c", type: "report_persisted" }),
    ]);
    expect(entries.map((entry) => entry.known)).toEqual([true, false, true]);
    expect(entries.map((entry) => entry.sequence)).toEqual([1, 2, 3]);
  });
});

describe("current action", () => {
  function state(
    status: InvestigationState["status"],
    experiments: InvestigationState["experiments"] = [],
  ): InvestigationState {
    return {
      investigationId: "inv-1",
      targetId: "target-1",
      status,
      observations: [],
      findings: [],
      hypotheses: [],
      experiments,
      decisions: [],
    };
  }

  function experiment(status: ExperimentRecord["status"], id: string = status): ExperimentRecord {
    return {
      id,
      hypothesisId: "hyp-1",
      variableChanged: "pool size",
      baselineValue: 10,
      experimentValue: 40,
      status,
      sequenceIndex: 0,
    };
  }

  it("describes the unambiguous statuses", () => {
    expect(currentAction(state("planning"))).toBe("Planning the next test");
    expect(currentAction(state("running"))).toBe("Running a test");
    expect(currentAction(state("investigating"))).toBe("Analysing results");
    expect(currentAction(state("reporting"))).toBe("Writing the report");
    expect(currentAction(state("complete"))).toBe("Complete");
    expect(currentAction(state("failed"))).toBe("Failed");
  });

  describe("the experimenting status", () => {
    // The Orchestrator sets `experimenting` together with INVOKE_TEST_PLANNER,
    // *before* the human approval boundary. Claiming an approved experiment is
    // running at that point asserts both an approval and load generation that
    // may not have happened.
    it("does not claim an approval when no experiment row exists yet", () => {
      expect(currentAction(state("experimenting"))).toBe("Working out the next experiment");
    });

    it("says a proposal is waiting for approval", () => {
      expect(currentAction(state("experimenting", [experiment("proposed")]))).toBe(
        "Experiment proposed, waiting for approval",
      );
    });

    it("distinguishes approved-but-not-yet-started from running", () => {
      expect(currentAction(state("experimenting", [experiment("approved")]))).toBe(
        "Experiment approved, waiting to start",
      );
      expect(currentAction(state("experimenting", [experiment("queued")]))).toBe(
        "Approved experiment queued",
      );
      expect(currentAction(state("experimenting", [experiment("running")]))).toBe(
        "Running an approved experiment",
      );
    });

    it("reports the most advanced experiment when several coexist", () => {
      expect(
        currentAction(
          state("experimenting", [
            experiment("proposed", "a"),
            experiment("running", "b"),
            experiment("approved", "c"),
          ]),
        ),
      ).toBe("Running an approved experiment");
    });

    it("falls back to neutral wording when every experiment is terminal", () => {
      expect(
        currentAction(
          state("experimenting", [experiment("succeeded", "a"), experiment("rejected", "b")]),
        ),
      ).toBe("Working out the next experiment");
    });
  });
});

describe("timestamps", () => {
  it("formats in UTC so the output does not depend on the runner's timezone", () => {
    expect(formatTimestamp("2026-09-21T08:30:05Z")).toBe("2026-09-21 08:30:05 UTC");
    expect(formatTimestamp("2026-09-21T10:30:05+02:00")).toBe("2026-09-21 08:30:05 UTC");
  });

  it("passes an unparseable timestamp through untouched", () => {
    expect(formatTimestamp("not a date")).toBe("not a date");
  });
});
