import type { InvestigationState, Report, TestRun } from "@perfpilot/schemas/types";
import { render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
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

import { ApiRequestError } from "@/lib/api";

import InvestigationPage from "./page";

const investigation = (status: InvestigationState["status"]): InvestigationState => ({
  investigationId: "inv-1",
  targetId: "target-1",
  status,
  currentTestRunId: "run-1",
  observations: [],
  findings: [],
  hypotheses: [],
  experiments: [],
  decisions: [],
});

const testRun = (status: TestRun["status"]): TestRun => ({
  id: "run-1",
  testPlanId: "plan-1",
  targetId: "target-1",
  status,
  progress: { currentVus: status === "succeeded" ? 1 : 0, targetVus: 1 },
});

const report: Report = {
  id: "report-1",
  investigationId: "inv-1",
  executiveSummary: "The persisted report is authoritative.",
  capacity: { estimatedSustainableUsers: 1, recommendedOperatingUsers: 1 },
  keyMetrics: {
    throughputRps: 503.162,
    p50Ms: 1.314,
    p95Ms: 2.702,
    p99Ms: 3.703,
    errorRate: 0,
    peakConcurrencyTested: 1,
  },
  findings: [],
  bottleneckAnalysis: [],
  recommendations: [],
  regression: { previousP95Ms: 2.702, currentP95Ms: 2.702, regressionPct: 0 },
};

async function renderLoaded(
  status: InvestigationState["status"],
  runStatus: TestRun["status"] = "running",
) {
  api.getInvestigation.mockResolvedValue(investigation(status));
  api.getTestRun.mockResolvedValue(testRun(runStatus));
  api.getReport.mockResolvedValue(report);
  render(<InvestigationPage />);
  await waitFor(() => expect(screen.getByText("Investigation progress")).toBeInTheDocument());
}

beforeEach(() => {
  api.getInvestigation.mockReset();
  api.getReport.mockReset();
  api.getTestRun.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("investigation result-page lifecycle", () => {
  it("does not suppress the replacement poll under React Strict Mode", async () => {
    api.getInvestigation.mockResolvedValue(investigation("running"));
    api.getTestRun.mockResolvedValue(testRun("running"));

    render(
      <StrictMode>
        <InvestigationPage />
      </StrictMode>,
    );

    await waitFor(() => expect(api.getTestRun).toHaveBeenCalledWith("run-1"));
  });

  it.each(["planning", "running", "investigating"] as const)(
    "keeps polling while the backend is %s",
    async (status) => {
      api.getInvestigation
        .mockResolvedValueOnce(investigation(status))
        .mockResolvedValueOnce(investigation("running"));
      api.getTestRun.mockResolvedValue(testRun("running"));

      render(<InvestigationPage />);
      await waitFor(() => expect(api.getInvestigation).toHaveBeenCalledTimes(2), {
        timeout: 3000,
      });
    },
  );

  it("waits during reporting and fetches the persisted report after completion", async () => {
    api.getInvestigation
      .mockResolvedValueOnce(investigation("reporting"))
      .mockResolvedValueOnce(investigation("complete"));
    api.getTestRun.mockResolvedValue(testRun("succeeded"));
    api.getReport.mockResolvedValue(report);

    render(<InvestigationPage />);
    await waitFor(() => expect(api.getInvestigation).toHaveBeenCalledTimes(1));
    expect(api.getReport).not.toHaveBeenCalled();
    await waitFor(() => expect(api.getReport).toHaveBeenCalledWith("inv-1"), { timeout: 3000 });
  });

  it("stops polling at complete and renders the real report values", async () => {
    await renderLoaded("complete", "succeeded");
    await waitFor(() => expect(screen.getByText(report.executiveSummary)).toBeInTheDocument());
    expect(screen.getByText("503.162")).toBeInTheDocument();
    expect(screen.getByText("2.702")).toBeInTheDocument();
    const calls = api.getInvestigation.mock.calls.length;
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(api.getInvestigation).toHaveBeenCalledTimes(calls);
  });

  it("surfaces a missing report after a completed investigation", async () => {
    api.getInvestigation.mockResolvedValue(investigation("complete"));
    api.getTestRun.mockResolvedValue(testRun("succeeded"));
    api.getReport.mockRejectedValue(new ApiRequestError("not ready", 404));

    render(<InvestigationPage />);
    await waitFor(() =>
      expect(
        screen.getByText("The investigation is complete, but its persisted report is unavailable."),
      ).toBeInTheDocument(),
    );
  });

  it("stops on a failed investigation", async () => {
    await renderLoaded("failed", "failed");
    expect(
      screen.getByText("The backend reported an investigation or test-run failure."),
    ).toBeInTheDocument();
    expect(api.getReport).not.toHaveBeenCalled();
  });

  it("stops on a failed test run", async () => {
    await renderLoaded("running", "failed");
    expect(
      screen.getByText("The backend reported an investigation or test-run failure."),
    ).toBeInTheDocument();
  });

  it("surfaces an aborted test run", async () => {
    await renderLoaded("running", "aborted_over_limit");
    expect(
      screen.getByText("The test run was aborted by a configured safety limit."),
    ).toBeInTheDocument();
  });

  it("recovers after a transient API failure", async () => {
    api.getInvestigation
      .mockRejectedValueOnce(new Error("temporary network failure"))
      .mockResolvedValueOnce(investigation("running"));
    api.getTestRun.mockResolvedValue(testRun("running"));

    render(<InvestigationPage />);
    await waitFor(() => expect(screen.getByText("temporary network failure")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Investigation progress")).toBeInTheDocument(), {
      timeout: 3000,
    });
  });

  it("exits loading after repeated API failures", async () => {
    api.getInvestigation.mockRejectedValue(new Error("API unavailable"));

    render(<InvestigationPage />);
    await waitFor(() => expect(screen.getByText("API unavailable")).toBeInTheDocument());
    await waitFor(
      () => expect(screen.getByText("The investigation API is unavailable.")).toBeInTheDocument(),
      { timeout: 6000 },
    );
  }, 7000);
});
