# Local Development

**Status:** verified Phase 1 local stack. `infrastructure/docker/docker-compose.yml` stands up the real `db`, `redis`, `web`, `api`, `worker`, and pinned `k6-runner` services. The real Orchestrator/specialists, persistence, Celery execution, k6 metrics, and browser result path have been verified together against a controlled target. See [Running the pieces](#running-the-pieces).

## Prerequisites

- Node.js (LTS) + a package manager (pnpm recommended for workspace support across `apps/web` and any shared TS packages)
- Python 3.11+ with `venv` or `uv`
- Docker + Docker Compose
- [k6](https://k6.io/) CLI installed locally (for running/debugging generated scripts outside Docker during development)
- PostgreSQL and Redis — provided via Docker Compose for local dev; no local install required

## Service layout (`infrastructure/docker`)

| Service | Purpose |
|---|---|
| `web` | Next.js dev server, `apps/web` |
| `api` | FastAPI, `apps/api` (includes agent code from `agents/*` and `packages/*` as installed local packages) |
| `worker` | Celery worker running the same codebase as `api`, for async test execution |
| `db` | PostgreSQL |
| `redis` | Celery broker/result backend |
| `k6-runner` | Container with the k6 binary, invoked by the worker for test execution |

`infrastructure/docker/docker-compose.yml` wires these together (issue #10). It is a **shared path** — flag changes in the team channel before merging, per [CONTRIBUTING.md](../../CONTRIBUTING.md#shared-paths--get-a-second-opinion-before-merging).

Two images support it, both building from the repository root so `apps/api`'s root-relative imports of `packages/schemas` resolve the same way they do in CI:

| Image | Used by | Definition |
|---|---|---|
| `perfpilot-api:local` | `api`, `worker` | `infrastructure/docker/api/Dockerfile` |
| `perfpilot-web:local` | `web` | `infrastructure/docker/web/Dockerfile` |

`k6-runner` is Developer 2/Govenor's ([CODEOWNERS](../../CODEOWNERS)) and
builds from the pinned `grafana/k6:0.57.0` base image. The API/worker image
carries the same pinned k6 binary because the current Load Engineer adapter
invokes k6 as a local subprocess and consumes the shared summary file. The
runner remains useful for direct script validation and version inspection;
spawning a fresh container per run would require mounting the Docker socket
into the worker, which is a meaningful privilege escalation.

### Network layout

Two networks, not one. `perfpilot` carries application traffic (`db`, `redis`, `api`, `worker`, `web`). `perfpilot-targets` carries load-generation traffic and is the only network `k6-runner` sits on, so the load generator has no route to the database or the broker — this is the compose-level half of [security-model.md](../security/security-model.md)'s "k6 running in its own container with network access scoped to the target(s) actually needed". `worker` is on both, because it is what invokes k6.

## Environment setup

1. `cp .env.example .env`
2. Fill in `GEMINI_API_KEY` and/or `DEEPSEEK_API_KEY` depending on `AI_PROVIDER` (see [ADR-004](../decisions/ADR-004-ai-provider-abstraction.md)).
3. Set `ALLOWED_TARGET_HOSTS` to include whatever demo target you're running locally (see [security model](../security/security-model.md#target-authorization)) — PerfPilot will refuse to test anything not listed here, including your own local demo app if you forget to add it.

## Running the pieces

The compose file lives in `infrastructure/docker/`, so run it from there:

```bash
cd infrastructure/docker

docker compose up                     # db + redis — the always-on infra
docker compose --profile backend up   # + api + worker
docker compose --profile frontend up  # + web
docker compose --profile all up       # everything, including k6-runner
```

`db` and `redis` carry no profile, so a bare `docker compose up` starts exactly the two services that are needed most often and work unconditionally. Everything else is gated behind a profile — naming a service directly also starts it, so the shorter forms work too:

```bash
docker compose up api worker          # same as --profile backend
docker compose up web
```

Requires Docker Compose **v2.24+** (the compose file uses `env_file: required: false` so the stack runs before you've created a `.env`).

### What actually works today

| Service | Status |
|---|---|
| `db`, `redis` | Real. Ports 5432/6379 are published, so Alembic and a host-run `uvicorn`/`celery` can reach them without entering a container. |
| `web` | Real Next.js frontend using the same-origin proxy to FastAPI. Source is bind-mounted with `WATCHPACK_POLLING` set, so hot reload works through Docker Desktop's bind mounts. |
| `api` | Real FastAPI service, including the Phase 1 contract endpoints. |
| `worker` | Real Celery worker, registering `perfpilot.execute_test_run` and `perfpilot.ping`. |
| `k6-runner` | Real pinned local image; useful for direct script validation and version inspection. |

### Verified Phase 1 browser E2E

The repo-owned stack was verified with a controlled authorized target using
k6 `v0.57.0`. The browser visibly progressed from `Running` to `Complete`,
rendered a real Finding and persisted Report, and matched API/DB metrics:

- Investigation `ecc197c8-ac5b-41d4-9c96-b61a2186d669`
- TestRun `9585061e-0390-4ed1-9068-c8a8c5804efc`
- throughput `633.2573633816329 req/s`
- p95 `2.0225256 ms`; p99 `2.5756977299999995 ms`
- error rate `0`; capacity `1`

This was a verified healthy run, not the exact DB-pool degradation reference
demo. Do not present it as that scenario.

Smoke-test the full backend path once it's up:

```bash
curl localhost:8000/health
# {"status":"ok"}

docker compose --profile backend exec api \
  python -c "from apps.api.celery_app import ping; print(ping.delay().get(timeout=10))"
# pong
```

The second command is the one worth running: it proves the API container, the broker, the worker and the result backend are all talking to each other, which is the whole point of the wiring.

## Database migrations

Schema lives in two places that must agree: `apps/api/db/models.py` (SQLAlchemy models — what exists in Postgres) and [database-design.md](../database/database-design.md) (the prose source of truth). `packages/schemas/python/entities.py` is the typed contract the API validates against; the models import their enums from it so there's one definition of what `test_type` may contain.

Alembic is configured at `apps/api/alembic.ini` rather than the repository root, and is run **from the repository root** so `apps.api.*` and `packages.*` imports resolve the way they do in CI:

```bash
cd infrastructure/docker && docker compose up -d db && cd ../..

alembic -c apps/api/alembic.ini upgrade head          # apply
alembic -c apps/api/alembic.ini downgrade -1          # roll back one
alembic -c apps/api/alembic.ini current               # what's applied
alembic -c apps/api/alembic.ini upgrade head --sql    # print DDL, don't apply
```

If `alembic` isn't on your PATH (common on Windows — see above), `python -m alembic ...` works identically.

### Changing the schema

1. Edit `apps/api/db/models.py`.
2. `alembic -c apps/api/alembic.ini revision --autogenerate -m "what changed"`.
3. **Read the generated file before committing it.** Autogenerate is a first draft, not an oracle — it doesn't detect table or column *renames* (it emits a drop plus an add, which loses the data), and it never emits `DROP TYPE` for an enum, so any new enum needs a line adding to `downgrade()` by hand. The existing initial migration has that block; copy the pattern.
4. Apply it, then re-run `--autogenerate` once more. A second run that produces an *empty* migration is the proof your models and the database actually agree.

The connection URL comes from `DATABASE_URL` and is never written into `alembic.ini`, so no connection string is committed. `.env.example`'s `postgresql://` URL is rewritten to `postgresql+psycopg://` at runtime — apps/api uses psycopg 3, and SQLAlchemy would otherwise route a bare `postgresql://` to psycopg2, which isn't installed.

## Background jobs

Test execution runs off the request path: `POST /api/tests/{id}/run` returns `202 queued` immediately and a Celery worker picks the run up (issue #13). Nothing happens without a worker — the row just sits `queued`.

```bash
cd infrastructure/docker && docker compose up -d db redis && cd ../..

# from the repository root, same as alembic
celery -A apps.api.celery_app worker --loglevel=info
```

Or let compose run it, which is what the `worker` service is for:

```bash
cd infrastructure/docker && docker compose --profile backend up -d
```

Watch a run go through end to end:

```bash
# trigger one, then poll until it leaves `queued`
curl -s localhost:8000/api/test-runs/$RUN_ID -H "Authorization: Bearer $API_AUTH_SECRET"
```

`queued` → `running` → `succeeded`, with `progress.current_vus` moving off 0 once the worker records stages.

### If a run stays queued forever

Check the worker actually registered the task:

```bash
celery -A apps.api.celery_app inspect registered
```

You want `perfpilot.execute_test_run` in that list, not just `perfpilot.ping`. A worker only knows tasks from modules it has imported, which is why `celery_app.py` names `apps.api.tasks` in `include=` — the API process imports it anyway to call `.delay()`, so this failure is invisible from the API side and shows up only as jobs that never run.

## Working against a demo target

The reference [demo scenario](../demo-scenario.md) expects a small, team-owned application (e.g. a simple e-commerce or quiz app) running locally or in a container, added to `ALLOWED_TARGET_HOSTS`, and registered as a `Target` with `authorization_confirmed: true` before any plan can be run against it (see [security model](../security/security-model.md)).

## Running tests

See [docs/testing/testing-strategy.md](../testing/testing-strategy.md) for the full strategy. Once implementation starts:

- Python: `pytest` per package (`apps/api`, each `agents/*`, `packages/*`)
- TypeScript: the project's configured test runner for `apps/web`
- k6 scripts: validated via `k6 run --dry-run` or equivalent before execution, per [load-engineer.md](../agents/load-engineer.md)

## Checking CI before you push

[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) has seven blocking jobs — `ts-lint`, `ts-format`, `ts-test`, `py-lint`, `py-format`, `py-test`, `build` — plus two that are `continue-on-error` and can't turn a PR red (`py-typecheck`, `audit`). There are two ways to run them before pushing, and they're for different moments.

### Fast loop — the same commands, on your machine

```bash
./scripts/ci-local.sh            # every blocking job
./scripts/ci-local.sh py         # ruff, black, pytest, compileall
./scripts/ci-local.sh ts         # eslint, prettier, vitest, next build
./scripts/ci-local.sh --install  # pip install -r requirements-dev.txt first
```

Seconds to a couple of minutes, and it replicates the workflow's own `git ls-files` guards so a job CI would skip is skipped here too. **Windows: run it in Git Bash**, not PowerShell or cmd.

#### First-run setup on Windows

Three things bite on a fresh Windows checkout. All of them are environment, not repo:

1. **`pip install` works, but the tools still aren't found.** pip drops `ruff.exe`/`black.exe`/`pytest.exe` into a `Scripts\` directory that isn't on PATH, and says so in a warning that's easy to scroll past. The script sidesteps this by calling `python -m ruff` rather than bare `ruff`, so you don't have to fix PATH at all.
2. **`python` runs the Microsoft Store stub.** It prints "Python was not found..." and exits without running anything. The script probes several candidates (`py -3.11`, `python3`, `python`, …) and uses the first that actually executes, so it usually routes around this on its own. If it can't, either turn the alias off under *Settings > Apps > Advanced app settings > App execution aliases*, or point the script at your interpreter: `PERFPILOT_PYTHON="py -3.11" ./scripts/ci-local.sh py`.
3. **pnpm fails with `'...\AppData\Local\pnpm\.tools\...\pnpm' is not recognized`.** pnpm self-installs the version pinned in `package.json`'s `packageManager` field, and that cached copy can land corrupt. Delete it and let pnpm refetch: `rm -rf ~/AppData/Local/pnpm/.tools/pnpm`. Failing that, `corepack enable && corepack prepare pnpm@12.3.4 --activate`.

The tidiest fix for 1 and 2 together is a virtualenv, which also matches the Python version CI pins:

```bash
py -3.11 -m venv .venv
source .venv/Scripts/activate     # Git Bash; PowerShell is .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

`.venv/` is already git-ignored. Worth doing even though the script works without it: CI runs Python 3.11, and a newer local Python can disagree with it on `pytest` in ways `ruff` and `black` won't (their `target-version` is pinned in `pyproject.toml`, so those two behave the same anywhere). The script prints which interpreter it used and warns when it isn't 3.11.

Or run the gates by hand — this is all the script does:

```bash
ruff check .                        # py-lint
black --check .                     # py-format
pytest                              # py-test
python -m compileall -q apps/api    # half of build

pnpm install --frozen-lockfile
pnpm --filter web lint              # ts-lint
pnpm exec eslint packages/schemas/typescript --no-error-on-unmatched-pattern
pnpm run format:check               # ts-format
pnpm --filter web test              # ts-test
pnpm --filter web build             # the other half of build
```

### Faithful run — `act`

The fast loop runs on *your* machine; CI runs on `ubuntu-latest` with Node 20. That gap is not theoretical here — see [.gitattributes](../../.gitattributes) for the CRLF/prettier false-positive it already caused a Windows contributor, and STATUS.md's 2026-09-12 entry for a local Node version that couldn't run the versions of Vitest/jsdom CI installs happily. When the fast loop passes and CI still disagrees, that gap is usually why.

[`act`](https://github.com/nektos/act) runs the real workflow in Linux containers, so it closes it. It needs Docker running.

```bash
winget install nektos.act          # or: choco install act-cli / scoop install act

act -l                             # list the jobs
act pull_request                   # run the PR-triggered jobs
act pull_request -j py-lint        # just one
```

The default runner image is a stripped-down one with no Python or Node, so point act at a fuller image. Put this in `~/.actrc` so you don't retype it:

```text
-P ubuntu-latest=catthehacker/ubuntu:act-latest
```

Two things to expect: the first run pulls a ~1GB image, and the `audit` job's gitleaks step wants a `GITHUB_TOKEN` it won't have. Skip that job — every step in it is `continue-on-error` in real CI anyway, so it can't be what's failing your PR.

### What CI can't tell you

`docker compose` is not exercised by any workflow. Nothing in CI builds the images in `infrastructure/docker/` or starts the stack, so a green PR says nothing about whether the local stack still comes up. Run the smoke commands in [Running the pieces](#running-the-pieces) yourself after changing anything under `infrastructure/docker/`.
