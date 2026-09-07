# API Contract

**Owner:** Developer 3 (Backend / Data) · **Code location:** `apps/api/`

All endpoints are versionless-for-now (`/api/...`) — the MVP is single-version, single-tenant. Request/response bodies are the Pydantic models in `packages/schemas/python`, mirrored in `packages/schemas/typescript` for the frontend. All endpoints return `application/json`.

## Authentication (MVP)

A single static bearer token (`API_AUTH_SECRET`, see `.env.example`), sent as `Authorization: Bearer <token>`. This is a deliberate hackathon-scope simplification — see [ADR-001](../decisions/ADR-001-tech-stack.md) and [security model](../security/security-model.md) for why full multi-user auth is out of scope for Phase 0/1. Every endpoint below requires this header unless noted.

## Common error shape

```json
{ "error": { "code": "string", "message": "string", "detail": {} } }
```

| HTTP status | Meaning |
|---|---|
| 400 | Malformed request body |
| 401 | Missing/invalid auth token |
| 403 | Target not on the authorization allow-list (see security model) |
| 404 | Resource not found or not owned by caller's project |
| 409 | Action conflicts with current resource state (e.g. re-running a test still `in_progress`) |
| 422 | Body fails schema validation |
| 429 | Safety-limit rejection (e.g. requested VUs exceed `MAX_VIRTUAL_USERS`) |

---

## Projects

### `POST /api/projects`
- **Purpose:** create a project — the top-level container for targets, plans, and investigations.
- **Request:** `{ "name": "string", "description": "string?" }`
- **Response:** `201` → `Project` (see [database design](../database/database-design.md#project)).
- **Errors:** 422 on missing `name`.

### `GET /api/projects/{id}`
- **Purpose:** fetch a project and its summary (target count, latest investigation status).
- **Response:** `200` → `Project`. `404` if not found.

---

## Targets

### `POST /api/projects/{id}/targets`
- **Purpose:** register a target application and record the authorization confirmation required before any load can be sent to it (see [security model](../security/security-model.md#target-authorization)).
- **Request:**
  ```json
  { "base_url": "https://demo.perfpilot.local", "name": "string", "authorization_confirmed": true, "authorization_confirmed_by": "string" }
  ```
- **Response:** `201` → `Target`.
- **Errors:** `422` if `authorization_confirmed` is not `true` — the API refuses to create an unconfirmed target rather than creating it in a disabled state. `403` if `base_url`'s host isn't on `ALLOWED_TARGET_HOSTS`.

---

## Test plans

### `POST /api/tests/plan`
- **Purpose:** invoke the Test Planner agent (via the Orchestrator) to produce a `TestPlan` for a target.
- **Request:** `TestPlanRequest` (see [test-planner.md](../agents/test-planner.md#input-schema)).
- **Response:** `201` → `TestPlan`, persisted with status `proposed`.
- **Errors:** `422` on schema failure or an agent-reported "insufficient input" rejection (see test-planner.md failure states).

### `POST /api/tests/{id}/run`
- **Purpose:** approve a `TestPlan` and enqueue its execution. `{id}` is the `TestPlan` id.
- **Request:** `{ "target_id": "tgt_..." }`
- **Response:** `202` → `{ "test_run_id": "run_...", "status": "queued" }`. Execution happens asynchronously via Celery (see [system-architecture.md](../architecture/system-architecture.md)); this endpoint never blocks on test completion.
- **Errors:** `429` if the plan's concurrency/duration exceeds configured safety limits and the plan wasn't already clamped; `403` if the target's authorization has been revoked since the plan was created.

---

## Test runs

### `GET /api/test-runs/{id}`
- **Purpose:** poll status of a running/completed test.
- **Response:** `200` → `{ "id": "...", "status": "queued|running|succeeded|failed|aborted_over_limit", "progress": { "current_vus": 340, "target_vus": 1000 } }`.

### `GET /api/test-runs/{id}/metrics`
- **Purpose:** fetch validated metrics for a completed (or in-progress, partial) test run.
- **Response:** `200` → `{ "metrics": [ "...Metric records..." ] }`.
- **Errors:** `404` if the run doesn't exist or belongs to a different project.

---

## Investigations

### `POST /api/investigations`
- **Purpose:** start a new investigation for a target (kicks off UNDERSTAND → PLAN).
- **Request:** `{ "target_id": "tgt_...", "objective": "determine_capacity|diagnose_regression|validate_fix|baseline", "expected_traffic": { "...": "see test-planner.md" } }`
- **Response:** `201` → `Investigation` with status `planning`.

### `GET /api/investigations/{id}`
- **Purpose:** fetch full investigation state (mirrors the Orchestrator's `InvestigationState`, see [data-flow.md](../architecture/data-flow.md#investigation-state)) for the dashboard's investigation view.
- **Response:** `200` → `InvestigationState`.

### `GET /api/investigations/{id}/findings`
- **Purpose:** fetch just the ranked findings (lighter payload for a findings-only dashboard panel).
- **Response:** `200` → `{ "findings": [ "...Finding..." ] }`.

### `POST /api/investigations/{id}/experiments`
- **Purpose:** explicitly approve a specific recommended experiment (human-in-the-loop control point — the Orchestrator proposes, a human or an auto-approve policy confirms before load is generated again).
- **Request:** `{ "hypothesis_id": "hyp_..." }`
- **Response:** `202` → `{ "test_run_id": "run_..." }` (the resulting follow-up `TestRun`, queued).
- **Errors:** `409` if the hypothesis has no `recommended_experiment` or an experiment budget limit has already been hit.

### `POST /api/investigations/{id}/continue`
- **Purpose:** ask the Orchestrator to advance the investigation given the latest completed test run (used by the Celery worker's completion callback, and by a manual "continue" action in the dashboard).
- **Request:** `{ "test_run_id": "run_..." }`
- **Response:** `200` → `OrchestratorDecision` (see [orchestrator.md](../agents/orchestrator.md#output-schema)).

---

## Reports

### `GET /api/reports/{id}`
- **Purpose:** fetch a completed report.
- **Response:** `200` → `Report` (see [reporting-agent.md](../agents/reporting-agent.md#output-schema)). `404` if the investigation hasn't reached `reporting`/`complete` yet — the API does not auto-generate a partial report on this endpoint; report generation happens as part of the investigation reaching that state.

---

## Ownership note

`apps/api` (Developer 3) owns the HTTP layer, request/response validation, auth, and persistence for every endpoint above. It does not own what happens *inside* `POST /api/tests/plan` or `.../continue` beyond calling the Orchestrator and persisting what comes back — that reasoning belongs to Developer 1's agents. This is the seam that lets backend and AI work proceed in parallel: Developer 3 can build and test every endpoint above against the schemas in `packages/schemas` with a stubbed Orchestrator response, before Developer 1's agents are finished.
