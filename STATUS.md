# STATUS.md

The **live** state of the project. This changes every session — for the stable plan/timeline, see [PLANNING.md](PLANNING.md).

**If you are an AI assistant opening this repo for a session: read this file before doing anything else.** It tells you what's currently being worked on, what's blocked, and what's next — the things a fresh chat tab has no way to know otherwise. Before you end your session (or hand off), update your developer's section below and add a line to the log. This is the whole point of the file: it only works if it stays current.

**Last updated:** 2026-09-14 by Kamogelo 

---

## Per-developer status

Each section below follows the same template. Update your own section — don't edit someone else's without flagging it with them first (same rule as touching their code, see [CONTRIBUTING.md](CONTRIBUTING.md#what-not-to-do)).

### Thatayaone — AI / Orchestration

**Last updated:** — not yet logged

- **Currently working on:**
- **Just completed:**
- **Blocked on:**
- **Next up:** claim an issue from [docs/development/next-steps.md#thatayaone--developer-1-ai--orchestration](docs/development/next-steps.md#thatayaone--developer-1-ai--orchestration) — start with `packages/ai` (#1), it's the one thing everyone else's agents import.

### Govenor — Performance Engine

**Last updated:** — not yet logged

- **Currently working on:**
- **Just completed:**
- **Blocked on:**
- **Next up:** claim an issue from [docs/development/next-steps.md#govenor--developer-2-performance-engine](docs/development/next-steps.md#govenor--developer-2-performance-engine); also owns unblocking [issue #9](https://github.com/thato899/perfpilot/issues/9) (interval vs. summary metrics) early — see Thato's proposal there, needs your read.

### Kamogelo — Backend / Data

**Last updated:** 2026-09-16 by Kamogelo

- **Currently working on:** issue #12 (`apps/api` endpoints) — branch `feature/api-endpoints`, stacked on #11's branch. #10 and #11 both have PRs open awaiting review.
- **Just completed:** the local stack. `infrastructure/docker/docker-compose.yml` with all six planned services, profile-gated so a bare `docker compose up` starts `db` + `redis` (which is what #11 and #13 need) and `--profile all` brings up everything. Two Dockerfiles (`infrastructure/docker/api/`, `.../web/`), a root `.dockerignore`, and the minimum `apps/api` scaffolding needed for the `api`/`worker` containers to actually boot: `requirements.txt`, `main.py` (`/health` only), `celery_app.py` (one no-op `perfpilot.ping` task). Validated with `docker compose config` across every profile, and the repo's own CI gates (`ruff check .`, `black --check .`, `pytest`, `compileall apps/api`) all pass with the new files in place.
- **Blocked on:** nothing. Two things are *waiting on other owners* rather than blocking me: `k6-runner` runs an unpinned upstream `grafana/k6` image until Govenor writes `infrastructure/docker/k6/Dockerfile`, and the `perfpilot-targets` network is a plain bridge rather than `internal: true` because locking egress down depends on whether the demo target runs on the host or as a container — also his call. Both are written up in the compose file's comments, not just here.
- **Next up:** #13 (Celery) — the last of my four. `POST /api/tests/{id}/run` already persists a `queued` TestRun; #13 is what consumes it, and the task it dispatches is Govenor's k6 wrapper. Still the one who activates `render.yaml`; note the module paths in its TODOs (`rootDir: apps/api`, `main:app`, `app.celery_app`) are wrong for this repo — see the 09-14 log entry.
- **Unblocks Thato:** every endpoint `apps/web`'s `mock-api.ts` mirrors now exists for real, so the dashboard's mocked layer can be swapped for `fetch` calls whenever he wants it.

**Needs a second opinion before merge (shared paths, per [CONTRIBUTING.md](CONTRIBUTING.md#shared-paths--get-a-second-opinion-before-merging)):** `infrastructure/docker/docker-compose.yml` and the root `.dockerignore` (#10), `docs/development/local-development.md`, `docs/api/api-contract.md`, and **`.github/workflows/ci.yml`** (#12 — adds a Postgres service and an apps/api dependency install to `py-test`; that one touches everyone's CI, so please read it before merging). Govenor is the right reviewer for the docker half; anyone for the CI change.

### Thato — Frontend / Reporting

**Last updated:** 2026-09-13 by Thato (Claude Code)

- **Currently working on:** nothing active — both PRs are merged into `main` (PR #18/issue #14 at 18:58, PR #17/issue #15 at 19:23 on 2026-09-12), CI green on both merge commits. Everything in next-steps.md's Thato backlog that doesn't depend on a teammate is done; see next-steps.md's Thato section for the exact per-item status.
- **Just completed:** Dashboard (issue #14, PR #18, merged) — `apps/web`: Next.js + TypeScript + Tailwind + shadcn/ui, all four required flows (create target / trigger investigation / watch progress / view report) working against a mocked API (`src/lib/mock-api.ts`, `localStorage`-backed). Verified end to end with a scripted headless-browser run (screenshots + console-error check), not just `next build`. Found a schema gap (`types.ts` had no `ExpectedTraffic`) and fixed it. Tightened CI: `ts-lint` now runs `apps/web`'s own Next.js-flavored eslint config instead of only the generic root one. Added a real automated test suite — Vitest + React Testing Library (`apps/web/README.md#testing`), 21 tests covering `mock-api.ts`'s full behavior (target creation/rejection, tick-by-tick investigation advance to a completed report, finding/hypothesis timing) and the severity/status badge components — plus a new `ts-test` CI job (guarded the same way `ts-lint`/`ts-format` are). This closed the "automated frontend tests" gap the PR originally shipped with flagged as not-yet-done. (Separately, and in parallel: Reporting Agent, issue #15, PR #17, also merged — see that PR/branch for details, not duplicated here.)
- **Blocked on:** nothing for this fixture/mock-first slice. Wiring the dashboard to a real API needs `apps/api` (#12) — noted as a "Not yet done" item in `apps/web/README.md`, not a current blocker since mock-first was the explicit Phase 1 scope.
- **Next up:** proposed a recommendation on [issue #9](https://github.com/thato899/perfpilot/issues/9) (summary-at-completion over interval-bucketed metrics, for Phase 1) — still open, waiting on Govenor's read before treating it as settled; this is the one open item that's genuinely not mine to close. Otherwise: pick up the next unclaimed `dev:thato` issue once one exists (none currently unclaimed), or help review a teammate's PR (none currently open).

---

## Log

Reverse-chronological. One entry per session — a couple of lines, not a full changelog (the git history and issue board are that).

### 2026-09-16 — Kamogelo

- Issue #12: `apps/api` HTTP layer. All **13** endpoints in api-contract.md, not just the four groups the issue title names — the done-when says "every listed endpoint matches its documented request/response shape", and the extra ones are thin enough that leaving them half-built would have been the worse trade.
- Built against a stub Orchestrator (`apps/api/orchestrator_stub.py`) injected through `deps.get_orchestrator()`. That function is the only place naming an Orchestrator implementation, so Thatayaone's real one replaces it without touching a router. The stub returns payloads that *validate against packages/schemas* rather than plausible-looking dicts, so a contract change there fails these tests instead of surfacing at integration.
- Security-model gates are enforced and tested: `authorization_confirmed` required (422) and the `ALLOWED_TARGET_HOSTS` check (403) are independent, and confirmation is checked *first* so an unconfirmed request for an arbitrary host doesn't learn which hosts are allow-listed. Authorization is re-checked at run time, not trusted from target creation. The VU and duration ceilings return 429.
- Every failure goes through one envelope. FastAPI's defaults don't produce the documented `{"error": {...}}` shape — `HTTPException` gives `{"detail": ...}` and a validation failure gives a bare list — so all three are re-wrapped. There's a test asserting a 422 body parses like every other error.
- **46 endpoint tests, run against real Postgres.** SQLite was not an option: the models use JSONB and native Postgres enums, so it would be testing a schema that never ships. Also booted the app under `uvicorn apps.api.main:app` (the container's actual CMD) and drove the full demo flow over HTTP, not just through TestClient.
- **CI change, please review:** `py-test` now runs a `postgres:16-alpine` service and installs `apps/api/requirements.txt`. Without the install every apps/api test would skip itself and the job would pass while testing nothing — which is the gap I flagged in #11's entry. `.github/` is a shared path.
- Two contract clarifications, both written into api-contract.md rather than left in code: `POST /api/tests/plan` needs `project_id`/`target_id` beyond what `TestPlanRequest` carries (it has a target *description*, no ids); and the 429 rule's "…and the plan wasn't already clamped" qualifier has no field to hang on — `clamped` is a TestRun column and no run exists at approval time. Implemented as a straight ceiling check; flagged as an open question.
- Known gaps, deliberate: `POST /api/tests/{id}/run` persists a `queued` TestRun but dispatches nothing (#13). `POST .../experiments` reuses the target's latest plan instead of asking the Test Planner for a follow-up, so the FK chain is real rather than dangling — #13 replaces that. `current_vus` in run progress reads the last recorded stage, which is 0 until the worker writes stages; it reports what's known rather than interpolating.

### 2026-09-14 — Kamogelo, second session

- Issue #11: Postgres schema. SQLAlchemy models for all 14 entities in `apps/api/db/models.py`, a declarative base with a constraint naming convention in `apps/api/db/base.py`, and an Alembic environment at `apps/api/alembic.ini` + `apps/api/alembic/`. `alembic.ini` deliberately sits under `apps/api`, not the repo root (root config is a shared path), and runs from the root so `apps.api.*`/`packages.*` imports resolve as they do in CI.
- Enums are **imported** from `packages/schemas/python/entities.py` rather than redeclared, so there's one definition of what `test_type` may contain. Needed `values_callable` on every `sa.Enum`: SQLAlchemy's default persists the Python member *name* (`LOAD`), while Pydantic serializes the *value* (`load`) — without it the database and every JSON payload would disagree, and only on first read-back.
- Verified against a real Postgres 16 (same major as the compose `db` service), not just written: applies to a genuinely fresh database; schema matches database-design.md column by column across all 14 entities (scripted audit); `--autogenerate` run a second time produces an empty migration, proving models and schema agree; two full down/up cycles are clean; a full investigation graph inserts across every layer, with the confidence CHECK and the one-report-per-investigation constraint both rejecting bad rows.
- **Bug found and fixed in the process:** Alembic emits `CREATE TYPE` for enum columns on the way up but never `DROP TYPE` on the way down, so the first downgrade left all nine types orphaned and the next `upgrade` died on "type test_type already exists". `downgrade()` now drops them explicitly. Anyone adding an enum column later has to add a line there too — written up in local-development.md#changing-the-schema.
- Judgement calls worth a reviewer's eye: `TestStage` got a `UNIQUE(test_run_id, sequence_index)` that database-design.md doesn't state but "sequence" implies; `Investigation`'s active-status partial index is written as `NOT IN ('complete','failed')` rather than listing the five in-flight statuses, so a status added later is treated as active by default; and the ER diagram's many-to-many Investigation↔TestRun edge is *not* materialised as a join table, because the normative Entities section defines only the two nullable FK columns.
- No tests added, same reason as #10: CI installs only `requirements-dev.txt`, which has no SQLAlchemy, and a migration test needs a live database CI doesn't have. #12 has to solve the CI-dependencies problem; a `services: postgres` block in the py-test job would then make migration tests possible.

### 2026-09-14 — Kamogelo

- Issue #10: stood up `infrastructure/docker/docker-compose.yml` with all six services from local-development.md's planned layout, plus `infrastructure/docker/{api,web}/Dockerfile` and a root `.dockerignore`. Both images build from the repo root, because `apps/api` imports `packages.schemas` root-relative and the container has to mirror that or the imports break.
- Used compose **profiles** rather than shipping six services that half-fail: `db` + `redis` have no profile and start on a bare `docker compose up`; `api`/`worker` sit behind `backend`, `web` behind `frontend`, `k6-runner` behind `k6`, and everything is also in an `all` profile for the #10 done-when check. The reasoning is that #11 and #13 need a database and a broker *today*, and making someone wait through a pnpm install to get them is friction for no benefit.
- Wrote the minimum `apps/api` scaffolding for the containers to genuinely boot — `requirements.txt`, `main.py` with only `GET /health`, `celery_app.py` with one no-op `perfpilot.ping` task. This is deliberately *not* issue #12/#13 work: it's boot scaffolding, because a compose file whose services can't start isn't wiring. `ping.delay().get()` round-tripping through Redis is the smoke test that proves the whole backend path at once (command in local-development.md).
- Put `k6-runner` on its own network (`perfpilot-targets`) with no route to `db`/`redis`, which is the compose-level half of security-model.md's "k6 ... network access scoped to the target(s) actually needed, not open egress". Left two decisions to Govenor in comments rather than guessing: pinning a locally-built k6 image (his folder, his version choice), and whether `perfpilot-targets` should be `internal: true` — that depends on whether the demo target runs on the host or as a container.
- **Found, not fixed:** `render.yaml`'s TODOs assume `rootDir: apps/api` with `uvicorn main:app` and `celery -A app.celery_app`. Those are wrong for this repo — with `apps/api` as the root, `packages.schemas` imports don't resolve. The correct paths are `apps.api.main:app` and `apps.api.celery_app` from the repo root. Not changed here (activating `render.yaml` is separate work on a shared root file); flagged in `apps/api/celery_app.py`'s docstring so whoever does it sees it in context.
- **Also flagged:** `requirements-dev.txt`'s comment says pydantic should move to `apps/api`'s runtime deps "once apps/api declares its own". It now does, and pydantic is listed there — but CI still installs only `requirements-dev.txt`, so removing it there would break `py-test`. Left in both deliberately. Consolidating that (and adding fastapi to whatever CI installs, which #12 will need for its tests) is a separate change to a shared root file.
- **Not verified:** `docker compose up` has not actually been executed against this branch — only `docker compose config` across every profile. First person with Docker running should do the two smoke commands in local-development.md before #10 is closed. No workflow exercises compose either, so a green PR says nothing about it. The CI gates themselves (`ruff`, `black`, `pytest` — 15 tests including Thato's merged reporting-agent suite, `compileall`) were run locally and pass.
- Added `scripts/ci-local.sh` along the way — runs the seven blocking CI jobs locally with the workflow's own skip guards, since a PR is a slow place to discover a lint failure. Not part of #10; drop it if the team would rather it were separate. Documented in local-development.md, along with three Windows-specific setup traps it works around (pip's `Scripts\` not on PATH, the Microsoft Store `python` stub, and a corrupt self-installed pnpm).
- **#10 stays open** until `api`/`worker` serve real endpoints (#12/#13) and Govenor's k6 image lands — the done-when is "`docker compose up` brings up every planned service", and three of them are still standing in for something.

### 2026-09-13 — Thato (Claude Code)

- Doc sync only, no code changes: `main` had moved on since this file was last written (PR #18/issue #14 and PR #17/issue #15 both merged 2026-09-12 evening, CI green on both), but this file and `next-steps.md` still read as if the PRs were open and the Reporting Agent checkbox unstarted. Updated both to reflect merged state, dropped the now-resolved "expect a merge conflict here" note, and checked off next-steps.md's Reporting Agent line.
- Confirmed via `gh`: no open PRs, no unclaimed `dev:thato` issues, issue #9 still open awaiting Govenor's read on the proposal from 2026-09-12. Nothing else currently blocking or actionable on my end.

### 2026-09-12 — Thato (Claude Code), second session

- Went back through next-steps.md's Thato backlog end to end to check what was actually left undone (vs. blocked on a teammate). Everything not dependent on another owner was already done from the first session (#14, #15); the two genuinely-blocked items — issue #9 (needs Govenor) and real API/agent wiring (needs #12/#2/#4) — are correctly left alone, not forced.
- Found one real gap that was mine to close: no automated frontend test suite (apps/web/README.md had flagged this as "not yet done"). Added Vitest + React Testing Library (21 tests: `mock-api.ts`'s full behavior including the tick-by-tick investigation lifecycle, plus the severity/status badge components) and a guarded `ts-test` CI job, same pattern as `ts-lint`/`ts-format`. Landed on the existing `feature/dashboard-mocked-api` branch (PR #18, still open/unmerged) since it directly closes that PR's own flagged gap.
- Hit three real toolchain snags getting the suite running locally (documented in `apps/web/README.md#testing` so the next person doesn't rediscover them): Vitest 5/`@vitejs/plugin-react` 6/jsdom 30 all assume a Node newer than this machine's local 20.11 (missing `node:util`'s `styleText`, and an ESM-only jsdom sub-dependency) — pinned to `vitest@3.2.7`, `vite@6.4.3`, `@vitejs/plugin-react@4.7.0`, `jsdom@25.0.1` instead. Also had to flip `pnpm-workspace.yaml`'s `esbuild` build-script gate from its placeholder to `true` (Vite can't run without esbuild's native binary) — unlike `sharp`/`unrs-resolver`, this one isn't optional. None of this should affect CI, which installs a newer Node 20.x via `actions/setup-node@v4`.
- Updated `docs/development/next-steps.md` (Thato's dashboard checkbox note) and `apps/web/README.md` (moved "automated frontend tests" out of "Not yet done", added a Testing section) to match.

### 2026-09-12 — Thato (Claude Code)

- Claimed and completed issue #14 (dashboard): scaffolded `apps/web` (Next.js 16, TypeScript, Tailwind v4, shadcn/ui), built the mock API layer + fixtures, and all four required views. Verified with a real headless-browser run end to end (not just a type-check) — screenshots confirm the home page, target selection, live progress ticking 0 → 1000 VUs, and the final report all render correctly with no console errors.
- Along the way: installed `pnpm` globally (was only reachable via `npx pnpm@version` before — `create-next-app`/`shadcn` both shell out to a bare `pnpm` on PATH) and Playwright's Chromium build, for local verification; neither is a repo dependency. Found a schema gap (`types.ts` had no `ExpectedTraffic`) and fixed it. Tightened `ts-lint` in CI to run `apps/web`'s own Next.js-flavored eslint config (`eslint-config-next`) instead of only the generic root one, which wasn't actually exercising React/Next-specific rules.
- Posted a proposed recommendation on issue #9 (summary-at-completion over interval-bucketed metrics) rather than deciding it unilaterally — it's a joint call with Govenor per roadmap.md.
- Also claimed and completed issue #15 (Reporting Agent) this same session — see PR #17 / the `feature/reporting-agent-fixture` branch for that entry, kept separate since it's a separate PR.

### 2026-09-09 — Thato (Claude Code)

- Set up the Phase 1 engineering process: 8-stage CI pipeline (lint/format/typecheck/test/build/audit for TS+Python, guarded so it's green today and activates automatically as code lands), issue-claim automation (self-assign flips `status:todo`→`status:in-progress`; a non-blocking `claim-check` flags PRs closing unclaimed issues), issue/PR templates, `CODEOWNERS`, root Python/JS tooling configs, real smoke tests for `packages/schemas/python`, a `render.yaml` deployment template for the full planned stack, and this file + `PLANNING.md`.
- Ran `ruff --fix`/`black`/`prettier --write` once against the pre-existing `packages/schemas/python/{entities,agent_io}.py` and `packages/schemas/typescript/types.ts` so the new lint/format CI jobs start green — import ordering, blank lines, and union-type line-wrapping only, no behavior change. Flagged here since `packages/schemas/` is Kamogelo's owned/shared path — worth a glance next session, not a blocker.
- No branch protection applied (team's explicit call — see `PLANNING.md`'s process-decisions section). Landed as a PR, not a direct push to `main`.

---

## Quick links

[PLANNING.md](PLANNING.md) · [Issue board](https://github.com/thato899/perfpilot/issues) · [CONTRIBUTING.md](CONTRIBUTING.md#claim-a-task-before-you-start)
