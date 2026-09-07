# Testing Strategy

This describes how the eventual (Phase 1+) implementation will be tested. No tests are implemented in Phase 0.

## Unit tests

Target the deterministic core first — it's the highest-value, lowest-flakiness layer:

- **`packages/metrics`**: p50/p90/p95/p99 aggregation, error-rate calculation, threshold pass/fail evaluation, regression percentage, capacity estimation. These are pure functions over recorded/fixture k6 output and should be tested exhaustively — this is the layer the whole "AI never does arithmetic" guarantee depends on (see [system-architecture.md#ai-output-reliability](../architecture/system-architecture.md)).
- **`packages/schemas`**: every Pydantic model validates known-good fixtures and rejects known-bad ones (missing evidence on a hypothesis, a recommendation with no `finding_id`, etc. — see each agent contract's "Guardrails"/"Failure states" sections).
- **Orchestrator continuation policy** (`agents/orchestrator`): the deterministic go/stop rules in [orchestrator.md](../agents/orchestrator.md#continuation-policy) — table-driven tests over `(state) -> decision`, independent of any actual AI call.

## Integration tests

- **FastAPI + database**: each endpoint in [api-contract.md](../api/api-contract.md) against a real (test) Postgres instance — request validation, persistence, error shapes, ownership checks.
- **Agent + AI provider**: each agent's prompt/response cycle against a real provider call in a small, deliberately-run suite (not part of the fast test loop, given cost/latency) — confirms the provider abstraction (`packages/ai`) actually round-trips a valid structured output for real, on top of the schema-fixture tests above which don't call a live model.
- **Backend + k6**: the Load Engineer's generate → dry-run-validate → execute → parse pipeline against a small, fast, local demo target — confirms the whole chain works before pointing it at the real demo app.
- **Metrics pipeline**: raw k6 JSON summary (recorded fixture) → `packages/metrics` → validated `Metric` records, end to end.

## Agent evaluation

This is distinct from ordinary integration testing: it's specifically about whether an agent's *behavior* respects its contract, not just whether it returns well-formed JSON.

For each agent, maintain a small fixture suite that checks:

- **Structural validity** — output always validates against its Pydantic schema (covered above, but re-asserted here specifically against live-model output, not just hand-written fixtures).
- **Responsibility boundaries respected** — e.g. the Test Planner never emits k6 code; the Load Engineer's output never contains a bottleneck claim; the Reporting Agent never introduces a number not present in its input (see each agent's "Non-responsibilities").
- **No unevidenced claims** — every `Performance Investigator` hypothesis carries at least one `evidence` entry with a `source_ref` that actually exists in the input it was given (see [performance-investigator.md#guardrails](../agents/performance-investigator.md#guardrails-against-hallucination-enforced-not-just-prompted)). This is checked mechanically, not by eyeballing output.
- **Observation vs. hypothesis distinction held** — an `observations[]` entry never contains speculative language ("likely," "probably") and a `hypotheses[]` entry is never phrased as settled fact.
- **Useful test plans** — a Test Planner fixture suite covering a range of stated objectives (`determine_capacity`, `diagnose_regression`, etc.) and checking the recommended `test_type` matches the objective per the mapping in [test-planner.md](../agents/test-planner.md).

## End-to-end

The full lifecycle, run against the demo target from [docs/demo-scenario.md](../demo-scenario.md):

```text
Create project → Configure target → Generate plan → Generate k6 → Run test
→ Analyze → Investigate → (Experiment loop) → Report
```

This is the scenario the hackathon demo itself performs live; an automated version of it (even just one happy-path run, recorded) is the highest-value end-to-end test for confidence going into the demo.

## What's explicitly out of scope for testing in the MVP

- Load/soak testing of PerfPilot's *own* infrastructure (i.e., testing whether the API/worker can handle many concurrent investigations) — not a hackathon concern.
- Exhaustive fuzzing of AI output — the guardrails above catch the failure modes that matter (hallucinated evidence, boundary violations); broader adversarial-prompt testing is a post-MVP concern.
