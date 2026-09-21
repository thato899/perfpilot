# PerfPilot status

**Last updated:** 2026-09-22 by Govenor

## Current phase

**Phase 1 implementation and real E2E complete; Team Lead sign-off granted. Phase 2 #35 and #38 are merged; #39 is waiting on #32/#34 contracts.**

- Phase 1 implementation: complete.
- Backend and browser E2E: verified.
- Exact DB-pool reference demo: **not reproduced**.
- Phase 1 sign-off: granted by Govenor/Team Lead in PR #48.
- Phase 2 gate: open for the scoped tickets below.
- #35: merged in PR #50 (`27e30b1da5e7450636194e1a82d173258810c7e2`); issue closed with `status:done`.
- #38: merged in PR #51 (`status:done`); consumes the published state contract.
- #32: `status:in-progress`; comparison contract implemented locally, pending PR review and merge.
- #39: `status:todo`; waiting on the #32 comparison contract and baseline/comparison API from #34.

## Phase 2 ownership

| Owner | GitHub | Tickets | Primary area |
|---|---|---|---|
| Thato | `thato899` | #35, #38, #39 | investigation state and frontend integration |
| Kamogelo | `Kamogelo-Skhosana` | #34, #37 | data/API and timeline integration |
| Govenor | `malumzz` | #32, #36 | deterministic metrics and safe k6 execution |
| Thatayaone | `Thatayaone910` | #33 | bounded agent evaluation |

No subjective capability or tooling assessments belong in project documentation. Each owner is responsible for the tickets assigned above.

## Phase 1 record

Merged implementation PRs: #42, #43, #44, #45, #46, and #47, plus earlier foundation PRs. Primary Phase 1 issues #1–#15 and #27 are closed. Issue #13 is `status:done`; #9 is a resolved architecture question without a lifecycle status.

The verified healthy E2E run used FastAPI, PostgreSQL, Redis, Celery, pinned k6 v0.57.0, deterministic metrics, Investigator, persisted Finding/Report, and the Next.js browser path. Evidence remains in [docs/phase1-closeout.md](docs/phase1-closeout.md). Do not describe it as the exact DB-pool degradation demo.

## Phase 2 dependency waves

```text
Wave 1: #32, #33, #35 architecture/state work, #34 persistence/API groundwork
Wave 2: #36 after #32/#35; #37 after #35; #38 after #35 and relevant #33 semantics
Wave 3: #39 after #32/#34 and any required stable #35 run identity
```

Handoff contracts are documented in [PLANNING.md](PLANNING.md), [docs/roadmap.md](docs/roadmap.md), and the issue bodies:

- #32 → #34/#39: comparison schema, units, sign semantics, and unavailable/incompatible behavior.
- #35 → #36/#37/#38: event schema, hypothesis/experiment identity, approval, budget, ordering, and terminal states.
- #34 → #39: baseline identity, retrieval, comparison response, and error envelopes.
- #33 → #35/#38: grounded/unsupported interpretation, evidence references, and confidence constraints.

Avoid dependency cycles and mega-PRs. Shared schema/database changes require affected-owner review and a backward-compatibility statement.

## Govenor — #32 progress

Implemented locally in `packages/metrics`: `MetricComparison` now provides a
typed, JSON-serializable result with available/incompatible/unavailable status,
metric and test-run identity, concurrency context, p50/p90/p95/p99 latency
deltas, throughput delta, error-rate delta, and baseline-relative percentage
deltas. Positive latency/error deltas mean worse performance; positive
throughput deltas mean better performance. Different concurrency values remain
valid for capacity-stage comparisons; endpoint-scope mismatches are rejected.

Validation: focused comparison/API tests pass (`10 passed`), full Python suite
passes (`60 passed, 64 skipped`), and Ruff passes on all touched Python files.
The current checkout is on `main`; the work must be moved to the owner-specific
feature branch and submitted for review before #32 can be marked done.

## Exact next action

Open the owner-specific #32 PR with the comparison contract and notify
Kamogelo/#34 and Thato/#39 of the serialized handoff shape. Then wait for the
#35 investigation-state contract before starting #36. #33 remains owned by
Thatayaone and #37 remains out of scope.
