# apps/api

**Owner:** Developer 3/Kamogelo (Backend / Data)

FastAPI backend: HTTP layer, auth, persistence, background job dispatch. Invokes the Orchestrator (`agents/orchestrator`) but contains no agent reasoning itself.

## Layout

```text
main.py              FastAPI app: routers + error handlers + /health.
config.py            Settings from the environment, incl. the safety ceilings.
deps.py              Auth, DB session, and the Orchestrator seam.
errors.py            The single error envelope api-contract.md documents.
schemas.py           Request/response bodies; ORM -> packages/schemas conversion.
orchestrator_stub.py Canned Orchestrator. DELETE when agents/orchestrator lands.
routers/             One module per resource group (issue #12).
celery_app.py        Celery app; `include` is what makes tasks visible to a worker.
tasks.py             Async test execution (issue #13).
load_engineer_stub.py Canned k6 wrapper. DELETE when agents/load-engineer lands.
db/base.py           Declarative base, constraint naming convention, session factory.
db/models.py         SQLAlchemy models for all 14 entities (issue #11).
alembic.ini          Migration config — run from the REPO ROOT, see below.
alembic/             Migration environment and versions/.
tests/               Endpoint tests against the stub Orchestrator.
requirements.txt     Runtime dependencies for the api and worker containers.
```

## The two agent seams

`deps.get_orchestrator()` and `deps.get_load_engineer()` are the only places
that name an agent implementation. Both return stubs today; when
Developer 1/Thatayaone's `agents/orchestrator` and Developer 2/Govenor's
`agents/load-engineer` land, those two functions change and nothing else
does. Each stub returns payloads that validate against `packages/schemas`,
so a contract change there breaks the tests here rather than surfacing at
integration time.

The Load Engineer stub is deliberately *not* a pure fake: the safety-ceiling
clamping and the pre-execution allow-list re-check are implemented for real,
because those are the parts that must survive the swap. The tests covering
them should keep passing against Govenor's wrapper unchanged.

## Running the tests

They need a database — the models use JSONB and native Postgres enums, so
SQLite would be testing a schema that never ships:

```bash
cd infrastructure/docker && docker compose up -d db && cd ../..
python -m pytest apps/api/tests
```

The suite skips itself if no database is reachable, so `pytest` stays green
for teammates who haven't started the stack.

Migrations run from the repository root, not from here:

```bash
alembic -c apps/api/alembic.ini upgrade head
```

See [local-development.md#database-migrations](../../docs/development/local-development.md#database-migrations) for the full workflow, including the two things Alembic's autogenerate will not do for you.

The ORM lives here rather than in `packages/schemas` deliberately: that package is the typed *contract* layer (its docstring scopes ORM mapping and persistence out), and it's a shared path needing cross-owner sign-off. The two stay in step because `db/models.py` imports its enums from `packages/schemas` instead of redeclaring them.

## Running a worker

Execution is asynchronous; without a worker a run stays `queued`:

```bash
celery -A apps.api.celery_app worker --loglevel=info
```

See [local-development.md#background-jobs](../../docs/development/local-development.md#background-jobs), including what to check when a run never leaves the queue.

## Reference

- [docs/api/api-contract.md](../../docs/api/api-contract.md) — every endpoint, request/response shape, auth, and error contract
- [docs/database/database-design.md](../../docs/database/database-design.md) — the schema to migrate
- `packages/schemas/python/` — the Pydantic models request/response bodies and persistence must validate against
- [docs/security/security-model.md](../../docs/security/security-model.md) — target authorization and safety-ceiling enforcement points that live at this layer

This app can be built and tested against a stubbed Orchestrator response before the real agents exist — see [docs/development/team-workflow.md](../../docs/development/team-workflow.md#how-the-contracts-enable-parallel-work).
