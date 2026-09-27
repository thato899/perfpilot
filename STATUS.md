# PerfPilot status


**Last updated:** 2026-09-27 by Thato


## Current phase


**Phase 1 implementation and real E2E complete; Team Lead sign-off granted. Phase 2 #32, #34, #35, #37, and #38 are complete; #39 is no longer blocked on #34.**


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
- #39: #32 and #34 are complete, so the dependency is clear. The issue still carries `status:blocked`; reconcile its board status when Thato resumes work.
- #34: merged in PR #62 and carried to `main` by PR #63; issue closed. Persists a deliberately chosen baseline per target and exposes the comparison API #39 consumes. Every number comes from #32's `compare_metrics`; this layer adds no arithmetic. `baseline_id` is required on the comparison endpoint — there is no fallback to "the most recent run", which is the silent selection the ticket exists to prevent. Review added a stable scenario identity (`apps/api/scenario_identity.py`) so two plans that share a target, type and concurrency but differ in journeys, stages, ramp or duration are refused rather than compared; both targets are now authorized on the comparison route; and a supplied idempotency key is resolved before the already-a-baseline repeat. See [docs/phase2/p2-api-1-baselines.md](docs/phase2/p2-api-1-baselines.md).
- For #35's owner: `--autogenerate` wants to rename four `investigation_event` unique constraints — real pre-existing drift between that migration and the naming convention in `db/base.py` (identical columns, different generated names). Deliberately left alone by #34 as another owner's table; it needs its own fix.
- Follow-up from #34, for whoever owns the run lifecycle: a baseline's scenario identity is frozen at selection time, but the *current* run's is read from its plan live, so editing a plan after runs have executed can make two previously comparable runs incomparable. The fix is to snapshot the scenario onto `test_run` at execution time. Left out of #34 deliberately — it changes the run lifecycle, not this slice.
- #37: **done** — merged in PR #60 and carried to `main` by PR #61. Issue closed with `status:done` on 2026-09-27 after PR #64 recorded the post-merge browser evidence. Renders #35's ordered `events`, `experiment_budget` and typed statuses. All three review findings on the earlier attempt are incorporated: the experiment wording no longer asserts an approval the server has not recorded, terminal snapshots are never marked stale, and the page renders the timeline's loading and reconnect states instead of returning early. See [docs/phase2/p2-ui-1-investigation-timeline.md](docs/phase2/p2-ui-1-investigation-timeline.md).
