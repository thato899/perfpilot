# Agent Contract — Test Planner Agent

**Owner:** Developer 1/Thatayaone (AI / Orchestration) · **Code location:** `agents/test-planner/`

## Purpose

Convert application information and expected traffic into a structured, executable-agnostic performance test plan, and pick the right test *type* for the stated objective. This agent decides *what* should be tested, never *how* it is implemented in k6 (that's the Load Engineer) and never *what a result means* (that's the Investigator).

## Responsibilities

- Parse the target description (API spec/OpenAPI doc, described user journeys, expected concurrency/RPS, peak vs. normal traffic, latency/error-rate requirements).
- Choose the appropriate test type for the stated objective — load, stress, spike, endurance, capacity, baseline, or regression — and state why.
- Produce a `TestPlan`: target concurrency, ramp strategy, stages, user journeys to exercise, thresholds, duration, and success criteria.
- When invoked for a follow-up experiment (Orchestrator-initiated), produce a plan that isolates the single variable named in the experiment request (e.g. "same plan as baseline, with `db_pool_size` noted as the controlled variable") — the Test Planner does not decide *which* variable to change; that comes from the Investigator's `recommended_experiments` via the Orchestrator.
- Flag when the supplied application information is too incomplete to produce a meaningful plan (missing target, missing any traffic expectation) rather than inventing numbers.

## Non-responsibilities

- Does **not** write k6 code or any executable script.
- Does **not** execute anything.
- Does **not** decide whether a test result indicates a bottleneck.
- Does **not** choose the target host or confirm authorization — that is a precondition enforced by `apps/api` before this agent is ever invoked (see [security model](../security/security-model.md)).

## Input schema

`TestPlanRequest`:

```json
{
  "target_description": {
    "application_name": "string",
    "api_spec_ref": "optional pointer to an OpenAPI doc",
    "user_journeys": ["Login → Dashboard → Quiz → Submit Quiz"],
    "expected_traffic": {
      "normal_concurrent_users": 100,
      "peak_concurrent_users": 1000,
      "peak_description": "optional free text, e.g. 'flash sale at 09:00'"
    },
    "performance_requirements": {
      "p95_ms": 1000,
      "max_error_rate": 0.01
    }
  },
  "objective": "determine_capacity | diagnose_regression | validate_fix | baseline",
  "experiment_context": {
    "hypothesis_id": "optional — set only for Orchestrator-initiated follow-up plans",
    "variable_to_isolate": "optional, e.g. 'db_pool_size'",
    "baseline_test_run_id": "optional"
  }
}
```

## Output schema

`TestPlan` (see `packages/schemas/python/agent_io.py` for the authoritative type):

```json
{
  "test_type": "load | stress | spike | endurance | capacity | baseline | regression",
  "rationale": "why this test type fits the stated objective",
  "target_concurrency": 2000,
  "ramp_strategy": { "type": "step | linear | spike", "step_size": 250, "step_duration_s": 120 },
  "user_journeys": ["Login → Dashboard → Quiz → Submit Quiz"],
  "thresholds": { "p95_ms": 1000, "max_error_rate": 0.01 },
  "duration": { "total_s": 1800 },
  "stages": [
    { "target_vus": 10, "duration_s": 60 },
    { "target_vus": 50, "duration_s": 120 }
  ],
  "success_criteria": ["p95 stays under 1000ms through the 500-VU stage"],
  "controlled_variable": "optional — set only on experiment plans, e.g. { name: 'db_pool_size', baseline_value: 50, experiment_value: 100 }"
}
```

## Tools

- `packages/ai` (`AIService`) for the plan-generation reasoning itself.
- Read access to the target's stored `TestPlan` history and prior `TestRun` summaries (via the Orchestrator-provided input; no direct DB access).
- No network access, no execution capability.

## Failure states

| Failure | Handling |
|---|---|
| Target description lacks any traffic expectation | Returns a plan-generation failure with a specific "missing input" reason, not an invented default like "assume 100 users." |
| Requested objective and supplied info conflict (e.g. `diagnose_regression` with no `baseline_test_run_id`) | Rejected with a specific reason; the Orchestrator surfaces this rather than silently picking `baseline` instead. |
| Output fails schema validation (e.g. thresholds missing) | Returned to the Orchestrator's retry path (see [orchestrator.md](orchestrator.md)); this agent does not retry itself. |
