# Implementation Roadmap

> **Current status (2026-09-23):** Phase 1 implementation and real backend/browser E2E are complete. Govenor/Team Lead granted sign-off in PR #48. The exact DB-pool reference demo was not reproduced. Phase 2 implementation is underway: #32, #35, and #38 are merged and verified; #34 and #37 remain open and unmerged; #39 is blocked on #34.

## Phase 0 — this commit

Documentation, contracts, repository structure. No agents, no dashboard, no k6 runner, no LLM integration, no production infrastructure. Done when the checklist in [README.md](../README.md#phase-0-definition-of-done) is satisfied.

## Phase 1 — thin vertical slice

The goal of Phase 1 is **one full pass through the lifecycle end to end**, even if every individual piece is minimal, against the [demo scenario](demo-scenario.md). Concretely, in parallel by owner (see [team-workflow.md](development/team-workflow.md)):

- **Developer 1/Thatayaone**: `packages/ai` with one working provider (`GeminiProvider` or `DeepSeekProvider`); Orchestrator with the deterministic continuation policy; Test Planner producing a valid `TestPlan` for the demo scenario's inputs; Performance Investigator producing a valid `Finding` from fixture metrics before wiring it to real ones.
- **Developer 2/Govenor**: k6 script generation for one journey type; execution wrapper with the safety ceiling enforced; `packages/metrics` computing p50/p95/p99/error-rate/threshold-pass-fail/regression-% from real k6 JSON output.
- **Developer 3/Kamogelo**: `apps/api` with the endpoints in [api-contract.md](api/api-contract.md) that the Phase 1 slice actually needs (projects, targets, test plan/run, investigation create/get); Postgres schema migrated per [database-design.md](database/database-design.md); Celery wiring for async test execution.
- **Developer 4/Thato**: a minimal dashboard — create a target, trigger an investigation, watch a test run's progress, view the resulting report; Reporting Agent producing a valid `Report` from fixture `InvestigationState` before wiring it to a real one.

Definition of done for Phase 1: the [demo scenario](demo-scenario.md) runs for real, once, start to finish, producing a report a stakeholder could read.

## Phase 2 — investigation loop robustness

Phase 2 is authorized after the Phase 1 sign-off recorded in `STATUS.md`. Ticket status is tracked on GitHub and must match merged implementation evidence. No ticket is considered complete until its own Definition of Done is met and its PR is merged and verified.

### Phase 2 ticket register

| ID | Owner | Deliverable | Depends on |
|---|---|---|---|
| P2-API-1 ([#34](https://github.com/thato899/perfpilot/issues/34)) | Kamogelo | Persisted historical baselines and deterministic baseline comparison contract/API | #32 stable; Phase 1 sign-off |
| P2-API-2 ([#35](https://github.com/thato899/perfpilot/issues/35)) | Thato | Robust multi-hypothesis investigation state, experiment budget, and loop API | Phase 1 sign-off; #33 semantics where applicable |
| P2-METRICS-1 ([#32](https://github.com/thato899/perfpilot/issues/32)) | Govenor | Deterministic baseline/experiment comparison metrics and regression calculations | Phase 1 sign-off |
| P2-RUNNER-1 ([#36](https://github.com/thato899/perfpilot/issues/36)) | Govenor | Safe repeatable execution of approved follow-up experiments with real k6 results | Phase 1 sign-off; P2-API-2 contract |
| P2-EVAL-1 ([#33](https://github.com/thato899/perfpilot/issues/33)) | Thatayaone | Agent evaluation suite for structured output, evidence grounding, and hallucination resistance | Phase 1 sign-off |
| P2-UI-1 ([#37](https://github.com/thato899/perfpilot/issues/37)) | Kamogelo | Investigation timeline and run-state visualization | #35 stable timeline/state API |
| P2-UI-2 ([#38](https://github.com/thato899/perfpilot/issues/38)) | Thato | Live findings/hypotheses panel with evidence and confidence states | #35; relevant #33 semantics |
| P2-UI-3 ([#39](https://github.com/thato899/perfpilot/issues/39)) | Thato | Side-by-side baseline/experiment comparison and report integration | Phase 1 sign-off; P2-API-1; P2-METRICS-1 |

GitHub issues are the execution source of truth. The authoritative allocation is Thato: #35/#38/#39; Kamogelo: #34/#37; Govenor: #32/#36; Thatayaone: #33. See [PLANNING.md](../PLANNING.md) for the dependency waves and handoff contracts.

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
- **Resolved:** summary-at-completion `Metric` rows are sufficient for the Phase 1 MVP; interval/time-bucketed rows are deferred to Phase 2 if the timeline or comparison UX demonstrates a need. See [database-design.md](database/database-design.md).
