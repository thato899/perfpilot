# PLANNING.md

The stable plan: phases, timeline, Definition of Done, where the detail actually lives. This changes rarely — for what's happening *right now*, read [STATUS.md](STATUS.md) instead. For task-level scope, read [docs/roadmap.md](docs/roadmap.md) and [docs/development/next-steps.md](docs/development/next-steps.md); this doc doesn't repeat their content, it dates it and points at it.

**If you are an AI assistant opening this repo for the first time this session:** read this file, then [STATUS.md](STATUS.md), then the [issue board](https://github.com/thato899/perfpilot/issues), in that order, before touching code. That's the whole state of the project.

---

## Where the authoritative detail lives

| Question | Answer lives in |
|---|---|
| What are we building, and why | [README.md](README.md) |
| What's in Phase 1 vs. deferred | [docs/roadmap.md](docs/roadmap.md) |
| Who owns what code | [docs/development/team-workflow.md](docs/development/team-workflow.md#ownership-map) |
| Who owns what *process* (Team Lead, PM, Reviewer, Reporter) | [docs/development/team-roles.md](docs/development/team-roles.md) |
| Per-developer task checklist | [docs/development/next-steps.md](docs/development/next-steps.md) |
| How to claim a task, branch, PR, review | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Testing expectations per layer | [docs/testing/testing-strategy.md](docs/testing/testing-strategy.md) |
| What's happening *right now* | [STATUS.md](STATUS.md) |

## Timeline

Current checkpoint: **2026-09-16**. Hard deadline: **2026-10-07**. Internal integration target: **2026-10-02**.

| Date | Milestone | Tracking |
|---|---|---|
| 2026-09-16 | Checkpoint 1 — **substantially complete**: local stack, AI gateway, k6 script-generation/metrics prototypes, dashboard, Postgres migrations, and API endpoints are on `main`. Remaining: settle metric granularity and complete integration seams. | #1, #6, #9, #10, #11, #12, #14, #15 |
| 2026-09-23 | Checkpoint 2 — Orchestrator + Test Planner produce valid fixture output; k6 execution wrapper enforces safety ceilings; Celery consumes queued runs; API and dashboard integration path is proven. | #2, #3, #7, #8, #13 |
| 2026-09-30 | Checkpoint 3 — the complete Phase 1 slice passes in isolation and in a local integrated run, including report generation and failure-path tests. | #4, #5, #7, #8, #13, #15 |
| **2026-10-02 — internal target** | **Full integration**: the [demo scenario](docs/demo-scenario.md) runs for real, once, start to finish, producing a report a stakeholder could read. This is Phase 1's Definition of Done per [roadmap.md](docs/roadmap.md#phase-1--thin-vertical-slice) — met five days early, deliberately. | — |
| 2026-10-02 → 2026-10-07 | **The 5-day buffer.** For integration bugs found once the pieces actually meet each other, demo rehearsal, and judge-Q&A prep. **Not extra feature time** — pulling new scope into this window is a Team Lead call (Govenor, per [team-roles.md](docs/development/team-roles.md#team-lead--govenor)), not a default. | — |
| **2026-10-07 — hard deadline** | Submission. | — |

Issue numbers above are a planning aid; the [issue board](https://github.com/thato899/perfpilot/issues) is authoritative for task status. Update this table when scope or ownership changes.

## Ownership and next actions

The four developers own independent surfaces, but integration is shared. Each owner should keep their section in [STATUS.md](STATUS.md) current, claim an issue before starting, and request review before changing shared contracts or root configuration.

| Developer | Owns | Next required outcome |
|---|---|---|
| **Thatayaone — AI / Orchestration** | `packages/ai/`, `agents/orchestrator/`, `agents/test-planner/`, `agents/performance-investigator/` | Finish the provider-backed AI service, deterministic orchestrator state machine, fixture-valid Test Planner and Investigator outputs, and structured-output validation. Then expose the seam Kamogelo's API can call. |
| **Govenor — Performance Engine / Team Lead** | `packages/metrics/`, `agents/load-engineer/`, `infrastructure/docker/k6/` | Settle metric granularity with Thato, finish the k6 execution wrapper and safety ceilings, provide the pinned k6 image/runner integration, and validate metrics against real k6 JSON. As Team Lead, make the final Phase 1 scope and readiness calls. |
| **Kamogelo — Backend / Data** | `apps/api/`, database migrations, canonical `packages/schemas/` ownership | Finish Celery dispatch for queued `TestRun` records, connect the worker to the load-engineer wrapper, and validate the API-to-orchestrator-to-worker path against Postgres. Approve or coordinate all schema changes. |
| **Thato — Frontend / Reporting** | `apps/web/`, `agents/reporting/` | Replace mocked dashboard calls with the real API once the integration seam is ready, preserve the working mock fixtures for tests, wire report display to real output, and prepare the demo/rehearsal experience. |

### Integration order

1. Thatayaone publishes stable agent contracts and orchestrator calls.
2. Govenor exposes the safe load-execution/metrics interface and k6 runner.
3. Kamogelo dispatches queued runs through Celery and connects those interfaces in the API.
4. Thato switches the dashboard from mock data to the API and verifies the report flow.
5. Everyone runs the demo scenario, fixes integration defects, and signs off before the 2026-10-02 internal target.

## Definition of Done per phase

- **Phase 0** — done. See [README.md's Phase 0 checklist](README.md#phase-0-definition-of-done), fully checked off.
- **Phase 1** — the demo scenario runs end-to-end for real, once (see table above). Team Lead (Govenor) makes the final call on when it's actually done, not just individually checked off per owner — see [roadmap.md](docs/roadmap.md#phase-1--thin-vertical-slice) and [team-roles.md](docs/development/team-roles.md#team-lead--govenor).
- **Phase 2+** — deliberately not detailed here; see [roadmap.md](docs/roadmap.md#phase-2--investigation-loop-robustness). Out of scope before 2026-10-07.

## Process decisions on record

Written down so a future session doesn't silently re-litigate them:

- **No GitHub branch-protection rules on `main`.** Deliberate team call — this is a group project and the team preferred convention over a hard lock. Enforcement is: PR-based workflow documented in CONTRIBUTING.md, plus `.github/workflows/claim-check.yml` (informational, non-blocking).
- **Claiming a task = self-assigning its GitHub issue.** `.github/workflows/issue-automation.yml` flips `status:todo` → `status:in-progress` automatically on assignment. See [CONTRIBUTING.md#claim-a-task-before-you-start](CONTRIBUTING.md#claim-a-task-before-you-start).
- **One root `pyproject.toml`** configures Ruff/Black/pytest/mypy for the whole Python side of the monorepo, rather than one per package. Simpler while `apps/api`, `agents/*`, `packages/*` don't yet have divergent dependencies. Revisit once they do.
- **`render.yaml` is a template, not an active deployment.** It's correct against `.env.example` and the planned service layout, but points at `apps/api`/`apps/web` code that doesn't exist yet. Kamogelo activates it (see the TODOs inside the file).
- **CI's `audit` stage (dependency + secret scanning) is informational (non-blocking) for now** — nothing is deployed yet, so nothing is currently at stake beyond code hygiene. Revisit once `render.yaml` is actually activated.
- **This PR itself lands as a branch → PR into `main`, not `develop`.** `CONTRIBUTING.md` and `team-workflow.md` describe a `main → develop → feature/*` model, but `develop` has never actually existed in this repo — every commit so far has gone straight to `main`. That's a pre-existing gap between documented process and actual practice, not something this PR resolves unilaterally. The team should decide, deliberately: stand up `develop` for real, or update those two docs to describe what's actually happening (PR-into-`main`). Until decided, treat `main` as the PR target.
