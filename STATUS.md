# PerfPilot status

**Last updated:** 2026-09-27 by Thato

## Current phase

**Phase 1 implementation and real E2E complete; Team Lead sign-off granted. Phase 2 #32–#38 are complete; #39 is unblocked now that #34 is merged.**

- Phase 1 implementation: complete.
- Backend and browser E2E: verified.
- Exact DB-pool reference demo: **not reproduced**.
- Phase 1 sign-off: granted by Govenor/Team Lead in PR #48.
- Phase 2 gate: open for the remaining scoped ticket, #39.
- #35: merged in PR #50 (27e30b1da5e7450636194e1a82d173258810c7e2); issue closed with `status:done`.
- #38: merged in PR #51; issue closed with `status:done`; consumes the published state contract.
- #32: merged in PR #54; comparison contract is the stable handoff for #34/#39.
- #33: implementation merged in PR #55; issue closed. The deterministic suite passes without credentials, and the bounded live adapter is opt-in.
- #34: merged in PR #62 and carried to `main` by PR #63; issue closed. Persists a deliberately chosen baseline per target and exposes the comparison API #39 consumes. Every number comes from #32's `compare_metrics`; this layer adds no arithmetic. `baseline_id` is required on the comparison endpoint — there is no fallback to "the most recent run", which is the silent selection the ticket exists to prevent. Review added stable scenario identity (`apps/api/scenario_identity.py`), authorization for both targets, and idempotency-key ordering. See [docs/phase2/p2-api-1-baselines.md](docs/phase2/p2-api-1-baselines.md).
- #35 follow-up for its owner: `--autogenerate` wants to rename four `investigation_event` unique constraints — pre-existing drift between that migration and `db/base.py` naming conventions (identical columns, different generated names). #34 deliberately left the other owner's table untouched; it needs its own fix.
- Follow-up from #34 for the run-lifecycle owner: baseline scenario identity is frozen at selection, but the current run's identity is read from its plan live. Editing a plan after runs have executed can make previously comparable runs incomparable. Snapshot the scenario onto `test_run` at execution time; this was left out of #34 because it changes the run lifecycle.
- #36: implementation merged through PR #58; issue closed. Approved follow-up execution persists one deterministic `ExperimentResult` per run. See the Govenor progress section below.
- #37: **done** — merged in PR #60 and carried to `main` by PR #61. PR #64 records the post-merge browser evidence required by the DoD; issue closed with `status:done` on 2026-09-27. See [docs/phase2/p2-ui-1-investigation-timeline.md](docs/phase2/p2-ui-1-investigation-timeline.md).
- #39: #32 and #34 are complete, so its dependency is satisfied. GitHub still labels the issue `status:blocked`; reconcile the board label when Thato resumes work.

## Phase 2 ownership

| Owner | GitHub | Tickets | Primary area |
|---|---|---|---|
| Thato | `thato899` | #35, #38, #39 | investigation state and frontend integration |
| Kamogelo | `Kamogelo-Skhosana` | #34, #37 | data/API and timeline integration |

## Govenor — #36 progress

The worker execution boundary consumes the approved Experiment and linked TestRun from #35, refuses duplicate delivery, re-checks target authorization, enforces the configured k6 safety limits, persists raw/script references and Metric rows, and persists exactly one `ExperimentResult` containing the typed comparison from #32. The Load Engineer contract documents the lifecycle, failure states, idempotency, and audit requirements. Runtime changes ensure a new investigation records its baseline run ID and approval events contain the flushed Experiment ID.

Validation on `feature/p2-runner-1`: focused API/worker regression tests passed (`3 passed`), earlier worker/metrics coverage passed (`24 passed`), the full Python suite passed before the live smoke (`134 passed`), and Ruff/Black passed on touched Python files. Real Docker evidence: API health returned 200, worker k6 reported `v0.57.0`, baseline run `f79dccc5-6d25-4aaa-b50d-783b854ac939` completed, and approved experiment `0c21ad16-cebf-4fd0-9d98-e517d4ca6f15` reused TestRun `851cd09b-9966-4e96-afa1-88704231a642` on duplicate approval, completed once, and persisted an `available` comparison plus `inconclusive` result. Raw script and summary files were written to the k6 results directory. PR #58 completed the remaining CI, review, merge, and post-merge verification steps.

- #35: merged in PR #50 (architecture/state groundwork); issue closed with `status:done`.
- #38: merged in PR #51 (findings UI); issue closed with `status:done`.
- #32: merged in PR #54; deterministic comparison contract is the stable handoff for #34/#39.
- #33: implementation merged in PR #55; deterministic suite passes without credentials, and the bounded live adapter is opt-in.
- #36: implementation merged through PR #58; issue closed.
- #34: baseline persistence/comparison API merged in PR #62 and carried to `main` in #63; issue closed.
- #37: timeline merged in PR #60 and carried to `main` in #61; browser evidence recorded in PR #64; issue closed.
- #39: the #32 and #34 dependencies are complete. Its `status:blocked` label is stale; Thato can resume this work.
