# P2-API-1: Historical baselines and the comparison API

Issue #34 persists a *chosen* prior run and exposes a comparison against it.
The complaint it answers is in the issue's own words: *"Users must compare a
run with an intentional prior run, not an unrelated or silently selected
result."* Everything below follows from taking that literally.

## Who owns what

| Concern | Owner |
|---|---|
| Every calculation — deltas, percentages, rounding, sign convention | `packages/metrics` (#32) |
| Which records may legitimately be compared | `apps/api/baselines.py` |
| Authorization, persistence, HTTP shape | `apps/api/routers/baselines.py` |
| Choosing a baseline | a person, through the API |

The API performs no arithmetic. `compare_metrics` is called and its result is
passed through untouched, which is why a change to the sign convention or the
rounding is a one-line change in one package rather than a hunt across two.

No agent selects a baseline. There is no "most recent compatible run"
fallback, and `baseline_id` is a required parameter rather than an optional
one — an endpoint that picked a reference when none was named would be
precisely the silent selection the ticket forbids.

## What a baseline is

A row recording that someone promoted a succeeded `TestRun` to be the
reference for its target. Not a kind of test, not a flag on the run.

Two fields are copied onto that row at selection time — `test_type` and
`target_concurrency` — rather than read back through the plan. The reason is
that a `TestPlan` is mutable. If compatibility were judged by reading the live
plan, editing it would retroactively change whether a comparison made six
weeks ago was valid, and nobody would be told. A baseline has to keep meaning
what it meant when it was chosen.

## Compatibility rules

All must hold. Each returns `409` with the bracketed code and a `detail`
object carrying the values that failed.

1. **Both runs succeeded** — `baseline_run_not_succeeded`,
   `current_run_not_succeeded`. A queued, running, failed or safety-aborted
   run has no final numbers to compare.
2. **Same target** — `environment_mismatch`. The target is the environment:
   same `target_id` means the same base URL and the same authorization record.
3. **Same `test_type`** — `test_type_mismatch`.
4. **Same `target_concurrency`** — `concurrency_mismatch`.
5. **Both runs recorded metrics** — `baseline_metrics_unavailable`,
   `current_metrics_unavailable`. Missing data is refused, never read as zero.
6. **At least one shared endpoint scope** — `no_shared_endpoint`.

Checked in that order, so the reported reason is the most fundamental one:
being on a different target makes the type and concurrency questions moot, and
a run that never finished is unusable for a more basic reason than either.

### Worked examples

| Baseline | Current | Result |
|---|---|---|
| `load`, 100 VUs, target A, succeeded | `load`, 100 VUs, target A, succeeded | Compared |
| `load`, 100 VUs, **plan X** | `load`, 100 VUs, **plan Y** | Compared — same shape; re-planning does not disqualify a baseline |
| `load`, 100 VUs, target A | `load`, 100 VUs, **target B** | `409 environment_mismatch` |
| `load`, **200 VUs** | `load`, **1000 VUs** | `409 concurrency_mismatch` — otherwise more load reads as a regression |
| `load`, 100 VUs | **`stress`**, 100 VUs | `409 test_type_mismatch` |
| succeeded | **running** | `409 current_run_not_succeeded` |
| metrics for `/checkout` | metrics for `/browse` only | `409 no_shared_endpoint` |
| metrics for `/`, `/checkout` | metrics for `/`, `/browse` | Compared on `/`; `/checkout` and `/browse` reported as unmatched |

## Metric pairing

Metrics are paired by **endpoint scope**, because that is the axis
`compare_metrics` itself refuses to cross — pairing on anything else would
only produce `incompatible` verdicts from the layer below. The aggregate row
(`endpoint: null`) is paired like any other scope and is returned first.

When a run records the same endpoint more than once — `database-design.md`
allows interval-collected metrics as well as a final summary — the latest
sample wins, because that is the one describing the finished run.

Endpoints measured in only one of the two runs are named in
`baseline_only_endpoints` / `current_only_endpoints`. They are reported rather
than dropped: a scope present in one run and absent from the other is a real
difference between them, and omitting it silently would make the comparison
look more complete than it is.

## Idempotency

- Re-selecting the same run for the same target returns `200` with the
  existing record. Not a duplicate, not an error — the uniqueness rule
  `(target_id, test_run_id)` makes this safe at the database level, and two
  concurrent selections resolve to the same row rather than a `500`.
- An optional `idempotency_key` covers the case where a caller retries before
  knowing whether the first request landed. The same key for a *different*
  run is `409 idempotency_key_reused`: honouring it would silently change
  which run the caller believes is their baseline.
- The comparison endpoint is a read and has nothing to duplicate.

## Migration

`20260924_..._baseline_selection_for_deterministic_comparison.py` adds the
`baseline` table and nothing else.

Two things in it were **not** what autogenerate produced, both worth knowing
before writing the next migration:

1. **The `test_type` enum is reused, not created.** Autogenerate emits a bare
   `sa.Enum(...)`, which makes the migration issue a second `CREATE TYPE
   test_type` and fail with *"type test_type already exists"* — rolling the
   whole upgrade back. It uses `postgresql.ENUM(..., create_type=False)`
   instead. `local-development.md#changing-the-schema` already flags enums as
   the one thing autogenerate reliably gets wrong; this is that.
2. **Four `investigation_event` constraint renames were removed.** They are
   real pre-existing drift between #35's migration and the naming convention
   in `db/base.py` — identical columns, different generated names — but
   `investigation_event` is #35's table and renaming another owner's
   constraints here would be an unrelated schema change. Raised separately.
   Until it is fixed, `--autogenerate` will keep proposing them, so an empty
   drift migration is not currently the right expectation.

Verified against real Postgres: applies to a fresh database and to a populated
one without touching existing runs; downgrade drops only `baseline`, keeping
the shared enum and every row; re-upgrade is clean.

Run it the usual way, from the repository root:

```bash
alembic -c apps/api/alembic.ini upgrade head
```

## Tests

| Layer | File | What it covers |
|---|---|---|
| Rules | `apps/api/tests/test_baselines.py::TestEligibility`, `TestPairCompatibility` | Every rule and its reason code, as values, with no database |
| Pairing | `TestMetricPairing` | Endpoint matching, unmatched scopes, repeated samples, delegation to `packages/metrics` |
| Persistence | `TestPersistence` | The uniqueness and `RESTRICT` rules, against real Postgres — they are enforced by the database, so asserting them in Python alone would prove nothing |
| HTTP | `TestSelectionEndpoint`, `TestComparisonEndpoint`, `TestListingEndpoints` | Every documented success and failure, including auth |

## Consumer handoff

- **#39** consumes `ComparisonResponse` and `BaselineRef` — see
  `packages/schemas/typescript/types.ts`. Render `null` percent fields as
  "not expressible" rather than `0%`: they mean the baseline value was zero.
  Branch on the typed `status` and the `409` codes rather than on message
  text.
