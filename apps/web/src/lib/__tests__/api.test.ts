import { afterEach, describe, expect, it, vi } from "vitest";

import { createInvestigation, createTarget, getBaselines, getComparison, getInvestigation, getReport } from "../api";

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("production API client", () => {
  it("sends the selected read-only path to the investigation planner", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ id: "inv-1" }))
      .mockResolvedValueOnce(response({
        investigation_id: "inv-1",
        target_id: "target-1",
        status: "planning",
        observations: [], findings: [], hypotheses: [], experiments: [], decisions: [],
      }));
    vi.stubGlobal("fetch", fetchMock);

    await createInvestigation({
      targetId: "target-1",
      objective: "baseline",
      userJourneys: ["/login.php"],
      expectedTraffic: { normalConcurrentUsers: 1, peakConcurrentUsers: 1 },
    });

    const sent = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(sent.user_journeys).toEqual(["/login.php"]);
  });

  it("uses the server proxy and translates target request/response shapes", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response({
        id: "target-1",
        project_id: "project-1",
        base_url: "https://demo.perfpilot.local",
        name: "Demo",
        authorization_confirmed: true,
        authorization_confirmed_by: "Thato",
        authorization_confirmed_at: "2026-09-19T00:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const target = await createTarget("project-1", {
      name: "Demo",
      baseUrl: "https://demo.perfpilot.local",
      authorizationConfirmed: true,
      authorizationConfirmedBy: "Thato",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/perfpilot/projects/project-1/targets",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "Demo",
          base_url: "https://demo.perfpilot.local",
          authorization_confirmed: true,
          authorization_confirmed_by: "Thato",
        }),
      }),
    );
    expect(target).toMatchObject({
      id: "target-1",
      projectId: "project-1",
      baseUrl: "https://demo.perfpilot.local",
      authorizationConfirmed: true,
    });
  });

  it("maps persisted investigation state without changing backend values", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response({
          investigation_id: "inv-1",
          target_id: "target-1",
          status: "investigating",
          current_test_run_id: "run-1",
          observations: [],
          findings: [
            {
              id: "finding-1",
              severity: "HIGH",
              summary: "p95 breached",
              observations: [{ id: "obs-1", statement: "p95 rose", metric_ref: "metric-1" }],
            },
          ],
          hypotheses: [
            {
              id: "hyp-1",
              finding_id: "finding-1",
              statement: "Pool contention",
              confidence: 0.6,
              status: "testing",
              evidence: [{ statement: "Pool at 98%", source_ref: "metric-1" }],
            },
          ],
          experiments: [],
          decisions: [{ step: "investigating", decision: "Analyze run", made_by: "orchestrator" }],
        }),
      ),
    );

    const investigation = await getInvestigation("inv-1");
    expect(investigation.status).toBe("investigating");
    expect(investigation.findings[0]?.observations[0]?.metricRef).toBe("metric-1");
    expect(investigation.hypotheses[0]?.confidence).toBe(0.6);
  });

  it("renders a report from backend values without recomputation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response({
          id: "report-1",
          investigation_id: "inv-1",
          executive_summary: "Summary",
          capacity: { sustainable_concurrency: 750, recommended_operating_concurrency: 600 },
          key_metrics: {
            throughput_rps: 100,
            p50_ms: 100,
            p95_ms: 800,
            p99_ms: 1200,
            error_rate: 0.02,
            peak_concurrency_tested: 1000,
          },
          findings: [{ id: "finding-1", severity: "HIGH", summary: "Slow" }],
          bottleneck_analysis: [
            { observation: "Slow", likely_cause: "Pool", evidence: ["metric-1"], confidence: 0.87 },
          ],
          recommendations: [
            { finding_id: "finding-1", statement: "Increase pool", priority: "HIGH" },
          ],
          regression: { previous_p95_ms: 500, current_p95_ms: 800, regression_pct: 60 },
        }),
      ),
    );

    const report = await getReport("inv-1");
    expect(report.capacity.estimatedSustainableUsers).toBe(750);
    expect(report.keyMetrics.errorRate).toBe(0.02);
    expect(report.regression.regressionPct).toBe(60);
  });

  it("maps the selected baseline and canonical comparison response without changing deltas", async () => {
    const baseline = {
      id: "baseline-1",
      target_id: "target-1",
      test_run_id: "run-base",
      label: "Release baseline",
      selected_by: "Thato",
      test_type: "load",
      target_concurrency: 100,
      scenario_fingerprint: "v1:abc",
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response({ baselines: [baseline] }))
        .mockResolvedValueOnce(
          response({
            baseline,
            current_test_run_id: "run-exp",
            comparisons: [
              {
                status: "available",
                conclusion: "improvement",
                baseline_metric_id: "metric-base",
                current_metric_id: "metric-exp",
                concurrency_delta: 50,
                concurrency_delta_pct: 50,
                baseline_thresholds: { p95_ms: 250, max_error_rate: 0.02 },
                current_thresholds: { p95_ms: 200, max_error_rate: 0.01 },
                baseline_threshold_passed: true,
                current_threshold_passed: false,
                p95_delta_ms: 12.5,
                p95_delta_pct: 5,
              },
            ],
            baseline_only_endpoints: [],
            current_only_endpoints: [],
          }),
        ),
    );

    await expect(getBaselines("target-1")).resolves.toMatchObject([
      { id: "baseline-1", testRunId: "run-base", scenarioFingerprint: "v1:abc" },
    ]);
    await expect(getComparison("run-exp", "baseline-1")).resolves.toMatchObject({
      baseline: { id: "baseline-1", testRunId: "run-base" },
      currentTestRunId: "run-exp",
      comparisons: [
        {
          conclusion: "improvement",
          p95DeltaMs: 12.5,
          p95DeltaPct: 5,
          currentMetricId: "metric-exp",
          concurrencyDelta: 50,
          baselineThresholds: { p95Ms: 250, maxErrorRate: 0.02 },
          currentThresholdPassed: false,
        },
      ],
    });
  });

  it("renders the persisted report shape when optional finding lists are omitted", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response({
          id: "report-2",
          investigation_id: "inv-2",
          executive_summary: "Healthy",
          capacity: { sustainable_concurrency: 1, recommended_operating_concurrency: 1 },
          key_metrics: {
            throughput_rps: 503.162,
            p50_ms: 1.314,
            p95_ms: 2.702,
            p99_ms: 3.703,
            error_rate: 0,
            peak_concurrency_tested: 1,
          },
          bottleneck_analysis: [],
          regression: { previous_p95_ms: 2.702, current_p95_ms: 2.702, regression_pct: 0 },
        }),
      ),
    );

    await expect(getReport("inv-2")).resolves.toMatchObject({
      investigationId: "inv-2",
      findings: [],
      recommendations: [],
      keyMetrics: { p99Ms: 3.703 },
    });
  });

  it("preserves API error status and code for UI handling", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          response(
            { error: { code: "target_not_allowed", message: "Target is not allow-listed." } },
            403,
          ),
        ),
    );

    await expect(getInvestigation("inv-1")).rejects.toMatchObject({
      status: 403,
      code: "target_not_allowed",
    });
  });
});
