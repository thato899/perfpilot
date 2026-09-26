"""Scenario identity — what makes two runs the *same experiment* (issue #34).

Target, test type and concurrency are not enough. Two plans can agree on all
three and still describe substantially different tests: a five-minute soak of
`["browse"]` and a forty-minute ramp through `["browse", "checkout", "search"]`
share a target, a type and a peak VU count. Comparing them produces numbers
that look like a regression and are really a change of experiment. This module
defines the identity that closes that gap, and `apps/api/baselines.py` enforces
it.

Three properties the identity has to have, and how each is obtained:

**Stable.** The same scenario must fingerprint identically today and in six
weeks, on any machine. So the document is canonicalised before hashing —
sorted keys, no insignificant whitespace, integral floats narrowed to ints —
and hashed with SHA-256 rather than Python's salted `hash()`.

**Versioned.** `v1:` prefixes every fingerprint. If the field set or the
canonical form ever changes, previously stored fingerprints do not silently
start meaning something else: they carry a version this module no longer
recognises, and the comparison is refused with a reason that says exactly
that. A fingerprint whose rule you cannot name is worse than no fingerprint.

**Explainable.** The fingerprint alone can only say "different". The
normalized document is therefore stored beside it, so a refusal can name the
fields that actually differ instead of printing two hashes at the caller.

## What is in the identity, and what is deliberately out

In, because each one changes what load is generated or what is exercised:

| Field | Why |
|---|---|
| `test_type` | A stress test is not a load test |
| `target_concurrency` | More load reads as a regression |
| `ramp_strategy` | How load arrives changes the numbers it produces |
| `stages` | The ramp profile itself |
| `duration` | A 5-minute and a 40-minute run are different experiments |
| `user_journeys` | Different work exercises different code |

Out, with reasons, because compatibility should not be stricter than the
question being asked:

- `rationale` — prose. Rewording why a plan exists does not change the test.
- `thresholds`, `success_criteria` — the pass/fail judgement applied *to* the
  measurements, not the measurements. Two runs with identical load and
  different thresholds produced their numbers the same way, and those numbers
  are what a comparison compares.
- `controlled_variable` — the field that records what an experiment
  deliberately varies. Putting it in the identity would make every experiment
  incomparable with the baseline it was designed to be measured against,
  which is the opposite of this ticket.
- `status`, ids, timestamps — not scenario at all.

`test_type` and `target_concurrency` are inside the fingerprint so it is a
complete plan identity rather than a partial one, but `check_pair` tests them
individually *first*. A caller who changes the test type therefore gets
`test_type_mismatch`, which names the problem, rather than a generic
`scenario_mismatch` that does not.

## Ordering is treated as significant

`stages` is an ordered ramp, so its order is obviously meaningful. Lists are
not reordered anywhere else either, including `user_journeys`, where an
argument could be made that order is incidental. The asymmetry of the two
mistakes decides it: a spurious refusal is visible, names the field, and can
be fixed by re-selecting a baseline, while a spurious *match* silently
compares two different experiments and reports the difference as a
regression. Only one of those is self-correcting.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

SCENARIO_FINGERPRINT_VERSION = "v1"

#: The plan attributes hashed into a v1 fingerprint. Named here rather than
#: inline so a reviewer can see the whole contract in one place, and so
#: changing it is visibly a change that needs a new version.
SCENARIO_FIELDS_V1: tuple[str, ...] = (
    "test_type",
    "target_concurrency",
    "ramp_strategy",
    "user_journeys",
    "duration",
    "stages",
)


def _canonical(value: Any) -> Any:
    """Reduce a JSONB-shaped value to one canonical Python form.

    The only transformation with teeth is the numeric one: Postgres round-trips
    a JSONB number as `int`, `float` or `Decimal` depending on how it was
    written, so `{"seconds": 300}` and `{"seconds": 300.0}` would otherwise
    hash differently while describing the same five minutes.

    Anything that is not a JSON type raises rather than being coerced with
    `str()`. JSONB cannot contain anything else, so a surprise here means the
    caller passed something that is not a scenario — and quietly fingerprinting
    its `repr` would produce a stable-looking hash of the wrong thing.
    """
    if value is None or isinstance(value, (str, bool)):
        # bool before int on purpose: bool is a subclass of int, and True must
        # stay True rather than becoming 1.
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, (float, Decimal)):
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            raise ValueError(f"scenario field is not a finite number: {value!r}")
        return int(number) if number.is_integer() else number
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    raise TypeError(f"scenario field has a non-JSON type: {type(value).__name__}")


def scenario_document(plan: Any) -> dict[str, Any]:
    """The canonical scenario of a test plan, ready to hash or store.

    Takes the plan rather than a dict so there is exactly one place that
    decides which attributes count, and `test_type` is read through `.value`
    so the identity is the enum's stable wire string rather than its Python
    repr.
    """
    raw: dict[str, Any] = {}
    for field in SCENARIO_FIELDS_V1:
        value = getattr(plan, field)
        raw[field] = value.value if hasattr(value, "value") else value
    return _canonical(raw)


def fingerprint(document: dict[str, Any]) -> str:
    """`v1:<sha256>` over the canonical JSON encoding of `document`.

    `sort_keys` is what makes the encoding canonical; `separators` removes the
    insignificant whitespace; `ensure_ascii=False` keeps a journey named in
    non-ASCII characters hashing as itself rather than as its escape sequence.
    SHA-256 rather than `hash()` because the latter is salted per process and
    would give a different answer on every restart.
    """
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{SCENARIO_FINGERPRINT_VERSION}:{digest}"


def plan_fingerprint(plan: Any) -> tuple[str, dict[str, Any]]:
    """Both halves of the identity for a plan, computed once."""
    document = scenario_document(plan)
    return fingerprint(document), document


def fingerprint_version(value: str) -> str:
    """The version prefix of a stored fingerprint, or `""` if it has none."""
    prefix, separator, _ = value.partition(":")
    return prefix if separator else ""


def differing_fields(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Which top-level scenario fields differ, sorted.

    Top-level only: naming `stages` is the useful answer, and walking into a
    ramp profile to report `stages[2].duration_s` would put the plan's internals
    into an error body for very little gain.
    """
    return sorted(
        field for field in set(baseline) | set(current) if baseline.get(field) != current.get(field)
    )
