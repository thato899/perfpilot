# agents/reporting

**Owner:** Developer 4/Thato (Frontend / Reporting)

Turns a complete investigation into a human-readable report: executive summary, capacity estimate, ranked findings, bottleneck analysis, actionable recommendations, and regression comparison.

Full contract: [docs/agents/reporting-agent.md](../../docs/agents/reporting-agent.md). Input/output types: `packages/schemas/python/agent_io.py` (`ReportRequest`, `ReportOutput`).

## Status

Phase 1 is complete: `build_report()` produces a valid, contract-checked
`Report` from the real persisted investigation state, and the API persists the
result for the browser. The verified healthy E2E uses the deterministic report
builder; the optional AI-generated prose seam remains schema-validated and is
not required for numeric truth.

- **`report_builder.py`** — `build_report(request: ReportRequest) -> ReportOutput`, plus `validate_report()`, a standalone check for the pass-through/grounding guardrails in reporting-agent.md's Failure states table (also run internally by `build_report` before it returns).
- **`fixtures/investigation_states.py`** — `demo_scenario_request()` (the [demo scenario](../../docs/demo-scenario.md)'s DB-connection-pool-contention walkthrough, using the same numbers as reporting-agent.md's own illustrative example) and `healthy_run_request()` (the "no findings at all" case).
- **`tests/test_report_builder.py`** — both fixtures produce a valid report; recommendations are gated on `HypothesisStatus.SUPPORTED` (bottleneck_analysis is not — it renders every hypothesis); a malformed input (hypothesis pointing at a missing finding) is rejected; tampering with a pass-through value or an unevidenced recommendation is caught by `validate_report`.

## Deterministic and optional AI paths

Prose generation (`_executive_summary`, `_recommendation_statement`) is templated, not AI-generated:

```text
# The deterministic builder is production-safe for numeric truth. An optional
# `build_report_generated()` seam validates any AI-generated ReportOutput using
# the shared structured-output boundary before persistence.
```

The deterministic builder is already the production-safe default. The optional
AI seam can change prose without touching structural grounding, ranking, or
numeric pass-through.

## A schema gap found while implementing this (flagged, not silently worked around)

`ReportRequest` was missing a `key_metrics` field — nothing upstream carried the "Key metrics table" data this agent's Responsibilities section requires. Added it to `packages/schemas/python/agent_io.py` (mirrored in the illustrative JSON in `docs/agents/reporting-agent.md`) as part of this PR — flagged there for Kamogelo/Govenor to weigh in on, since `packages/schemas/` is a shared path per [CONTRIBUTING.md](../../CONTRIBUTING.md#shared-paths--get-a-second-opinion-before-merging).

Also noted in `reporting-agent.md`: `packages/schemas/typescript/types.ts`'s dashboard-facing `Report`/`CapacitySummary` types use different field names again (e.g. `estimatedSustainableUsers` vs. this agent's `sustainable_concurrency`) — a deliberate separate layer, not a second drift to reconcile here. Whoever builds `apps/api`'s `ReportOutput` → `entities.Report` → frontend `Report` mapping (issue #12) needs to know all three shapes name the same concepts differently on purpose.

## Phase 2 boundary

Historical comparisons, richer investigation-loop UI, and additional AI
evaluation belong to the gated Phase 2 issues. They are not prerequisites for
the verified Phase 1 report path.
