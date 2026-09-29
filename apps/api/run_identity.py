"""Freezing a run's scenario identity at creation — issue #68.

#34 froze the *baseline* side of a comparison and read the *current* run's
identity live from its `TestPlan`. That asymmetry was documented as a known
limitation at the time, and this module is the fix: editing a plan after a run
has executed can no longer change whether that run's historical result appears
comparable, because the run carries its own snapshot.

Everything here exists to make one rule structural rather than remembered:

    A TestRun cannot be created without a scenario identity.

There are three places a run is created — plan approval, the first run of an
investigation, and an approved experiment's run — and a fourth will be added
eventually. Rather than repeating the snapshot at each call site and hoping
nobody forgets, they all go through `new_test_run`, which is the only
supported way to build the row. A forgotten snapshot would not fail loudly; it
would quietly produce a run that can never be compared, which is the sort of
bug that is found months later by someone wondering why their comparison is
refused.

## What is *not* here

No backfill for pre-existing runs. Their identity is unknown and stays
unknown; `apps/api/baselines.py` refuses comparisons that involve them with a
typed reason. Reconstructing a snapshot from a plan that may have been edited
in the meantime would produce a value that looks authoritative and isn't,
which is precisely the failure #68 exists to remove.

No update path either. The snapshot is written by the INSERT and never
touched again — not when the run starts, not when it completes, not when it is
retried. A Celery retry re-executes the same row, so it sees the same
snapshot; a genuinely new request creates a new row with its own.

## Clamping

A run can be accepted at 1000 VUs and executed at 500 when the safety ceiling
bites, and `TestRun.clamped` records that. The snapshot deliberately keeps
saying 1000, because that is what was accepted and the column has to mean one
thing consistently. The discrepancy is not swept up: `baselines.py` refuses to
compare a clamped run at all, rather than comparing it as though 1000 VUs of
load had been generated. See `docs/phase3/p3-api-1-run-identity.md`.
"""

from __future__ import annotations

import uuid
from typing import Any

from packages.schemas.python.entities import TestRunStatus

from .db import models as m
from .errors import unprocessable
from .scenario_identity import plan_fingerprint


def new_test_run(
    *,
    plan: m.TestPlan,
    target_id: uuid.UUID,
    status: TestRunStatus = TestRunStatus.QUEUED,
    **extra: Any,
) -> m.TestRun:
    """Build a TestRun carrying the frozen identity of the plan it will run.

    Keyword-only on purpose: `test_plan_id` and `target_id` are both UUIDs, and
    a positional swap between them is a silent, plausible-looking bug that the
    type checker cannot catch.

    A plan whose scenario cannot be normalized is rejected here, at creation,
    with a typed 422 rather than an unhandled TypeError several frames away.
    The ticket is explicit about this: never create a run whose comparison
    identity would be falsely inferred. Refusing to start is the safe failure;
    starting with a bad identity is not.
    """
    try:
        fingerprint, document = plan_fingerprint(plan)
    except (TypeError, ValueError) as reason:
        raise unprocessable(
            "scenario_identity_invalid",
            "The test plan's scenario could not be normalized into a comparable identity.",
            {"test_plan_id": str(plan.id), "reason": str(reason)},
        ) from reason

    return m.TestRun(
        test_plan_id=plan.id,
        target_id=target_id,
        status=status,
        scenario_fingerprint=fingerprint,
        scenario=document,
        **extra,
    )
