# infrastructure/docker

**Owner:** primarily Developer 2/Govenor (k6 runner) and Developer 3/Kamogelo (overall compose wiring) — the top-level `docker-compose.yml` is a shared/root-adjacent file, flag changes before merging (see [CONTRIBUTING.md](../../CONTRIBUTING.md#shared-paths--get-a-second-opinion-before-merging)).

Container definitions for: `web` (Next.js), `api` (FastAPI), `worker` (Celery), `db` (PostgreSQL), `redis`, and `k6-runner`. See [docs/development/local-development.md](../../docs/development/local-development.md#planned-service-layout-infrastructuredocker) for the planned layout and [Running the pieces](../../docs/development/local-development.md#running-the-pieces) for the commands.

## What's here

```text
docker-compose.yml     all six services, profile-gated
api/Dockerfile         perfpilot-api:local — used by both `api` and `worker`
web/Dockerfile         perfpilot-web:local — Next.js dev server
k6/                    Govenor's (CODEOWNERS) — no Dockerfile yet
k6/results/            k6 raw output, git-ignored; bind-mounted into worker + k6-runner
```

Both images build from the **repository root**, not from this directory: `apps/api` imports `packages.schemas.python.*` root-relative (matching `pyproject.toml`'s `pythonpath = ["."]`), so the container has to mirror the repo layout for those imports to resolve. The root `.dockerignore` keeps that context small and keeps `.env` out of every image layer.

## Status

Stood up in issue #10. `db`, `redis` and `web` are fully real. `api` and `worker` boot against scaffolding in `apps/api` (a `/health` route and a no-op Celery task) — enough to prove the wiring, not the Phase 1 endpoints, which are issues #12 and #13.

`k6-runner` is wired into the compose file but has no local image definition: `infrastructure/docker/k6/` belongs to Developer 2/Govenor. The service currently runs the upstream `grafana/k6` image so it starts, and the compose file documents the two decisions left to him — pinning a locally-built image, and whether the worker `exec`s into a long-lived container or spawns one per test run.

No production infrastructure is defined here; deployment is `render.yaml` (see [docs/roadmap.md](../../docs/roadmap.md)).
