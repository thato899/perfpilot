# P2-API-2: Investigation state and experiment budgets

Issue #35 extends the existing `Investigation`, `Finding`, `Hypothesis`,
`Experiment`, `ExperimentResult`, and `Recommendation` entities. It does not
create a second state machine or a second experiment concept.

## State model

The mutable rows are the current projection used by the API and Orchestrator.
`investigation_event` is the append-only, ordered history of state-changing
boundaries. Both are written in the same transaction.

Every Finding, Hypothesis, and Experiment keeps its UUID. Findings and
hypotheses have an optional sequence index for new rows; legacy rows retain a
stable `(created_at, id)` read-order fallback. Evidence items receive an ID
when written. Experiment proposals are persisted before approval and use the
same `Experiment` row through approval, execution, and result persistence.

## Typed lifecycles

| Entity | States | Transition owner |
|---|---|---|
| Investigation | `planning → running → investigating → experimenting → reporting → complete` or `failed` | Orchestrator/API persistence boundary |
| Hypothesis | `proposed → testing → supported` or `rejected` | Investigator output validated by Orchestrator |
| Experiment | `proposed → queued → running → succeeded` or `failed`; `approved` is the human approval boundary; `rejected` is terminal | API approval and worker boundary |

An experiment is reserved exactly once when approval succeeds. A failed or
aborted run consumes that reservation: it is still a load-generating attempt.
Rejected proposals consume no budget.

## Budget semantics

`max_experiments` is copied from `MAX_EXPERIMENTS_PER_INVESTIGATION` when the
investigation is created. `experiments_run` is the consumed reservation count;
`remaining = max(0, max_experiments - experiments_run)`. The server never
accepts a request that raises the budget. Reservation and approval are
serialized on the Investigation row, so concurrent approvals cannot overspend.

When remaining reaches zero, a new approval returns `409
experiment_budget_exhausted`, and the Orchestrator reports the budget-exhausted
reason before reporting the best available state. No automatic retry can create
another run.

## Event contract

Each event has a UUID, a per-investigation monotonic `sequence`, typed `type`,
JSON payload containing stable related IDs, optional idempotency key, and
timestamp. Current event types are:

`investigation_created`, `test_run_queued`, `test_run_started`,
`test_run_completed`, `finding_recorded`, `hypothesis_recorded`,
`experiment_proposed`, `experiment_approved`, `experiment_started`,
`experiment_completed`, `budget_exhausted`, `continue_requested`, and
`report_persisted`, and `recommendation_recorded`.

`GET /api/investigations/{id}` exposes the current projection plus the ordered
`events` history and `experiment_budget` summary. Existing Phase 1 fields remain
present; nullable experiment plan/run links allow old and proposed rows to be
read without backfilling a fake execution.

## Idempotency and restart behavior

The approval endpoint accepts `Idempotency-Key` or a request-body
`idempotency_key`. A repeated key returns the existing experiment/run. A
repeated approval for the same hypothesis also returns its existing active or
completed run. The worker refuses to execute a non-queued TestRun, and the
continue endpoint uses a stable run-based key by default. Persisted events and
current rows therefore survive worker restarts and duplicate delivery.

The human approval boundary remains `POST
/api/investigations/{id}/experiments`; this slice preserves the existing queue
seam. k6 execution and runtime persistence remain the responsibility of #36.

## Consumer handoffs

- **#36:** use the existing approved Experiment ID and linked TestRun ID;
  update Experiment lifecycle status and append the execution events at the
  worker boundary.
- **#37:** consume `experiment_budget`, typed statuses, stable entity IDs, and
  ordered `events`; do not infer timeline order from array position.
- **#38:** use the same Experiment/Investigation event contracts when wiring
  runtime persistence; do not add a second runtime state table.
