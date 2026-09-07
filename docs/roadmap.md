# Implementation Roadmap

## Phase 0 — this commit

Documentation, contracts, repository structure. No agents, no dashboard, no k6 runner, no LLM integration, no production infrastructure. Done when the checklist in [README.md](../README.md#phase-0-definition-of-done) is satisfied.

## Phase 1 — thin vertical slice

The goal of Phase 1 is **one full pass through the lifecycle end to end**, even if every individual piece is minimal, against the [demo scenario](demo-scenario.md). Concretely, in parallel by owner (see [team-workflow.md](development/team-workflow.md)):

- **Developer 1**: `packages/ai` with one working provider (`GeminiProvider` or `DeepSeekProvider`); Orchestrator with the deterministic continuation policy; Test Planner producing a valid `TestPlan` for the demo scenario's inputs; Performance Investigator producing a valid `Finding` from fixture metrics before wiring it to real ones.
- **Developer 2**: k6 script generation for one journey type; execution wrapper with the safety ceiling enforced; `packages/metrics` computing p50/p95/p99/error-rate/threshold-pass-fail/regression-% from real k6 JSON output.
- **Developer 3**: `apps/api` with the endpoints in [api-contract.md](api/api-contract.md) that the Phase 1 slice actually needs (projects, targets, test plan/run, investigation create/get); Postgres schema migrated per [database-design.md](database/database-design.md); Celery wiring for async test execution.
- **Developer 4**: a minimal dashboard — create a target, trigger an investigation, watch a test run's progress, view the resulting report; Reporting Agent producing a valid `Report` from fixture `InvestigationState` before wiring it to a real one.

Definition of done for Phase 1: the [demo scenario](demo-scenario.md) runs for real, once, start to finish, producing a report a stakeholder could read.

## Phase 2 — investigation loop robustness

- The full experiment loop working with more than one candidate hypothesis at a time (today's demo scenario only exercises one).
- Regression comparison against a stored historical baseline, not just the immediately-prior run.
- Agent evaluation suite (see [testing-strategy.md](testing/testing-strategy.md#agent-evaluation)) covering hallucination guardrails against live model output, not just schema fixtures.
- Dashboard: investigation timeline view, live findings panel, side-by-side experiment comparison.

## Phase 3+ — deferred by design (not oversights)

Explicitly out of scope until there's a real need, per the project's "don't overengineer the first version" principle:

- Kubernetes or any distributed load-generation cluster.
- Autonomous agent swarm behavior of any kind.
- A custom load-testing engine (k6 remains the engine indefinitely — see [ADR-003](decisions/ADR-003-k6-selection.md)).
- A custom/self-hosted LLM.
- Multi-user auth, RBAC, multi-tenancy, billing.
- A mobile application.
- Splitting the modular monolith into separate deployed services — the module boundaries (`packages/schemas` contracts, folder ownership) are deliberately kept clean enough that this would be a mechanical extraction later, not a rewrite, if it's ever actually needed.

## Open questions to revisit (not blocking Phase 1)

- Whether experiment approval (`POST /api/investigations/{id}/experiments`, see [api-contract.md](api/api-contract.md)) should ever auto-approve below a certain load ceiling, versus always requiring a human click — deferred to Phase 2, needs product input from a live demo, not a Phase 0 guess.
- Whether `Metric` needs interval/time-bucketed rows (not just per-run summaries) for the dashboard's live progress view, or whether summary-at-completion is enough for the MVP — Developer 2 and Developer 4 should settle this early in Phase 1 since it affects both the metrics pipeline and the dashboard's live view.
