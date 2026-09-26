# PerfPilot status

**Last updated:** 2026-09-24 by Kamogelo

## Current phase

**Phase 1 implementation and real E2E complete; Team Lead sign-off granted. Phase 2 #32, #35, #36, and #38 are merged; #34 and #37 remain open, and #39 is blocked on #34.**

- Phase 1 implementation: complete.
- Backend and browser E2E: verified.
- Exact DB-pool reference demo: **not reproduced**.
- Phase 1 sign-off: granted by Govenor/Team Lead in PR #48.
- Phase 2 gate: open for the scoped tickets below.
- #35: merged in PR #50 (`27e30b1da5e7450636194e1a82d173258810c7e2`); issue closed with `status:done`.
- #38: merged in PR #51 (`status:done`); consumes the published state contract.
- #32: merged in PR #54; comparison contract is now the stable handoff for #34/#39.
- #36: `status:in-progress` on `feature/p2-runner-1`; approved follow-up execution now persists one deterministic `ExperimentResult` per run.
- #33: implementation complete on `feature/p2-eval-1-agent-evaluation`; PR pending. The deterministic suite passes without credentials, and the bounded live adapter is opt-in.
- #39: `status:todo`; waiting on the #32 comparison contract and baseline/comparison API from #34.
- #34: `status:in-progress` on `feature/p2-api-1-baselines`, PR #62, review feedback addressed. Persists a deliberately chosen baseline per target and exposes the comparison API #39 consumes. Every number comes from #32's `compare_metrics`; this layer adds no arithmetic. `baseline_id` is required on the comparison endpoint — there is no fallback to "the most recent run", which is the silent selection the ticket exists to prevent. Review added a stable scenario identity (`apps/api/scenario_identity.py`) so two plans that share a target, type and concurrency but differ in journeys, stages, ramp or duration are refused rather than compared; both targets are now authorized on the comparison route; and a supplied idempotency key is resolved before the already-a-baseline repeat. See [docs/phase2/p2-api-1-baselines.md](docs/phase2/p2-api-1-baselines.md).
- For #35's owner: `--autogenerate` wants to rename four `investigation_event` unique constraints — real pre-existing drift between that migration and the naming convention in `db/base.py` (identical columns, different generated names). Deliberately left alone by #34 as another owner's table; it needs its own fix.
- Follow-up from #34, for whoever owns the run lifecycle: a baseline's scenario identity is frozen at selection time, but the *current* run's is read from its plan live, so editing a plan after runs have executed can make two previously comparable runs incomparable. The fix is to snapshot the scenario onto `test_run` at execution time. Left out of #34 deliberately — it changes the run lifecycle, not this slice.
- #37: **done** — merged in PR #60 and present on both `develop` and `main`. Renders #35's ordered `events`, `experiment_budget` and typed statuses. All three review findings on the earlier attempt are incorporated: the experiment wording no longer asserts an approval the server has not recorded, terminal snapshots are never marked stale, and the page renders the timeline's loading and reconnect states instead of returning early. See [docs/phase2/p2-ui-1-investigation-timeline.md](docs/phase2/p2-ui-1-investigation-timeline.md).

P2-EVAL-1 review note: deterministic tests, Python lint/format, documentation,
and `STATUS.md` are updated. Because the change touches `docs/` and root
`pyproject.toml`, a second opinion from another owner remains required before
merge.

## Phase 2 ownership

| Owner | GitHub | Tickets | Primary area |
|---|---|---|---|
| Thato | `thato899` | #35, #38, #39 | investigation state and frontend integration |
| Kamogelo | `Kamogelo-Skhosana` | #34, #37 | data/API and timeline integration |

## Govenor — #36 progress

The worker execution boundary consumes the approved Experiment and linked
TestRun from #35, refuses duplicate delivery, re-checks target authorization,
enforces the configured k6 safety limits, persists raw/script references and
Metric rows, and now persists exactly one `ExperimentResult` containing the
typed comparison from #32. The Load Engineer contract documents the lifecycle,
failure states, idempotency, and audit requirements. Also fixed the runtime
boundaries so a new investigation records its baseline run ID and approval
events contain the flushed Experiment ID.

Validation on `feature/p2-runner-1`: focused API/worker regression tests pass
(`3 passed`), earlier worker/metrics coverage passed (`24 passed`), the full
Python suite passed before the live smoke (`134 passed`), and Ruff/Black passed
on touched Python files. Real Docker evidence is now complete: API health
returned 200, worker k6 reported `v0.57.0`, baseline run
`f79dccc5-6d25-4aaa-b50d-783b854ac939` completed, and approved experiment
`0c21ad16-cebf-4fd0-9d98-e517d4ca6f15` reused TestRun
`851cd09b-9966-4e96-afa1-88704231a642` on duplicate approval, completed once,
and persisted an `available` comparison plus `inconclusive` result. Raw script
and summary files were written to the k6 results directory. Remaining before
#36 is done: CI, review, merge to `main`, and post-merge verification.
- #35: merged in PR #50 (architecture/state groundwork); issue closed with `status:done`.
- #38: merged in PR #51 (findings UI); issue closed with `status:done`.
- #32: merged in PR #54; deterministic comparison contract is the stable handoff for #34/#39.
- #33: implementation merged in PR #55; the deterministic suite passes without credentials, and the bounded live adapter is opt-in.
- #36: merged through PR #58; approved follow-up execution persists one deterministic `ExperimentResult` per run.
- #34: Kamogelo's baseline persistence/comparison API; PR #62 open, retargeted to `develop`, review feedback addressed (scenario identity, baseline-target authorization, idempotency-key ordering). Awaiting re-review and the shared-contract sign-off for `packages/schemas/typescript/types.ts`; not yet merged.
- #37: Kamogelo's investigation timeline; **merged in PR #60** and on `develop` and `main`. (An earlier attempt, PR #53, was closed without merge after review; the feedback is incorporated in #60.)
- #39: `status:blocked`; #32 is merged, but the baseline/comparison API from #34 is still outstanding.
