# infrastructure/docker

**Owner:** primarily Developer 2/Govenor (k6 runner) and Developer 3/Kamogelo (overall compose wiring) — the top-level `docker-compose.yml` is a shared/root-adjacent file, flag changes before merging (see [CONTRIBUTING.md](../../CONTRIBUTING.md#shared-paths--get-a-second-opinion-before-merging)).

Container definitions for: `web` (Next.js), `api` (FastAPI), `worker` (Celery), `db` (PostgreSQL), `redis`, and `k6-runner`. See [docs/development/local-development.md](../../docs/development/local-development.md#service-layout-infrastructuredocker) for the layout and [Running the pieces](../../docs/development/local-development.md#running-the-pieces) for the commands.

## What's here

```text
docker-compose.yml     all six services, profile-gated
api/Dockerfile         perfpilot-api:local — used by both `api` and `worker`
web/Dockerfile         perfpilot-web:local — Next.js dev server
k6/                    Govenor's (CODEOWNERS) — pinned k6 runner image
k6/results/            k6 raw output, git-ignored; bind-mounted into worker + k6-runner
```

Both images build from the **repository root**, not from this directory: `apps/api` imports `packages.schemas.python.*` root-relative (matching `pyproject.toml`'s `pythonpath = ["."]`), so the container has to mirror the repo layout for those imports to resolve. The root `.dockerignore` keeps that context small and keeps `.env` out of every image layer.

## Status

The stack includes real Postgres, Redis, FastAPI endpoints, Celery execution,
the production Load Engineer adapter, and the pinned k6 runtime. The API and
worker share the same image; the worker consumes `perfpilot.execute_test_run`.
The end-to-end k6 smoke still requires an authorized controlled target and a
host/port configuration without conflicts.

`k6-runner` is owned by Developer 2/Govenor and builds from the pinned local image definition at `infrastructure/docker/k6/Dockerfile`. The service runs idle and the worker invokes k6 with `docker compose exec`; the alternative of spawning a fresh container per run would require mounting the Docker socket into the worker.

No production infrastructure is defined here; deployment is `render.yaml` (see [docs/roadmap.md](../../docs/roadmap.md)).
