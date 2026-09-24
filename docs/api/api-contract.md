# API Contract

**Owner:** Developer 3/Kamogelo (Backend / Data) · **Code location:** `apps/api/`

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
- **Request:** `TestPlanRequest` (see [test-planner.md](../agents/test-planner.md#input-schema)), **plus `project_id` and `target_id`**. `TestPlanRequest` carries a target *description* but no ids, and the API has to know which `Project` and `Target` to persist the resulting plan against. The request body is therefore the planner's fields flattened alongside those two ids — see `apps/api/schemas.py::CreateTestPlanRequest`.
- **Response:** `201` → `TestPlan`, persisted with status `proposed`.
- **Errors:** `422` on schema failure or an agent-reported "insufficient input" rejection (see test-planner.md failure states).

### `POST /api/tests/{id}/run`
- **Purpose:** approve a `TestPlan` and enqueue its execution. `{id}` is the `TestPlan` id.
- **Request:** `{ "target_id": "tgt_..." }`
- **Response:** `202` → `{ "test_run_id": "run_...", "status": "queued" }`. Execution happens asynchronously via Celery (see [system-architecture.md](../architecture/system-architecture.md)); this endpoint never blocks on test completion.
- **Errors:** `429` if the plan's concurrency/duration exceeds configured safety limits; `403` if the target's authorization has been revoked since the plan was created; `409` if a run for this plan is already `queued` or `running`.

  *Open question:* this previously read "…and the plan wasn't already clamped", but `clamped` is a `TestRun` column — there is no such field on `TestPlan`, and at approval time no run exists yet. Implemented as a straight ceiling check. If plans are meant to carry a pre-clamped marker, that's a `database-design.md` change and needs a decision.

  Both ceilings are checked: `target_concurrency` against `MAX_VIRTUAL_USERS`, and `duration.total_s` against `MAX_TEST_DURATION_SECONDS`.

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
- **Response:** `201` → `Investigation` with status `running`; its initial
  approved `TestPlan` and queued `TestRun` are linked through
  `current_test_run_id`.

### `GET /api/investigations/{id}`
- **Purpose:** fetch full investigation state (mirrors the Orchestrator's `InvestigationState`, see [data-flow.md](../architecture/data-flow.md#investigation-state)) for the dashboard's investigation view.
- **Response:** `200` → `InvestigationState`, including the current `experiment_budget` summary and ordered `events` history. Existing Phase 1 fields remain backward compatible.

### `GET /api/investigations/{id}/findings`
- **Purpose:** fetch just the ranked findings (lighter payload for a findings-only dashboard panel).
- **Response:** `200` → `{ "findings": [ "...Finding..." ] }`.

### `POST /api/investigations/{id}/experiments`
- **Purpose:** explicitly approve a specific recommended experiment (human-in-the-loop control point — the Orchestrator proposes, a human or an auto-approve policy confirms before load is generated again).
- **Request:** `{ "hypothesis_id": "hyp_...", "idempotency_key": "optional-client-key" }`; the same key may be sent as `Idempotency-Key`.
- **Response:** `202` → `{ "test_run_id": "run_...", "experiment_id": "exp_...", "status": "queued" }` (the resulting follow-up `TestRun`, queued).
- **Errors:** `409` if the hypothesis has no `recommended_experiment` or an experiment budget limit has already been hit.

### `POST /api/investigations/{id}/continue`
- **Purpose:** ask the Orchestrator to advance the investigation given the latest completed test run (used by the Celery worker's completion callback, and by a manual "continue" action in the dashboard).
- **Request:** `{ "test_run_id": "run_..." }`
- **Response:** `200` → `OrchestratorDecision` (see [orchestrator.md](../agents/orchestrator.md#output-schema)).

---

## Baselines

A baseline is a **deliberately chosen** prior run, persisted so a comparison
names an intentional reference rather than whatever the system happened to
pick. Selection is a human action through these endpoints; no agent chooses a
baseline, and no endpoint substitutes one.

Two runs are comparable when **all** of the following hold. Each failure
returns `409` with the code in brackets:

| Rule | Code |
|---|---|
| Both runs succeeded | `baseline_run_not_succeeded` / `current_run_not_succeeded` |
| Same target — the target *is* the environment | `environment_mismatch` |
| Same `test_type` | `test_type_mismatch` |
| Same `target_concurrency` | `concurrency_mismatch` |
| Both runs recorded metrics | `baseline_metrics_unavailable` / `current_metrics_unavailable` |
| At least one endpoint scope measured in both | `no_shared_endpoint` |

Compatibility is the *scenario shape*, not the plan row: re-planning the same
scenario keeps existing baselines valid, while a different concurrency does
not, because comparing 200 VUs against 1000 would read as a regression that is
really a load change.

### `POST /api/targets/{target_id}/baselines`

- **Purpose:** promote a succeeded run to a named baseline for its target.
- **Request:** `{ "test_run_id": "run_...", "label": "v1.2 release", "selected_by": "kamogelo", "idempotency_key": "optional" }`
- **Response:** `201` → `BaselineRef`. Re-selecting the same run returns `200`
  with the existing record — a safe repeat, not a duplicate and not an error.
- **Errors:** `404` unknown target or run; `409` run belongs to another target
  (`environment_mismatch`), run did not succeed, or the idempotency key was
  already used for a different run (`idempotency_key_reused`); `422` missing
  or empty `label`.

The response records `test_type` and `target_concurrency` as they were at
selection time. Compatibility is judged against those frozen values, so a
later edit to the plan cannot silently change whether an old comparison was
valid.

### `GET /api/targets/{target_id}/baselines`

- **Response:** `200` → `{ "baselines": [BaselineRef, ...] }`, newest first.
  An empty list is a normal result, not a `404`.

### `GET /api/baselines/{baseline_id}`

- **Response:** `200` → `BaselineRef`.

### `GET /api/test-runs/{run_id}/comparison?baseline_id={baseline_id}`

- **Purpose:** compare a run against one named baseline.
- **`baseline_id` is required.** Omitting it is a `422`, not a fallback to the
  most recent run — a silently selected reference is the thing this endpoint
  exists to prevent. Use the list endpoint to choose.
- **Response:** `200` →
  `{ "baseline": BaselineRef, "current_test_run_id": "run_...", "comparisons": [MetricComparison, ...], "baseline_only_endpoints": [...], "current_only_endpoints": [...] }`
- **Errors:** `404` unknown run or baseline; `409` with one of the codes above.

One `MetricComparison` is returned per endpoint scope measured in both runs,
aggregate (`endpoint: null`) first. Endpoints measured in only one of the runs
are named in `baseline_only_endpoints` / `current_only_endpoints` rather than
dropped: a scope present in one run and absent from the other is a real
difference, and omitting it would make the comparison look more complete than
it is.

Every number in `MetricComparison` is produced by `packages/metrics` and
passed through unchanged — this layer performs no arithmetic. A `null` percent
field means the baseline value was zero, so a percentage cannot be expressed;
it does not mean zero change.

## Reports

### `GET /api/reports/{id}`
- **Purpose:** fetch a completed report.
- **Response:** `200` → `Report` (see [reporting-agent.md](../agents/reporting-agent.md#output-schema)). `404` if the investigation hasn't reached `reporting`/`complete` yet — the API does not auto-generate a partial report on this endpoint; report generation happens as part of the investigation reaching that state.

---

## Operational endpoints

Not part of the resource surface above — infrastructure probes, not product API.

### `GET /health`
- **Purpose:** liveness probe. Consumed by `infrastructure/docker/docker-compose.yml`'s healthcheck for the `api` service and by `render.yaml`'s `healthCheckPath`.
- **Auth:** none. A probe that needs a bearer token can't be used by an orchestrator that doesn't have one.
- **Response:** `200` → `{ "status": "ok" }`.
- **Deliberately shallow:** it reports that the process is serving and checks nothing downstream. Compose already gates `api` on `db` and `redis` passing their own healthchecks, so re-checking them here would report someone else's outage as this service being unhealthy and trigger restarts that fix nothing. If a readiness probe that *does* check dependencies is ever needed, it belongs at a separate path, not folded into this one.

---

## Ownership note

`apps/api` (Developer 3/Kamogelo) owns the HTTP layer, request/response validation, auth, and persistence for every endpoint above. It does not own what happens *inside* `POST /api/tests/plan` or `.../continue` beyond calling the Orchestrator and persisting what comes back — that reasoning belongs to Developer 1/Thatayaone's agents. This is the seam that lets backend and AI work proceed in parallel: Developer 3/Kamogelo can build and test every endpoint above against the schemas in `packages/schemas` with a stubbed Orchestrator response, before Developer 1/Thatayaone's agents are finished.
