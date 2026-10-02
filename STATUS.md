# PerfPilot status

**2026-10-02 AI runtime update:** PR #81 merged the Python provider bridge
for issues #70, #78, #79, and #80, with real planner/investigator/report
dispatch, bounded calls, typed validation, sanitized audit records, and an
opt-in fixture smoke runner. Main-branch CI and affected-owner review passed;
#70 is closed. A short live Ollama adapter call and Docker worker connectivity
passed. A subsequent
`qwen3:8b` run validated the planner fixture on this CPU host; the
investigator and report fixtures timed out at the 180-second request bound.
Full Ollama evaluation and Gemini/DeepSeek live smoke remain, so #78, #79,
and #80 are still open. Post-merge offline verification passed (72 tests);
the database-backed API suite could not run locally because Docker Desktop's
Linux engine was unavailable.
See [docs/phase3/ai-providers.md](docs/phase3/ai-providers.md).

**Last updated:** 2026-09-30 by Govenor

## UI/UX follow-up

The workspace and investigation report polish pass is available on
`feature/ui-ux-report-polish`. It improves the dashboard hierarchy, explains
single-user test limits, and distinguishes unverified findings from measured
evidence. The next step is review and integration with `main`.

## Current phase

**Phase 1 and Phase 2 are complete. Phase 3 is planned, with all four initial tasks assigned.**

- Phase 1 implementation, backend/browser E2E, and formal sign-off: complete.
- Exact DB-pool reference scenario: **not reproduced**.
- Phase 2 tickets #32–#39: merged to `main`, verified, and closed.
- #39: comparison UI and canonical outcome/threshold response merged in PR #66; all CI checks passed and the issue is closed.
- Phase 3 work is assigned in priority order: Thato #67, Kamogelo #68, Thatayaone #70, then Govenor #71. Each is `status:in-progress` under the repository's assignment/claim workflow.

## Phase 3 assignments

### #68 — frozen run identity

Implementation complete on `feature/p3-api-1-run-identity`. Every new `TestRun`
records the scenario it was accepted to execute, at creation, and that record is
never written again; comparison compatibility reads it and can no longer reach a
mutable `TestPlan`. This closes the limitation #34 shipped knowingly: a plan
edit can no longer change whether an existing result appears comparable.

### #70 — production AI dispatch

The live production path now routes the Test Planner, Performance Investigator,
and Reporting Agent through the existing structured-generation validation seams
when `AI_PROVIDER_ENABLED=true`; default runtime remains offline-safe and
non-provider-backed, so local tests and demos continue without credentials.

Two decisions worth a reviewer's attention, both documented in
[docs/phase3/p3-api-1-run-identity.md](docs/phase3/p3-api-1-run-identity.md):

- **Legacy runs are refused, never reconstructed.** Runs predating the
  migration have no snapshot, and deriving one from a possibly-edited plan
  would manufacture false confidence. They return
  `{baseline,current}_run_identity_unknown`.
- **Clamped runs are refused rather than compared.** A run accepted at 1000 VUs
  and executed at 500 keeps a snapshot saying 1000, so comparing it would read a
  smaller test as an improvement.

The identity stays `v1` — #68 changes where it is read from, not what it
contains — so every baseline selected under #34 remains comparable.

Shared contract: `packages/schemas/typescript/types.ts` gains four additive
`IncompatibleReason` members. Sign-off requested from Thato as the comparison
consumer; #39 and #67 are the affected consumers and should render both new
families as explanations rather than errors.


| Priority | Owner | Issue | Work |
|---|---|---|---|
| 1 | Thato (`thato899`) | [#67](https://github.com/thato899/perfpilot/issues/67) | Export the selected canonical comparison to CSV and JSON |
| 2 | Kamogelo (`Kamogelo-Skhosana`) | [#68](https://github.com/thato899/perfpilot/issues/68) | Snapshot immutable scenario identity on each TestRun — **implementation complete**, PR open |
| 3 | Thatayaone (`Thatayaone910`) | [#70](https://github.com/thato899/perfpilot/issues/70) | Route production agent execution through AIService |
| 4 | Govenor (`malumzz`) | [#71](https://github.com/thato899/perfpilot/issues/71) | Measure run-to-run noise in controlled k6 comparisons — harness and fixture evidence on `feature/p3-metrics-1-run-noise`; comparison semantics unchanged |

Thato's UI task is first and can proceed independently. Kamogelo's backend
task follows it in priority and resolves a comparison reproducibility risk
already identified during #34: a mutable TestPlan can otherwise change the
apparent scenario of an existing TestRun. Thatayaone's next task fills a live
runtime gap: API tasks still call deterministic agent methods while generated
AIService seams exist. Govenor then characterizes repeat-run variability
without changing canonical outcomes. See [roadmap.md](docs/roadmap.md) and
[PLANNING.md](PLANNING.md) for rationale, boundaries, and handoff expectations.

### #71 — run-to-run noise

Implementation is on `feature/p3-metrics-1-run-noise`. The harness repeats one
allow-listed local plan outside the investigation loop, keeps invalid trials
with reasons, and reports p50/p95/p99, throughput, and error-rate spans.
`compare_metrics` is not modified. A within-span p95 illustration and a larger
p95 illustration both come back `regression`, so the current contract does not
separate noise from a material change. Procedure and safety rules:
[docs/phase3/p3-metrics-1-run-noise.md](docs/phase3/p3-metrics-1-run-noise.md).

The new phase-3 doc and the local-development pointer are shared-doc edits and
need a second opinion before merge. A 2026-09-30 local batch of 5 valid trials
on `localhost` with k6 v0.57.0 saw the same plan reported as improvement,
inconclusive, and regression. Raw k6 evidence stays gitignored. Remaining
before #71 is done: CI, review, merge to `main`, and post-merge verification.

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
