# PerfPilot status

For current operator setup and authorized target testing steps, see [startup.md](startup.md).

**2026-10-09 follow-up (PRs #96 and #97 merged):** Investigation `8bf039e9-242e-451d-b07c-1524561a7c77` measured 11/11 failed requests because the browser investigation targeted `/`; a read-only worker check returned HTTP 403 there and HTTP 200 at `/login.php`. The cause of the 403 remains undetermined. PR #96 added a selectable GET path and guarded against unsupported causal claims. Investigation `82739980-2f9f-4247-b17f-e2b13e900b24` entered the full login URL into the path field, producing `/https://eduquesttutors.co.za/login.php`. PR #97 accepts same-target URLs and extracts their path. A one-user validation run then saved `/login.php` and completed with 0% errors and p95 84.889 ms; the Gemini planner, investigator, and reporter were all audited as validated. This confirms the public login page works at one virtual user; it does not establish authenticated behavior or capacity.

**Current as of 2026-10-08, based on `main` at `dc4f42a`:** Phase 1, Phase 2, and
the original Phase 3 tickets #67, #68, #70, and #71 are complete. DeepSeek
issue #79 and Gemini issue #80 are both labeled `status:done` and closed. Their
provider implementations, bounded live evaluations, review, CI, merge, and
post-merge verification have passed. No GitHub issue remains open. Docker
Desktop's Linux engine was started for local verification on 2026-10-08.
The full Compose stack started, migrations applied, API and web returned HTTP
200, and the API-to-worker ping returned `pong`. A local database-backed API
suite passed 128 tests on the test-isolation branch using a separate temporary
Postgres database; the temporary database was removed afterward. PR #77
integrated the UI polish. PR #87
merged status reconciliation at `72690be`, PR #88 merged the blocker record at
`1b3d499`, PR #89 merged the `.env` configuration fix at `c081fa0`, and PR #90
merged the DeepSeek closeout documentation at `11239d2`. PR #91 merged the
evaluated Gemini default at `dc4f42a`. See
[docs/phase3/ai-providers.md](docs/phase3/ai-providers.md) for commands, limits,
and provider evidence.

The provider bridge merged as PR #81 (`626494d`) with successful CI and
affected-owner approval; Ollama follow-ups #82–#84 also merged. PR #86
(`c54b9e7`) added URL-secret redaction and selected-cloud dispatch coverage,
with successful CI and affected-owner approval. PR #89 added process-first
root `.env` configuration, DeepSeek's existing `DEEPSEEK_API` alias, and
`AIConfig` repr redaction; Kamogelo approved and all CI checks passed.

Post-merge local checks on `main`: `python -m pytest
packages/ai/test_runtime.py packages/validation agents -q` — 71 passed, 5
collection warnings; `python -m ruff check packages/ai apps/api agents
packages/validation` — passed; `python -m black --check .` — 75 files
unchanged. Final bounded DeepSeek smoke (`deepseek-chat`, 60 seconds, 2048
tokens) validated planner in 2.0s, investigator in 4.4s, and reporting in
3.3s. An earlier post-merge full attempt had planner validate in 2.2s and the
investigator fail after two attempts in 9.4s (`InvestigatorValidationError`);
reporting was not reached. A standalone investigator fixture then validated
in 4.2s before the final full pass. No prompts, responses, or credentials were
recorded. GitHub CI `py-test` passed with its Postgres service. The
untracked staging report in the local workspace is not part of this status
update.

Gemini evaluation on `main` at `11239d2`: with provider `gemini`, an explicit
`gemini-3.5-flash-lite` model, 60-second request timeout, 2048-token limit,
and at most one validation retry per fixture, the complete smoke validated
planner in 12.2s, investigator in 3.9s, and reporting in 2.8s. The old
`gemini-2.5-pro` default returned HTTP 404 on planner in 1.4s; two bounded
`gemini-3.8-flash` attempts each reached a later HTTP 503, and
`gemini-3.6-flash` returned HTTP 503 on planner. These failures were retained
on [issue #80](https://github.com/thato899/perfpilot/issues/80); no provider
fallback or transport retry occurred. No prompts, responses, or credentials
were recorded. The default-model branch passed 72 focused tests, Ruff, Black,
and a bounded smoke using the default model (planner 1.9s, investigator 2.7s,
reporting 3.4s). PR #91 passed all CI checks and received Kamogelo's
affected-owner approval. On merged `main` at `dc4f42a`, 72 focused tests,
Ruff, and Black passed again; the bounded Gemini smoke validated planner in
2.6s, investigator in 2.3s, and reporting in 4.0s. Issue #80 was then manually
labeled `status:done` and closed. GitHub CI `py-test` passed with Postgres.

The first local API test run against a separate Postgres database revealed
that an enabled provider in the developer's ignored `.env` could affect
credential-free API tests. The run was stopped without claiming a pass. This
branch isolates the API suite from the local `.env` and disables live provider
calls by default; the repeated database-backed suite passed 128 tests with
10 warnings. The temporary test database was dropped. Ruff and Black passed;
[PR #92](https://github.com/thato899/perfpilot/pull/92) tracks its CI, review,
and merge state.

**Last updated:** 2026-10-08

## UI/UX follow-up

The workspace and investigation report polish pass merged in PR #77
(`9945bd2`) after affected-owner approval and successful CI. It improves the
dashboard hierarchy, explains single-user test limits, and distinguishes
unverified findings from measured evidence. The branch is an ancestor of
current `main`; no UI polish integration remains outstanding.

## Current phase

**Phase 1, Phase 2, and Phase 3 tickets are complete.** Provider issues #79
and #80 are closed after live evaluation and post-merge verification.

- Phase 1 implementation, backend/browser E2E, and formal sign-off: complete.
- Exact DB-pool reference scenario: **not reproduced**.
- Phase 2 tickets #32–#39: merged to `main`, verified, and closed.
- #39: comparison UI and canonical outcome/threshold response merged in PR #66; all CI checks passed and the issue is closed.
- Original Phase 3 tickets #67, #68, #70, and #71 are merged and closed. DeepSeek follow-up #79 and Gemini follow-up #80 are complete and closed.

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
Provider tickets #79 and #80 extend #70. #79's Definition of Done is met; #80
remains open until its separate Definition of Done is met. See
[roadmap.md](docs/roadmap.md) and [PLANNING.md](PLANNING.md) for the original
rationale and handoff constraints.

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
