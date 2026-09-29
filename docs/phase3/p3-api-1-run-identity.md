# P3-API-1: Freezing scenario identity on each test run

Issue #68 closes an asymmetry that #34 shipped knowingly and wrote down as a
limitation:

> the baseline's scenario is frozen, but the current run's is read from its
> plan live, so editing a plan after runs have executed can make two previously
> comparable runs incomparable.

That was the conservative direction — a refusal rather than a quietly wrong
comparison — but it is still a plan edit deciding the fate of a result that was
recorded months earlier. A run should describe what it ran.

## The rule

**A TestRun records the scenario it was accepted to execute, at creation, and
that record is never written again.**

Everything below follows from taking that literally.

| Concern | Owner |
|---|---|
| What counts as a scenario, and how it is normalized and versioned | `apps/api/scenario_identity.py` (#34, unchanged) |
| Stamping the snapshot onto every new run | `apps/api/run_identity.py` |
| Deciding which records may be compared | `apps/api/baselines.py` |
| Every number in a comparison | `packages/metrics` (#32) |

The identity itself is **unchanged `v1`**. #68 moves *where it is read from*,
not what it contains, which is what keeps every baseline selected under #34
comparable across this change. A new field set would have meant a `v2` prefix
and every existing baseline returning `scenario_identity_unsupported`.

## Why a factory rather than three call sites

Runs are created in three places — plan approval, an investigation's first run,
and an approved experiment's run — and there will be a fourth. All of them go
through `run_identity.new_test_run`, which is the only supported way to build
the row.

This is deliberate. A forgotten snapshot would not fail loudly at the moment of
the mistake; it would produce a run that simply cannot be compared, discovered
weeks later by someone wondering why the API is refusing them. Making the
snapshot part of construction means the mistake cannot be made by omission.

`new_test_run` is keyword-only, because `test_plan_id` and `target_id` are both
UUIDs and a positional swap is a plausible-looking bug no type checker catches.

## Immutability, and what "retry" means here

The snapshot is written by the INSERT and by nothing else. There is no update
path, at start, at completion, or on retry.

Celery retries re-execute the *same row*, so they see the same snapshot by
construction rather than by a rule anyone has to remember. A genuinely new
request creates a new row with its own snapshot. Two runs of an unchanged plan
therefore agree, and neither drifts — pinned by
`TestFrozenRunIdentity::test_each_created_run_gets_its_own_stable_snapshot`.

## Legacy runs

Runs created before the migration have no snapshot, and **none is ever
reconstructed for them**.

The temptation is obvious: the plan is right there. But a plan that has been
edited since would yield an identity that looks authoritative and cannot be
supported, which is the exact failure mode this issue exists to remove.
Refusing to answer is the honest result.

So `scenario_fingerprint IS NULL` is a first-class state, and comparisons
involving such a run are refused with `baseline_run_identity_unknown` /
`current_run_identity_unknown`, carrying
`detail.cause = "run_predates_scenario_identity"`. The same check blocks
selecting a legacy run as a baseline, so a bad reference cannot be created and
then fail later.

For a consumer this is neither a user error nor a retryable failure. There is
no answer to be had for that run, and "this run is too old to compare" is the
honest rendering.

## Clamped runs

A run can be accepted at 1000 VUs and executed at 500 when the safety ceiling
bites; `TestRun.clamped` records it.

The snapshot keeps saying 1000, because the column has to mean one thing and
"what was accepted" is the thing it can mean consistently — it is written
before execution, so it cannot mean "what actually ran" without becoming
mutable. Amending it at completion was considered and rejected: it would trade
the immutability the whole ticket is about for a value that is still only
approximately true.

Instead the discrepancy is surfaced rather than absorbed. A clamped run is
refused with `baseline_run_clamped` / `current_run_clamped` and
`detail.clamped`. Comparing one would read a smaller test as an improvement,
which is precisely the silently-wrong answer the comparison contract exists to
prevent.

## Ordering of refusals

`check_eligibility` reports, in order: the run did not succeed → its identity
is unknown → it was clamped. Most fundamental first, so the reported reason is
the useful one. A run whose scenario cannot be established at all makes the
clamping question moot, and a run that never finished makes both moot.

## Malformed identity

A plan whose scenario cannot be normalized is rejected at run creation with
`422 scenario_identity_invalid`, rather than raising a `TypeError` several
frames away or — worse — creating a run with a guessed identity. Refusing to
start is the safe failure.

## Migration

`20260929_..._freeze_scenario_identity_on_each_test_run.py` adds two nullable
columns and two CHECK constraints to `test_run`, and nothing else. Every
existing row already satisfies both constraints, so there is no table rewrite
and nothing legacy data can fail on.

The constraint names are written **bare** (`scenario_identity_complete`, not
`ck_test_run_scenario_identity_complete`): `db/base.py`'s naming convention
adds the prefix itself, and passing an already-prefixed name produces
`ck_test_run_ck_test_run_…`, which then reads as permanent drift to every later
`--autogenerate`. This was got wrong once during #34 and again in the first
draft of this migration.

Verified against real Postgres: applies to a fresh database and to one holding
existing runs; downgrade drops only the new columns and keeps every row;
re-upgrade is clean; and both constraints are refused by the database under raw
SQL, not only by Python. `--autogenerate` proposes nothing for `test_run`
afterwards — the only drift it still reports is the pre-existing
`investigation_event` constraint rename first raised in #34, which belongs to
another owner's table.

## Tests

| What | Where |
|---|---|
| A plan edited after execution cannot change an existing comparison | `TestFrozenRunIdentity::test_editing_the_plan_cannot_change_an_existing_comparison` |
| The snapshot itself does not move when the plan does | `…::test_the_snapshot_is_not_rewritten_by_a_later_plan_edit` |
| Repeated run creation yields one stable snapshot each | `…::test_each_created_run_gets_its_own_stable_snapshot` |
| A legacy run is refused explicitly, not inferred | `…::test_a_legacy_run_is_refused_explicitly_not_inferred`, `…::test_a_legacy_run_cannot_be_selected_as_a_baseline` |
| A clamped run is refused rather than compared | `…::test_a_clamped_run_is_refused_rather_than_compared` |
| Unknown identity outranks clamping | `…::test_identity_is_reported_before_clamping` |
| `run_facts` structurally cannot reach a plan | `…::test_run_facts_never_touches_the_plan` |

Each behavioural test above was run against the pre-#68 `run_facts` first and
fails there — the plan edit flips the comparison, and the legacy and clamped
runs compare successfully. A regression test that passes before the fix is not
one.

## Consumer impact

Additive. No existing field changed type or meaning, and no response shape
changed.

- `packages/schemas/typescript/types.ts` gains four members on the
  `IncompatibleReason` union. A consumer that already branches on that union
  and has a default arm keeps working; one that switches exhaustively will get
  a compile error, which is the point of the union being typed.
- **#39** (comparison UI) and **#67** (comparison export) are the affected
  consumers. Both need the two new families rendered as *explanations* rather
  than errors: "too old to compare" and "clamped, so not comparable", not
  "something went wrong".
- Nothing needs to read `scenario_fingerprint` off a run. It is not exposed on
  the run response; if a consumer wants comparison provenance, that is a
  separate additive change to agree on rather than to assume.
