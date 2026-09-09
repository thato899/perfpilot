# Agent Contract — Load Engineer Agent

**Owner:** Developer 2/Govenor (Performance Engine) · **Code location:** `agents/load-engineer/`

## Purpose

Convert an approved `TestPlan` into an executable k6 script, run it against a confirmed, allow-listed target, and produce validated metrics. k6 is the execution engine (see [ADR-003](../decisions/ADR-003-k6-selection.md)) — this agent does not build its own load generator.

## Responsibilities

- Generate a k6 script from a `TestPlan`: virtual users, stages, thresholds, scenarios, and realistic traffic distribution across the plan's user journeys.
- Validate the generated script before execution (k6's own `--dry-run`/lint step at minimum; see [testing strategy](../testing/testing-strategy.md)).
- Execute the test as a background job (Celery), never inline on an HTTP request.
- Enforce the safety ceiling (`MAX_VIRTUAL_USERS`, `MAX_TEST_DURATION_SECONDS`) at execution time regardless of what the plan requests — if a plan exceeds the ceiling, this agent clamps and flags it rather than silently running the full request or silently failing.
- Collect k6's raw output and hand it to `packages/metrics` for parsing into validated `Metric` records (p50/p90/p95/p99, throughput, error rate, HTTP status distribution, endpoint-level breakdown).
- Report execution status back to the Orchestrator (`succeeded`, `failed`, `aborted_over_limit`) with the resulting `TestRun` and its metrics.

## Non-responsibilities

- Does **not** decide whether a database, a queue, or any other component is the bottleneck — that's the Performance Investigator, working from the metrics this agent produces.
- Does **not** decide *what* to test — it implements the `TestPlan` it's given; if the plan is wrong, that's a Test Planner concern.
- Does **not** compute derived metrics like regression % or capacity estimates — that belongs in `packages/metrics`, shared deterministic code, not duplicated inside this agent.
- Does **not** target anything outside the confirmed, allow-listed target already validated by `apps/api` (see [security model](../security/security-model.md)) — this agent trusts but also re-checks the target against the allow-list immediately before execution as a defense-in-depth measure.

## Input schema

`LoadExecutionRequest`:

```json
{
  "test_plan": { "...": "TestPlan, see test-planner.md" },
  "target": { "base_url": "https://demo.perfpilot.local", "auth": "reference to a stored credential, never inline secret" },
  "test_run_id": "run_01H..."
}
```

## Output schema

`LoadExecutionResult`:

```json
{
  "test_run_id": "run_01H...",
  "status": "succeeded | failed | aborted_over_limit",
  "k6_script_ref": "pointer to the generated script, stored for audit",
  "raw_output_ref": "pointer to raw k6 JSON summary, stored for audit",
  "metrics": [
    { "endpoint": "/api/quiz/submit", "p50_ms": 120, "p95_ms": 410, "p99_ms": 900, "error_rate": 0.002, "throughput_rps": 340, "concurrency": 500 }
  ],
  "clamped": { "requested_vus": 5500, "executed_vus": 5000, "reason": "MAX_VIRTUAL_USERS ceiling" }
}
```

## Tools

- The `k6` binary (invoked as a subprocess/container — see `infrastructure/docker`), never a reimplementation.
- `packages/metrics` for parsing/validating raw output.
- `packages/ai` (`AIService`) only for the script-generation step itself (turning a `TestPlan` into k6 JS) — not for interpreting results.
- No AI call is on the path between "raw k6 output" and "validated Metric record" — that path is 100% deterministic code, per [system-architecture.md#ai-output-reliability](../architecture/system-architecture.md).

## Failure states

| Failure | Handling |
|---|---|
| Generated k6 script fails validation/dry-run | Retried once with the validation error fed back to script generation; second failure marks the `TestRun` `failed` with the script and error retained for debugging. |
| Plan requests more VUs/duration than the configured ceiling | Clamp to the ceiling, execute the clamped test, and report `clamped` in the result — never silently execute the full request. |
| Target fails the allow-list re-check at execution time | Execution refused before any traffic is sent; `TestRun` marked `failed` with reason `target_not_authorized`. |
| k6 process crashes or times out mid-run | `TestRun` marked `failed`; partial metrics (if any were flushed) are still parsed and retained rather than discarded, and the failure is surfaced, not hidden. |
