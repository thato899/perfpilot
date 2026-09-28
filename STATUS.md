# PerfPilot status

**Last updated:** 2026-09-28

## Current phase

**Phase 1 and Phase 2 are complete. Phase 3 is planned, with all four initial tasks assigned.**

- Phase 1 implementation, backend/browser E2E, and formal sign-off: complete.
- Exact DB-pool reference scenario: **not reproduced**.
- Phase 2 tickets #32–#39: merged to `main`, verified, and closed.
- #39: comparison UI and canonical outcome/threshold response merged in PR #66; all CI checks passed and the issue is closed.
- Phase 3 work is assigned in priority order: Thato #67, Kamogelo #68, Thatayaone #70, then Govenor #71. Each is `status:in-progress` under the repository's assignment/claim workflow.

## Phase 3 assignments

| Priority | Owner | Issue | Work |
|---|---|---|---|
| 1 | Thato (`thato899`) | [#67](https://github.com/thato899/perfpilot/issues/67) | Export the selected canonical comparison to CSV and JSON |
| 2 | Kamogelo (`Kamogelo-Skhosana`) | [#68](https://github.com/thato899/perfpilot/issues/68) | Snapshot immutable scenario identity on each TestRun |
| 3 | Thatayaone (`Thatayaone910`) | [#70](https://github.com/thato899/perfpilot/issues/70) | Route production agent execution through AIService |
| 4 | Govenor (`malumzz`) | [#71](https://github.com/thato899/perfpilot/issues/71) | Measure run-to-run noise in controlled k6 comparisons |

Thato's UI task is first and can proceed independently. Kamogelo's backend
task follows it in priority and resolves a comparison reproducibility risk
already identified during #34: a mutable TestPlan can otherwise change the
apparent scenario of an existing TestRun. Thatayaone's next task fills a live
runtime gap: API tasks still call deterministic agent methods while generated
AIService seams exist. Govenor then characterizes repeat-run variability
without changing canonical outcomes. See [roadmap.md](docs/roadmap.md) and
[PLANNING.md](PLANNING.md) for rationale, boundaries, and handoff expectations.

## Phase 1/2 verification notes

- Phase 1 sign-off is recorded in PR #48. Runtime and browser E2E were verified.
- #32 established canonical deterministic comparison calculations; downstream
  consumers use its values rather than duplicating metric arithmetic.
- #34 persists an explicitly selected baseline and requires `baseline_id` for
  comparison; it never silently falls back to a recent run.
- #35 supplies durable investigation/event identity and state contracts.
- #36 executes approved follow-up work with authorization and k6 safety limits,
  duplicate-delivery protection, and auditable result persistence.
- #37 and #38 display the authoritative timeline and grounded findings.
- #39 adds the side-by-side baseline/experiment comparison, explicit missing,
  unavailable, incompatible, and inconclusive states, and links to source
  records. Its local Python/web checks, browser pass, and remote CI all passed.
- A separate migration follow-up remains documented for the investigation
  event constraint naming drift noted during #35. It was kept outside #34 and
  is not part of the Phase 3 work currently approved on the roadmap.

## Ownership

| Owner | GitHub | Area |
|---|---|---|
| Thato | `thato899` | Frontend and reporting |
| Kamogelo | `Kamogelo-Skhosana` | Backend, API, data |
| Govenor | `malumzz` | Metrics and k6 execution |
| Thatayaone | `Thatayaone910` | AI and orchestration |
