# agents/reporting

**Owner:** Developer 4/Thato (Frontend / Reporting)

Turns a complete investigation into a human-readable report: executive summary, capacity estimate, ranked findings, bottleneck analysis, actionable recommendations, and regression comparison.

Full contract: [docs/agents/reporting-agent.md](../../docs/agents/reporting-agent.md). Input/output types: `packages/schemas/python/agent_io.py` (`ReportRequest`, `ReportOutput`).

## Status

Phase 1 first slice done (issue #15): `build_report()` produces a valid, contract-checked `Report` from a fixture `InvestigationState` — no live investigation or AI call needed yet.

- **`report_builder.py`** — `build_report(request: ReportRequest) -> ReportOutput`, plus `validate_report()`, a standalone check for the pass-through/grounding guardrails in reporting-agent.md's Failure states table (also run internally by `build_report` before it returns).
- **`fixtures/investigation_states.py`** — `demo_scenario_request()` (the [demo scenario](../../docs/demo-scenario.md)'s DB-connection-pool-contention walkthrough, using the same numbers as reporting-agent.md's own illustrative example) and `healthy_run_request()` (the "no findings at all" case).
- **`tests/test_report_builder.py`** — both fixtures produce a valid report; recommendations are gated on `HypothesisStatus.SUPPORTED` (bottleneck_analysis is not — it renders every hypothesis); a malformed input (hypothesis pointing at a missing finding) is rejected; tampering with a pass-through value or an unevidenced recommendation is caught by `validate_report`.

## What's still fixture-only (not a gap — this is the documented plan)

Prose generation (`_executive_summary`, `_recommendation_statement`) is templated, not AI-generated:

```text
# BLOCKED-ON: #1 (packages/ai) — replace with AIService-generated prose once packages/ai exists.
```

Swapping that in once Thatayaone's `packages/ai` (issue #1) lands should not require touching the structural logic (grounding, ranking, pass-through) — those two functions are the only seam that changes.

## A schema gap found while implementing this (flagged, not silently worked around)

`ReportRequest` was missing a `key_metrics` field — nothing upstream carried the "Key metrics table" data this agent's Responsibilities section requires. Added it to `packages/schemas/python/agent_io.py` (mirrored in the illustrative JSON in `docs/agents/reporting-agent.md`) as part of this PR — flagged there for Kamogelo/Govenor to weigh in on, since `packages/schemas/` is a shared path per [CONTRIBUTING.md](../../CONTRIBUTING.md#shared-paths--get-a-second-opinion-before-merging).

Also noted in `reporting-agent.md`: `packages/schemas/typescript/types.ts`'s dashboard-facing `Report`/`CapacitySummary` types use different field names again (e.g. `estimatedSustainableUsers` vs. this agent's `sustainable_concurrency`) — a deliberate separate layer, not a second drift to reconcile here. Whoever builds `apps/api`'s `ReportOutput` → `entities.Report` → frontend `Report` mapping (issue #12) needs to know all three shapes name the same concepts differently on purpose.

## Not yet done

- Wiring to a real `InvestigationState` once the Orchestrator (issue #2) and Performance Investigator (issue #4) exist.
- The AI-generated prose swap noted above.
