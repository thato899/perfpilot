# P2-API-1: Historical baselines and the comparison API

Issue #34 persists a *chosen* prior run and exposes a comparison against it.
The complaint it answers is in the issue's own words: *"Users must compare a
run with an intentional prior run, not an unrelated or silently selected
result."* Everything below follows from taking that literally.

## Who owns what

| Concern | Owner |
|---|---|
| Every calculation — deltas, percentages, rounding, sign convention | `packages/metrics` (#32) |
| What makes two runs the same experiment | `apps/api/scenario_identity.py` |
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

Four things are copied onto that row at selection time — `test_type`,
`target_concurrency`, `scenario_fingerprint` and the `scenario` document it
was computed from — rather than read back through the plan. The reason is that
a `TestPlan` is mutable. If compatibility were judged by reading the live plan,
editing it would retroactively change whether a comparison made six weeks ago
was valid, and nobody would be told. A baseline has to keep meaning what it
meant when it was chosen.

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
5. **Same scenario** — `scenario_mismatch`, or
   `scenario_identity_unsupported` when the stored fingerprint's version is not
   one this build knows. See the next section.
6. **Both runs recorded metrics** — `baseline_metrics_unavailable`,
   `current_metrics_unavailable`. Missing data is refused, never read as zero.
7. **At least one shared endpoint scope** — `no_shared_endpoint`.

Checked in that order, so the reported reason is the most fundamental one:
being on a different target makes the type and concurrency questions moot, and
a run that never finished is unusable for a more basic reason than either.

### Scenario identity

Rules 2–4 were the whole of compatibility in the first revision of this PR,
and that was the gap review caught. Target, type and concurrency can all agree
while two plans still describe substantially different tests: a five-minute
soak of `["browse"]` and a forty-minute ramp through
`["browse", "checkout", "search"]` match on all three. Comparing them produces
deltas that look like a regression and are really a change of experiment —
exactly what #34 asks to be rejected.

`apps/api/scenario_identity.py` defines the identity and carries the full
argument. In summary:

| In the fingerprint | Out, and why |
|---|---|
| `test_type`, `target_concurrency` | `rationale` — prose; rewording does not change the test |
| `ramp_strategy`, `stages` | `thresholds`, `success_criteria` — the judgement applied *to* the numbers, not the numbers |
| `duration`, `user_journeys` | `controlled_variable` — what an experiment varies on purpose; including it would make every experiment incomparable with its own baseline |

Three properties it has to have, and how each is obtained:

- **Stable** — the document is canonicalised before hashing (sorted keys, no
  insignificant whitespace, integral floats narrowed to ints, so `300` and
  `300.0` are the same five minutes) and hashed with SHA-256 rather than
  Python's per-process-salted `hash()`.
- **Versioned** — every value is `v1:<sha256>`. If the field set or the
  canonical form changes, old fingerprints do not silently start meaning
  something else; they carry a version this build does not recognise and the
  comparison is refused with a reason that says so. A database `CHECK` enforces
  the prefix, because these rows outlive the process that wrote them.
- **Explainable** — a hash can only say "different", so the normalized document
  is stored beside it and `scenario_mismatch` carries
  `detail.differing_fields` naming the fields that actually disagree.

List order is treated as significant everywhere, including `user_journeys`
where a case could be made that it is incidental. The two mistakes are not
symmetric: a spurious refusal names the field and is fixed by re-selecting a
baseline, while a spurious *match* silently compares two different experiments
and reports the difference as a regression. Only one of those self-corrects.

**Known limitation.** The current run's scenario is read from its plan live,
while the baseline's is frozen, so editing a plan after runs have executed can
make two previously comparable runs incomparable. That is the conservative
direction rather than a silent wrong answer, and the proper fix — snapshotting
the scenario onto `test_run` at execution time — is a change to the run
lifecycle rather than to this slice, so it is raised separately.

### Worked examples

| Baseline | Current | Result |
|---|---|---|
| `load`, 100 VUs, target A, succeeded | `load`, 100 VUs, target A, succeeded | Compared |
| `load`, 100 VUs, **plan X** | `load`, 100 VUs, **plan Y**, same scenario | Compared — re-planning an identical scenario does not disqualify a baseline |
| `load`, 100 VUs, target A | `load`, 100 VUs, **target B** | `409 environment_mismatch` |
| `load`, **200 VUs** | `load`, **1000 VUs** | `409 concurrency_mismatch` — otherwise more load reads as a regression |
| `load`, 100 VUs | **`stress`**, 100 VUs | `409 test_type_mismatch` |
| `load`, 100 VUs, `["browse","checkout"]`, 5 min | `load`, 100 VUs, **`["browse"]`, 40 min** | `409 scenario_mismatch`, `differing_fields: ["duration", "user_journeys"]` |
| fingerprint `v0:…` | `v1:…` | `409 scenario_identity_unsupported` — re-select the baseline |
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

## Authorization

Both endpoints re-check that a target is still allow-listed and still
authorization-confirmed, rather than trusting whenever the target was created:
authorization can be revoked in between, and a baseline is a durable record
that outlives the request that made it.

The comparison endpoint authorizes **both** targets — the current run's and the
baseline's — and the baseline's before anything is read out of its row. The
first revision checked only the run's target, which meant a caller could name a
baseline belonging to a revoked target and get back a `409 environment_mismatch`
whose `detail` carried that target's id. The order is the fix, not just the
extra call: a `403` has to come before any refusal that quotes the record.

## Idempotency

- Re-selecting the same run for the same target returns `200` with the
  existing record. Not a duplicate, not an error — the uniqueness rule
  `(target_id, test_run_id)` makes this safe at the database level, and two
  concurrent selections resolve to the same row rather than a `500`.
- An optional `idempotency_key` covers the case where a caller retries before
  knowing whether the first request landed. The same key for a *different*
  run is `409 idempotency_key_reused`: honouring it would silently change
  which run the caller believes is their baseline.
- **The key is resolved before the "already a baseline" repeat**, not after.
  The first revision returned `200` from the `(target, run)` lookup first, so a
  caller retrying with a key that meant a different run got a success and
  walked away believing their key now referred to this one — the precise
  failure the key exists to prevent.
- A key supplied for a run that is already a baseline under no key returns
  `200` and is **not** written onto that row. A repeat read should not quietly
  mutate the record it is reporting, and the answer stays the same however many
  times it is asked.
- The `IntegrityError` path re-reads *both* uniqueness rules. Assuming the
  collision was on `(target_id, test_run_id)` turned a concurrent key collision
  into a `500`, which is the one outcome an idempotency key exists to prevent.
- The comparison endpoint is a read and has nothing to duplicate.

## Migration

`20260924_..._baseline_selection_for_deterministic_comparison.py` adds the
`baseline` table and nothing else.

It was **amended in place** rather than followed by a second migration, because
it had not merged: one new table deserves one migration. The revision id is
unchanged, so if you applied the earlier version, `upgrade head` will do
nothing — run `downgrade -1` then `upgrade head` to pick up
`scenario_fingerprint` and `scenario`. Nothing depends on `baseline` yet, so
that costs only the rows you selected while testing.

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
the shared enum and every row; re-upgrade is clean. Both check constraints and
the `RESTRICT` rule were exercised with raw SQL — an unversioned fingerprint
and a delete of a referenced run are both refused by the database, not only by
Python. `--autogenerate` against the migrated schema proposes nothing for
`baseline`; the only drift it still reports is the pre-existing
`investigation_event` rename described above.

Run it the usual way, from the repository root:

```bash
alembic -c apps/api/alembic.ini upgrade head
```

## Tests

| Layer | File | What it covers |
|---|---|---|
| Rules | `apps/api/tests/test_baselines.py::TestEligibility`, `TestPairCompatibility` | Every rule and its reason code, as values, with no database — including each scenario field on its own, reordered journeys, multiple differing fields, check ordering, and an unrecognised identity version |
| Pairing | `TestMetricPairing` | Endpoint matching, unmatched scopes, repeated samples, delegation to `packages/metrics` |
| Persistence | `TestPersistence` | The uniqueness and `RESTRICT` rules, against real Postgres — they are enforced by the database, so asserting them in Python alone would prove nothing |
| HTTP | `TestSelectionEndpoint`, `TestComparisonEndpoint`, `TestListingEndpoints` | Every documented success and failure, including auth, a revoked baseline target, and two different scenarios that share an endpoint |

Each of the three tests written for review feedback was checked against the
*old* code first and fails there — the scenario tests return a comparison, the
revoked-target test returns the `409` quoting the target id, and the concurrent
key collision raises `IntegrityError` into a `500`. A regression test that
passes before the fix is not one.

## Consumer handoff

- **#39** consumes `ComparisonResponse`, `BaselineRef` and the
  `IncompatibleReason` union — see `packages/schemas/typescript/types.ts`.
  Render `null` percent fields as "not expressible" rather than `0%`: they mean
  the baseline value was zero. Branch on the typed `status` and the
  `IncompatibleReason` codes rather than on message text.
- `scenario_fingerprint` is **opaque**. Compare it for equality to tell whether
  two baselines are interchangeable as references; never parse it, and do not
  show it to a user. For "why can't I compare these?", render
  `detail.differing_fields` from a `scenario_mismatch` — that is the part a
  person can act on.
- `scenario_identity_unsupported` is not a user error. The right affordance is
  "re-select this baseline", not a retry.
