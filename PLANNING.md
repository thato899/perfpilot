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

Current checkpoint: **2026-09-16**. Hard completion deadline: **2026-09-30**. No Phase 1 feature work should be carried into October.

| Date | Milestone | Tracking |
|---|---|---|
| 2026-09-16 | Checkpoint 1 — **substantially complete**: local stack, AI gateway, k6 script-generation/metrics prototypes, dashboard, Postgres migrations, and API endpoints are on `main`. Remaining: settle metric granularity and complete integration seams. | #1, #6, #9, #10, #11, #12, #14, #15 |
| 2026-09-23 | Integration checkpoint — Orchestrator, Test Planner, Investigator, Celery, k6 execution, and the real API/dashboard path are working together in a local run. | #2, #3, #4, #7, #9, #13, #27 |
| **2026-09-30 — hard deadline** | **Full Phase 1 completion**: the [demo scenario](docs/demo-scenario.md) runs for real, once, start to finish, producing a report a stakeholder could read. | #2, #3, #4, #5, #9, #13, #27 |

Issue numbers above are a planning aid; the [issue board](https://github.com/thato899/perfpilot/issues) is authoritative for task status. Update this table when scope or ownership changes.

## Ownership and next actions

The four developers own independent surfaces, but integration is shared. Each owner should keep their section in [STATUS.md](STATUS.md) current, claim an issue before starting, and request review before changing shared contracts or root configuration.

| Developer | Owns | Next required outcome |
|---|---|---|
| **Thatayaone — AI / Orchestration** | `packages/ai/`, `agents/orchestrator/`, `agents/test-planner/`, `agents/performance-investigator/` | AI provider gateway is implemented on `main`. Next, finish the deterministic orchestrator state machine, fixture-valid Test Planner and Investigator outputs, and the seam Kamogelo's API can call by Sep 23. |
| **Govenor — Performance Engine / Team Lead** | `packages/metrics/`, `agents/load-engineer/`, `infrastructure/docker/k6/` | Settle #9 with Thato by Sep 18, finish k6 runner integration and validate metrics against real k6 JSON by Sep 23. Make the final Phase 1 readiness call by Sep 30. |
| **Kamogelo — Backend / Data** | `apps/api/`, database migrations, canonical `packages/schemas/` ownership | Finish #13 Celery dispatch and connect the worker to the load-engineer wrapper by Sep 23; validate the API-to-orchestrator-to-worker path against Postgres by Sep 30. Approve or coordinate all schema changes. |
| **Thato — Frontend / Reporting** | `apps/web/`, `agents/reporting/` | Complete issue #27: replace mocked runtime calls with the real API, connect report display to real output, preserve fixtures, and run the integrated demo by Sep 30. |

### Integration order

1. Thatayaone publishes stable agent contracts and orchestrator calls.
2. Govenor exposes the safe load-execution/metrics interface and k6 runner.
3. Kamogelo dispatches queued runs through Celery and connects those interfaces in the API.
4. Thato switches the dashboard from mock data to the API and verifies the report flow.
5. Everyone runs the demo scenario, fixes integration defects, and signs off by the 2026-09-30 hard deadline.

## Remaining ticket schedule

The existing role structure does not change. These are the open tickets and the time each owner has to deliver them. All work must be complete by **2026-09-30**.

| Window | Owner | Existing tickets | Required deliverable | Technology stack |
|---|---|---|---|---|
| Sep 16–18 | Govenor + Thato | #9 | Decide summary versus interval metrics and record the decision in the API/dashboard contracts. | Python metrics models, Pydantic schemas, TypeScript dashboard types, Recharts if live charts are retained. |
| Sep 16–23 | Thatayaone | #2, #3, #4, #5 | Implement the deterministic Orchestrator, schema-valid Test Planner and Investigator fixture flows, and validation coverage for all agent contracts. | Python agents, Pydantic contracts in `packages/schemas`, TypeScript/Python `AIService`, Gemini provider. |
| Sep 16–23 | Govenor | #7 plus k6 runner follow-up | Finish safe execution integration, enforce VU/duration/target ceilings, validate real k6 JSON, and provide the runner container path. | Python subprocess wrapper, k6, Docker, JSON metrics parsing, PostgreSQL-compatible result contracts. |
| Sep 16–23 | Kamogelo | #13 | Consume queued `TestRun` records, dispatch the load engineer, persist progress/results, and expose failures through the API. | FastAPI, SQLAlchemy, Alembic/PostgreSQL, Celery, Redis, Docker. |
| Sep 18–30 | Thato | #27 | Replace mocked runtime calls with the real API, connect real investigation/report output, preserve fixtures, and verify the dashboard flow end to end. | Next.js, TypeScript, React, Tailwind/shadcn/ui, Vitest/RTL, FastAPI JSON API. |
| Sep 24–30 | Everyone | #2, #3, #4, #5, #9, #13, #27 | Integrate the full demo scenario, fix cross-surface defects, run CI and local Docker smoke tests, and obtain Team Lead sign-off. | Full stack: Next.js + TypeScript, Python/FastAPI, Pydantic, PostgreSQL, Celery/Redis, k6, Docker. |

### Ticket ownership rule

The issue board remains authoritative. Do not create replacement tickets for #2–#5, #9, #13, or #27. Owners should update their existing issue, keep status labels accurate, and link implementation PRs. A ticket is complete only when its acceptance behavior is demonstrated and the relevant tests/documentation are updated.

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
