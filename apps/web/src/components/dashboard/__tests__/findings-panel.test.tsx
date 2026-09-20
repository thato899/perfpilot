import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { InvestigationState } from "@perfpilot/schemas/types";
import { FindingsPanel } from "../findings-panel";

const state: InvestigationState = {
  investigationId: "inv-1",
  targetId: "target-1",
  status: "complete",
  observations: [],
  decisions: [],
  findings: [
    {
      id: "finding-1",
      severity: "HIGH",
      summary: "Performance degradation",
      observations: [
        { id: "obs-1", statement: "p95 latency exceeded threshold", metricRef: "metric-1" },
      ],
    },
  ],
  hypotheses: [
    {
      id: "hyp-a",
      findingId: "finding-1",
      statement: "DB contention",
      confidence: 0.6,
      status: "supported",
      evidence: [{ statement: "Pool saturation", sourceRef: "metric-1" }],
    },
    {
      id: "hyp-b",
      findingId: "finding-1",
      statement: "CPU saturation",
      confidence: 0.2,
      status: "rejected",
      evidence: [],
    },
  ],
  experiments: [
    {
      id: "exp-1",
      hypothesisId: "hyp-a",
      variableChanged: "pool size",
      baselineValue: 10,
      experimentValue: 20,
      status: "approved",
      sequenceIndex: 1,
    },
  ],
  experimentBudget: { maxExperiments: 1, consumed: 1, remaining: 0, exhausted: true },
};

describe("FindingsPanel", () => {
  it("renders deterministic measurements, competing hypotheses, evidence and server states", () => {
    render(<FindingsPanel investigation={state} />);
    expect(screen.getByText("p95 latency exceeded threshold")).toBeInTheDocument();
    expect(screen.getByText("DB contention")).toBeInTheDocument();
    expect(screen.getByText("CPU saturation")).toBeInTheDocument();
    expect(screen.getByText("Pool saturation")).toBeInTheDocument();
    expect(screen.getByText("approved")).toBeInTheDocument();
    expect(screen.getByText(/1 used of 1; 0 remaining — exhausted/)).toBeInTheDocument();
  });

  it("shows explicit empty state without inventing findings", () => {
    render(
      <FindingsPanel investigation={{ ...state, findings: [], hypotheses: [], experiments: [] }} />,
    );
    expect(screen.getByText(/No findings were recorded/)).toBeInTheDocument();
  });
});
