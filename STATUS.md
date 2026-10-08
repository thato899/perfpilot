# PerfPilot status

**Current as of 2026-10-08, on `main` at `c54b9e7`:** Phase 1, Phase 2, and
the original Phase 3 tickets #67, #68, #70, and #71 are complete. The only
open GitHub issues are #79 (DeepSeek) and #80 (Gemini). Their Python provider
implementations are merged, but each issue requires a bounded live evaluation
of all three fixtures before it can close. Both evaluations are blocked on
cloud credentials not present in this process environment. Docker Desktop's
Linux engine is also unavailable, so no local database-backed API run is
claimed. PR #77 integrated the UI polish; that branch is already contained in
`main`. See [docs/phase3/ai-providers.md](docs/phase3/ai-providers.md) for
commands, limits, and prior Ollama evidence.

The provider bridge merged as PR #81 (`626494d`) with successful CI and
affected-owner approval; Ollama follow-ups #82–#84 also merged. PR #86
(`c54b9e7`) added URL-secret redaction and selected-cloud dispatch coverage,
with successful CI and affected-owner approval. The documented credential-free
provider suite passes locally (69 tests), Ruff passes, and repository-wide
Black check passes (75 files). A repository-wide pytest attempt did not finish
and was interrupted without a result; it is not counted as verification.
GitHub currently shows no open PRs. The untracked staging report in the local
workspace is not part of this status update.

**Last updated:** 2026-10-08

## UI/UX follow-up

The workspace and investigation report polish pass merged in PR #77
(`9945bd2`) after affected-owner approval and successful CI. It improves the
dashboard hierarchy, explains single-user test limits, and distinguishes
unverified findings from measured evidence. The branch is an ancestor of
current `main`; no UI polish integration remains outstanding.

## Current phase

**Phase 1, Phase 2, and the original Phase 3 tickets are complete.** The
separate cloud-provider evaluations in #79 and #80 remain open.

- Phase 1 implementation, backend/browser E2E, and formal sign-off: complete.
- Exact DB-pool reference scenario: **not reproduced**.
- Phase 2 tickets #32–#39: merged to `main`, verified, and closed.
- #39: comparison UI and canonical outcome/threshold response merged in PR #66; all CI checks passed and the issue is closed.
- Original Phase 3 tickets #67, #68, #70, and #71 are merged and closed. Provider follow-ups #79 and #80 are separately tracked and remain open pending live cloud evaluations.

## Phase 3 completion record

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

Two implementation decisions, both documented in
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

Shared contract: `packages/schemas/typescript/types.ts` gained four additive
`IncompatibleReason` members. The comparison consumer reviewed the change;
#39 and #67 render both new families as explanations rather than errors.


| Priority | Owner | Issue | Work |
|---|---|---|---|
| 1 | Thato (`thato899`) | [#67](https://github.com/thato899/perfpilot/issues/67) | Export the selected canonical comparison to CSV and JSON — merged and closed |
| 2 | Kamogelo (`Kamogelo-Skhosana`) | [#68](https://github.com/thato899/perfpilot/issues/68) | Snapshot immutable scenario identity on each TestRun — merged and closed |
| 3 | Thatayaone (`Thatayaone910`) | [#70](https://github.com/thato899/perfpilot/issues/70) | Route production agent execution through AIService — merged and closed |
| 4 | Govenor (`malumzz`) | [#71](https://github.com/thato899/perfpilot/issues/71) | Measure run-to-run noise in controlled k6 comparisons — merged and closed; comparison semantics unchanged |

The original ticket order and rationale are retained here as history. All four
are complete; see their merged PRs and closed issues for delivery details.
Provider tickets #79 and #80 extend #70 and remain open for the required live
evaluations. See [roadmap.md](docs/roadmap.md) and [PLANNING.md](PLANNING.md)
for the original rationale and handoff constraints.

### #71 — run-to-run noise

Implementation merged in PR #75. The harness repeats one
allow-listed local plan outside the investigation loop, keeps invalid trials
with reasons, and reports p50/p95/p99, throughput, and error-rate spans.
`compare_metrics` is not modified. A within-span p95 illustration and a larger
p95 illustration both come back `regression`, so the current contract does not
separate noise from a material change. Procedure and safety rules:
[docs/phase3/p3-metrics-1-run-noise.md](docs/phase3/p3-metrics-1-run-noise.md).

The phase-3 doc and local-development pointer were reviewed and merged with
the work. A 2026-09-30 local batch of 5 valid trials
on `localhost` with k6 v0.57.0 saw the same plan reported as improvement,
inconclusive, and regression. Raw k6 evidence stays gitignored. CI, review,
merge, and post-merge verification are complete for #71; the issue was closed
on 2026-09-30.

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
