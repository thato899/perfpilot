import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Metric } from "@perfpilot/schemas/types";

import { ComparisonView, type ComparisonState } from "../comparison-view";

const metric = (id: string, values: Partial<Metric> = {}): Metric => ({
  id,
  testRunId: id === "base-metric" ? "base-run" : "experiment-run",
  p50Ms: 100,
  p90Ms: 200,
  p95Ms: 250,
  p99Ms: 300,
  throughputRps: 50,
  errorRate: 0.01,
  concurrency: 100,
  httpStatusDistribution: {},
  recordedAt: "2026-09-27T00:00:00Z",
  ...values,
});

const availableState: ComparisonState = {
  status: "available",
  response: {
    baseline: {
      id: "baseline-1",
      targetId: "target-1",
      testRunId: "base-run",
      label: "release",
      selectedBy: "Thato",
      testType: "load",
      targetConcurrency: 100,
      scenarioFingerprint: "v1:abc",
    },
    currentTestRunId: "experiment-run",
    comparisons: [],
    baselineOnlyEndpoints: [],
    currentOnlyEndpoints: [],
  },
  baselineMetrics: [],
  currentMetrics: [],
};

afterEach(() => {
  vi.restoreAllMocks();
  Reflect.deleteProperty(window.URL, "createObjectURL");
  Reflect.deleteProperty(window.URL, "revokeObjectURL");
});

describe("ComparisonView", () => {
  it("shows baseline and experiment values with canonical deltas and linked records", () => {
    const state: ComparisonState = {
      status: "available",
      response: {
        baseline: {
          id: "baseline-1",
          targetId: "target-1",
          testRunId: "base-run",
          label: "release",
          selectedBy: "Thato",
          testType: "load",
          targetConcurrency: 100,
          scenarioFingerprint: "v1:abc",
        },
        currentTestRunId: "experiment-run",
        comparisons: [
          {
            status: "available",
            conclusion: "improvement",
            baselineMetricId: "base-metric",
            currentMetricId: "experiment-metric",
            baselineConcurrency: 100,
            currentConcurrency: 100,
            concurrencyDelta: 0,
            concurrencyDeltaPct: 0,
            baselineThresholds: { p95Ms: 500, maxErrorRate: 0.02 },
            currentThresholds: { p95Ms: 500, maxErrorRate: 0.02 },
            baselineThresholdPassed: true,
            currentThresholdPassed: true,
            p50DeltaMs: -10,
            p50DeltaPct: -9.09,
            p90DeltaMs: -20,
            p90DeltaPct: -9.09,
            p95DeltaMs: -25,
            p95DeltaPct: -9.09,
            p99DeltaMs: -30,
            p99DeltaPct: -9.09,
            throughputDeltaRps: 5,
            throughputDeltaPct: 10,
            errorRateDelta: 0,
            errorRateDeltaPct: 0,
          },
        ],
        baselineOnlyEndpoints: [],
        currentOnlyEndpoints: [],
      },
      baselineMetrics: [metric("base-metric")],
      currentMetrics: [metric("experiment-metric", { p95Ms: 225, throughputRps: 55 })],
      experimentId: "experiment-1",
    };

    render(<ComparisonView state={state} />);

    expect(screen.getByText("Baseline and experiment comparison")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download CSV" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Download JSON" })).toBeEnabled();
    expect(screen.getByRole("link", { name: "base-run" })).toHaveAttribute(
      "href",
      "/api/perfpilot/test-runs/base-run",
    );
    expect(screen.getByRole("link", { name: "experiment-run" })).toHaveAttribute(
      "href",
      "/api/perfpilot/test-runs/experiment-run",
    );
    expect(screen.getByRole("link", { name: "experiment-1" })).toHaveAttribute(
      "href",
      "#experiment-experiment-1",
    );
    expect(screen.getByText("250 ms")).toBeInTheDocument();
    expect(screen.getByText("225 ms")).toBeInTheDocument();
    expect(screen.getByText("-25 ms")).toBeInTheDocument();
    expect(screen.getAllByText("-9.09%")).toHaveLength(3);
    expect(screen.getByLabelText("Comparison conclusion")).toHaveTextContent("improvement");
    expect(screen.getByText(/baseline: p95 ≤ 500 ms, error rate ≤ 2%/i)).toBeInTheDocument();
  });

  it.each(["regression", "unchanged", "inconclusive"] as const)(
    "shows a canonical %s conclusion",
    (conclusion) => {
      render(
        <ComparisonView
          state={{
            status: "available",
            response: {
              baseline: {
                id: "baseline-1",
                targetId: "target-1",
                testRunId: "base-run",
                label: "release",
                selectedBy: "Thato",
                testType: "load",
                targetConcurrency: 100,
                scenarioFingerprint: "v1:abc",
              },
              currentTestRunId: "experiment-run",
              comparisons: [
                {
                  status: "available",
                  conclusion,
                  reason: conclusion === "inconclusive" ? "Mixed performance signals." : null,
                  currentMetricId: "current-metric",
                },
              ],
              baselineOnlyEndpoints: [],
              currentOnlyEndpoints: [],
            },
            baselineMetrics: [],
            currentMetrics: [metric("current-metric")],
          }}
        />,
      );

      expect(screen.getByLabelText("Comparison conclusion")).toHaveTextContent(conclusion);
    },
  );

  it.each([
    [{ status: "missing", message: "Baseline not recorded." }, "Baseline not recorded."],
    [{ status: "incompatible", message: "Different scenario." }, "Incompatible"],
    [{ status: "unavailable", message: "Metrics unavailable." }, "Comparison unavailable"],
  ] as const)("shows the %s state clearly", (state, expected) => {
    render(<ComparisonView state={state as ComparisonState} />);
    expect(screen.getByRole("status")).toHaveTextContent(expected);
    expect(screen.getByRole("button", { name: "Download CSV" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Download JSON" })).toBeDisabled();
  });

  it("downloads the selected JSON export and reports a browser download failure", async () => {
    const user = userEvent.setup();
    const createObjectURL = vi.fn().mockReturnValue("blob:export");
    Object.defineProperty(window.URL, "createObjectURL", {
      configurable: true,
      value: createObjectURL,
    });
    Object.defineProperty(window.URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const { rerender } = render(<ComparisonView state={availableState} />);
    await user.click(screen.getByRole("button", { name: "Download JSON" }));

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(createObjectURL.mock.calls[0][0]).toBeInstanceOf(Blob);
    expect(click).toHaveBeenCalledOnce();

    createObjectURL.mockImplementationOnce(() => {
      throw new Error("Download API unavailable");
    });
    await user.click(screen.getByRole("button", { name: "Download CSV" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Could not download the comparison");

    rerender(<ComparisonView state={{ status: "loading" }} />);
    expect(screen.getByRole("button", { name: "Download CSV" })).toBeDisabled();
  });
});
