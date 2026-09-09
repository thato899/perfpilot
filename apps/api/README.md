# apps/api

**Owner:** Developer 3/Kamogelo (Backend / Data)

FastAPI backend: HTTP layer, auth, persistence, background job dispatch. Invokes the Orchestrator (`agents/orchestrator`) but contains no agent reasoning itself.

Not implemented yet — this is Phase 1 work. Build against:

- [docs/api/api-contract.md](../../docs/api/api-contract.md) — every endpoint, request/response shape, auth, and error contract
- [docs/database/database-design.md](../../docs/database/database-design.md) — the schema to migrate
- `packages/schemas/python/` — the Pydantic models request/response bodies and persistence must validate against
- [docs/security/security-model.md](../../docs/security/security-model.md) — target authorization and safety-ceiling enforcement points that live at this layer

This app can be built and tested against a stubbed Orchestrator response before the real agents exist — see [docs/development/team-workflow.md](../../docs/development/team-workflow.md#how-the-contracts-enable-parallel-work).
