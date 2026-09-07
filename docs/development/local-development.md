# Local Development

**Status:** target-state document for Phase 1 setup. No `docker-compose.yml` or install scripts exist yet in Phase 0 — this describes what Developer 3 will stand up first.

## Prerequisites

- Node.js (LTS) + a package manager (pnpm recommended for workspace support across `apps/web` and any shared TS packages)
- Python 3.11+ with `venv` or `uv`
- Docker + Docker Compose
- [k6](https://k6.io/) CLI installed locally (for running/debugging generated scripts outside Docker during development)
- PostgreSQL and Redis — provided via Docker Compose for local dev; no local install required

## Planned service layout (`infrastructure/docker`)

| Service | Purpose |
|---|---|
| `web` | Next.js dev server, `apps/web` |
| `api` | FastAPI, `apps/api` (includes agent code from `agents/*` and `packages/*` as installed local packages) |
| `worker` | Celery worker running the same codebase as `api`, for async test execution |
| `db` | PostgreSQL |
| `redis` | Celery broker/result backend |
| `k6-runner` | Container with the k6 binary, invoked by the worker for test execution |

A `docker-compose.yml` wiring these together is Phase 1 work (see [roadmap.md](../roadmap.md)) — this document exists so whoever writes it starts from an agreed shape instead of inventing one under time pressure.

## Environment setup

1. `cp .env.example .env`
2. Fill in `GEMINI_API_KEY` and/or `DEEPSEEK_API_KEY` depending on `AI_PROVIDER` (see [ADR-004](../decisions/ADR-004-ai-provider-abstraction.md)).
3. Set `ALLOWED_TARGET_HOSTS` to include whatever demo target you're running locally (see [security model](../security/security-model.md#target-authorization)) — PerfPilot will refuse to test anything not listed here, including your own local demo app if you forget to add it.

## Running the pieces (planned)

```bash
docker compose up db redis            # infra only
docker compose up api worker          # backend + async workers
docker compose up web                 # frontend
```

Or `docker compose up` for everything. Exact compose targets/commands will be finalized alongside the actual `docker-compose.yml` in Phase 1.

## Working against a demo target

The reference [demo scenario](../demo-scenario.md) expects a small, team-owned application (e.g. a simple e-commerce or quiz app) running locally or in a container, added to `ALLOWED_TARGET_HOSTS`, and registered as a `Target` with `authorization_confirmed: true` before any plan can be run against it (see [security model](../security/security-model.md)).

## Running tests

See [docs/testing/testing-strategy.md](../testing/testing-strategy.md) for the full strategy. Once implementation starts:

- Python: `pytest` per package (`apps/api`, each `agents/*`, `packages/*`)
- TypeScript: the project's configured test runner for `apps/web`
- k6 scripts: validated via `k6 run --dry-run` or equivalent before execution, per [load-engineer.md](../agents/load-engineer.md)
