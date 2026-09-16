# apps/api

**Owner:** Developer 3/Kamogelo (Backend / Data)

FastAPI backend: HTTP layer, auth, persistence, background job dispatch. Invokes the Orchestrator (`agents/orchestrator`) but contains no agent reasoning itself.

## Layout

```text
main.py          FastAPI app. Currently /health only — endpoints are issue #12.
celery_app.py    Celery app + one no-op task. Real dispatch is issue #13.
db/base.py       Declarative base, constraint naming convention, session factory.
db/models.py     SQLAlchemy models for all 14 entities (issue #11).
alembic.ini      Migration config — run from the REPO ROOT, see below.
alembic/         Migration environment and versions/.
requirements.txt Runtime dependencies for the api and worker containers.
```

Migrations run from the repository root, not from here:

```bash
alembic -c apps/api/alembic.ini upgrade head
```

See [local-development.md#database-migrations](../../docs/development/local-development.md#database-migrations) for the full workflow, including the two things Alembic's autogenerate will not do for you.

The ORM lives here rather than in `packages/schemas` deliberately: that package is the typed *contract* layer (its docstring scopes ORM mapping and persistence out), and it's a shared path needing cross-owner sign-off. The two stay in step because `db/models.py` imports its enums from `packages/schemas` instead of redeclaring them.

## Still to build

The HTTP layer is Phase 1 work (#12/#13). Build against:

- [docs/api/api-contract.md](../../docs/api/api-contract.md) — every endpoint, request/response shape, auth, and error contract
- [docs/database/database-design.md](../../docs/database/database-design.md) — the schema to migrate
- `packages/schemas/python/` — the Pydantic models request/response bodies and persistence must validate against
- [docs/security/security-model.md](../../docs/security/security-model.md) — target authorization and safety-ceiling enforcement points that live at this layer

This app can be built and tested against a stubbed Orchestrator response before the real agents exist — see [docs/development/team-workflow.md](../../docs/development/team-workflow.md#how-the-contracts-enable-parallel-work).
