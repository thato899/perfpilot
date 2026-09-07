# infrastructure/docker

**Owner:** primarily Developer 2 (k6 runner) and Developer 3 (overall compose wiring) — the top-level `docker-compose.yml` is a shared/root-adjacent file, flag changes before merging (see [CONTRIBUTING.md](../../CONTRIBUTING.md#shared-paths--get-a-second-opinion-before-merging)).

Container definitions for: `web` (Next.js), `api` (FastAPI), `worker` (Celery), `db` (PostgreSQL), `redis`, and `k6-runner`. See [docs/development/local-development.md](../../docs/development/local-development.md#planned-service-layout-infrastructuredocker) for the planned layout.

Not implemented yet — this is Phase 1 work. No production infrastructure is defined in Phase 0 (see [docs/roadmap.md](../../docs/roadmap.md)).
