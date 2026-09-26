"""Baseline eligibility and comparison assembly — issue #34 (P2-API-1).

The division of labour this module exists to hold:

- `packages/metrics` owns every calculation. Nothing here subtracts, divides
  or rounds a metric. `compare_metrics` is called and its result passed
  through untouched.
- This module owns *which* records may legitimately be compared, and says so
  in typed terms. That question is not arithmetic and it is not the metrics
  package's to answer, because it depends on the run's plan, status and
  target — persistence concerns.
- The AI selects nothing. A baseline is chosen by a person through the API
  and persisted; no agent picks one and no endpoint falls back to "the most
  recent run" when the requested one is unsuitable.

The last point is the ticket's actual complaint: *"Users must compare a run
with an intentional prior run, not an unrelated or silently selected
result."* Every function below therefore either returns a comparison for the
exact pair asked for, or refuses with a reason. There is no third branch that
quietly substitutes something else, and no path that treats missing data as
zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.metrics.metrics import MetricComparison, compare_metrics
from packages.schemas.python.entities import Metric as MetricSchema
from packages.schemas.python.entities import TestRunStatus

from .db import models as m
from .scenario_identity import (
    SCENARIO_FINGERPRINT_VERSION,
    differing_fields,
    fingerprint_version,
    plan_fingerprint,
)


class IncompatibleReason(str, Enum):
    """Why a baseline and a current run may not be compared.

    A closed set rather than free text: these are the values the API maps to
    error codes and #39 will branch on, so they are contract, not prose. The
    human-readable sentence lives alongside in `REASON_MESSAGES`.
    """

    BASELINE_RUN_NOT_SUCCEEDED = "baseline_run_not_succeeded"
    CURRENT_RUN_NOT_SUCCEEDED = "current_run_not_succeeded"
    ENVIRONMENT_MISMATCH = "environment_mismatch"
    TEST_TYPE_MISMATCH = "test_type_mismatch"
    CONCURRENCY_MISMATCH = "concurrency_mismatch"
    SCENARIO_MISMATCH = "scenario_mismatch"
    SCENARIO_IDENTITY_UNSUPPORTED = "scenario_identity_unsupported"
    BASELINE_METRICS_UNAVAILABLE = "baseline_metrics_unavailable"
    CURRENT_METRICS_UNAVAILABLE = "current_metrics_unavailable"
    NO_SHARED_ENDPOINT = "no_shared_endpoint"


REASON_MESSAGES: dict[IncompatibleReason, str] = {
    IncompatibleReason.BASELINE_RUN_NOT_SUCCEEDED: (
        "The baseline's test run did not succeed, so its metrics do not describe a completed test."
    ),
    IncompatibleReason.CURRENT_RUN_NOT_SUCCEEDED: (
        "The current test run has not succeeded, so there is nothing final to compare."
    ),
    IncompatibleReason.ENVIRONMENT_MISMATCH: (
        "The baseline and the current run were executed against different targets."
    ),
    IncompatibleReason.TEST_TYPE_MISMATCH: (
        "The baseline and the current run are different test types."
    ),
    IncompatibleReason.CONCURRENCY_MISMATCH: (
        "The baseline and the current run were planned for different concurrency levels."
    ),
    IncompatibleReason.SCENARIO_MISMATCH: (
        "The baseline and the current run describe different scenarios, "
        "so a difference between them would not be a difference in performance."
    ),
    IncompatibleReason.SCENARIO_IDENTITY_UNSUPPORTED: (
        "The baseline's scenario identity was recorded under a rule this version "
        "no longer recognises, so it cannot be compared. Re-select the baseline."
    ),
    IncompatibleReason.BASELINE_METRICS_UNAVAILABLE: (
        "The baseline's test run has no recorded metrics."
    ),
    IncompatibleReason.CURRENT_METRICS_UNAVAILABLE: (
        "The current test run has no recorded metrics."
    ),
    IncompatibleReason.NO_SHARED_ENDPOINT: (
        "The two runs recorded metrics, but for no endpoint in common."
    ),
}


@dataclass(frozen=True)
class Incompatible:
    """A refusal, with the evidence that produced it."""

    reason: IncompatibleReason
    detail: dict[str, object]

    @property
    def message(self) -> str:
        return REASON_MESSAGES[self.reason]


@dataclass(frozen=True)
class RunFacts:
    """The compatibility identity of one run.

    Deliberately a value object rather than an ORM row: eligibility is decided
    from these facts alone, and passing them explicitly keeps the rules
    readable and unit-testable without a database.

    `scenario_fingerprint` is the stable identity defined in
    `scenario_identity.py`; `scenario` is the canonical document it was
    computed from, carried alongside so a refusal can name the fields that
    differ rather than printing two hashes at the caller.
    """

    test_run_id: UUID
    target_id: UUID
    status: TestRunStatus
    test_type: str
    target_concurrency: int
    scenario_fingerprint: str
    scenario: Mapping[str, Any]


def run_facts(session: Session, run: m.TestRun) -> RunFacts:
    """Read a run's compatibility identity from its plan.

    The *current* run's type and concurrency are read live from its plan,
    while a baseline's are frozen on the baseline row at selection time. That
    asymmetry is intentional: the current run is being judged now, whereas a
    baseline has to keep meaning what it meant when someone chose it.
    """
    plan = session.get(m.TestPlan, run.test_plan_id)
    if plan is None:  # pragma: no cover - FK makes this unreachable
        raise ValueError(f"test run {run.id} has no plan")
    scenario_fingerprint, scenario = plan_fingerprint(plan)
    return RunFacts(
        test_run_id=run.id,
        target_id=run.target_id,
        status=run.status,
        test_type=plan.test_type.value,
        target_concurrency=plan.target_concurrency,
        scenario_fingerprint=scenario_fingerprint,
        scenario=scenario,
    )


def baseline_facts(baseline: m.Baseline) -> RunFacts:
    return RunFacts(
        test_run_id=baseline.test_run_id,
        target_id=baseline.target_id,
        # A baseline is only ever created from a succeeded run, and the row
        # records the selection rather than the run's mutable state.
        status=TestRunStatus.SUCCEEDED,
        test_type=baseline.test_type.value,
        target_concurrency=baseline.target_concurrency,
        scenario_fingerprint=baseline.scenario_fingerprint,
        scenario=baseline.scenario,
    )


def check_eligibility(run: RunFacts, *, as_baseline: bool) -> Incompatible | None:
    """Whether one run may take part in a comparison at all.

    Split from `check_pair` so the selection endpoint can reject an unsuitable
    run at the moment someone tries to promote it, rather than letting a bad
    baseline sit in the table until the first comparison fails.
    """
    if run.status is not TestRunStatus.SUCCEEDED:
        return Incompatible(
            reason=(
                IncompatibleReason.BASELINE_RUN_NOT_SUCCEEDED
                if as_baseline
                else IncompatibleReason.CURRENT_RUN_NOT_SUCCEEDED
            ),
            detail={"test_run_id": str(run.test_run_id), "status": run.status.value},
        )
    return None


def check_pair(baseline: RunFacts, current: RunFacts) -> Incompatible | None:
    """Whether these two specific runs describe the same experiment.

    Ordered cheapest-and-most-fundamental first, so the reported reason is the
    most useful one: being on a different target makes the type and
    concurrency questions moot.
    """
    for side, as_baseline in ((baseline, True), (current, False)):
        failure = check_eligibility(side, as_baseline=as_baseline)
        if failure is not None:
            return failure

    # The target is the environment. Same target means the same base URL and
    # the same authorization record, which is what makes two runs comparable;
    # different targets are different systems and are refused rather than
    # compared. See docs/phase2/p2-api-1-baselines.md.
    if baseline.target_id != current.target_id:
        return Incompatible(
            reason=IncompatibleReason.ENVIRONMENT_MISMATCH,
            detail={
                "baseline_target_id": str(baseline.target_id),
                "current_target_id": str(current.target_id),
            },
        )

    if baseline.test_type != current.test_type:
        return Incompatible(
            reason=IncompatibleReason.TEST_TYPE_MISMATCH,
            detail={
                "baseline_test_type": baseline.test_type,
                "current_test_type": current.test_type,
            },
        )

    # Same scenario shape, not necessarily the same plan row: re-planning the
    # same scenario should not silently disqualify every historical baseline.
    # A 200-VU run against a 1000-VU one is a different experiment, though, and
    # comparing them would read as a regression that is really a load change.
    if baseline.target_concurrency != current.target_concurrency:
        return Incompatible(
            reason=IncompatibleReason.CONCURRENCY_MISMATCH,
            detail={
                "baseline_target_concurrency": baseline.target_concurrency,
                "current_target_concurrency": current.target_concurrency,
            },
        )

    # The rest of the scenario: ramp strategy, stages, duration, journeys.
    # Target, type and concurrency can all agree while the two plans still
    # describe substantially different tests — a short soak of one journey
    # against a long ramp through three — and comparing those reports a change
    # of experiment as a change in performance. scenario_identity.py defines
    # what counts and why.
    if baseline.scenario_fingerprint != current.scenario_fingerprint:
        recorded_version = fingerprint_version(baseline.scenario_fingerprint)
        if recorded_version != SCENARIO_FINGERPRINT_VERSION:
            # The stored identity was computed under a rule this build no
            # longer knows, so "they differ" is not something we can honestly
            # conclude. Say that instead of reporting a scenario change that
            # may not have happened.
            return Incompatible(
                reason=IncompatibleReason.SCENARIO_IDENTITY_UNSUPPORTED,
                detail={
                    "baseline_scenario_identity_version": recorded_version,
                    "supported_scenario_identity_version": SCENARIO_FINGERPRINT_VERSION,
                },
            )
        return Incompatible(
            reason=IncompatibleReason.SCENARIO_MISMATCH,
            detail={
                "differing_fields": differing_fields(
                    dict(baseline.scenario), dict(current.scenario)
                ),
                "baseline_scenario_fingerprint": baseline.scenario_fingerprint,
                "current_scenario_fingerprint": current.scenario_fingerprint,
            },
        )

    return None


def load_metrics(session: Session, test_run_id: UUID) -> list[m.Metric]:
    return list(
        session.scalars(
            select(m.Metric)
            .where(m.Metric.test_run_id == test_run_id)
            .order_by(m.Metric.recorded_at, m.Metric.id)
        ).all()
    )


@dataclass(frozen=True)
class ComparisonResult:
    """One comparison per endpoint present on both sides, plus what was not.

    `unmatched` is reported rather than dropped for the same reason an
    unrecognised event is rendered rather than hidden: an endpoint measured in
    only one of the two runs is a real difference between them, and silently
    omitting it would make the comparison look more complete than it is.
    """

    comparisons: list[MetricComparison]
    baseline_only_endpoints: list[str | None]
    current_only_endpoints: list[str | None]


def _by_endpoint(metrics: list[m.Metric]) -> dict[str | None, m.Metric]:
    """Index metrics by endpoint, keeping the most recently recorded per scope.

    A run can record the same endpoint more than once when metrics are
    collected at intervals rather than only at completion (database-design.md
    allows for both). The latest sample is the one that describes the finished
    run, and `load_metrics` orders by `recorded_at` so the last write wins.
    """
    indexed: dict[str | None, m.Metric] = {}
    for metric in metrics:
        indexed[metric.endpoint] = metric
    return indexed


def build_comparison(
    *,
    baseline_run_id: UUID,
    current_run_id: UUID,
    baseline_metrics: list[m.Metric],
    current_metrics: list[m.Metric],
) -> ComparisonResult | Incompatible:
    """Pair metrics by endpoint and hand each pair to packages/metrics.

    Endpoint scope is the pairing key because that is the axis
    `compare_metrics` itself refuses to cross; matching on anything else would
    only produce `incompatible` results from the layer below. The aggregate
    row (endpoint `None`) is paired like any other scope.
    """
    if not baseline_metrics:
        return Incompatible(
            reason=IncompatibleReason.BASELINE_METRICS_UNAVAILABLE,
            detail={"test_run_id": str(baseline_run_id)},
        )
    if not current_metrics:
        return Incompatible(
            reason=IncompatibleReason.CURRENT_METRICS_UNAVAILABLE,
            detail={"test_run_id": str(current_run_id)},
        )

    baseline_index = _by_endpoint(baseline_metrics)
    current_index = _by_endpoint(current_metrics)
    shared = set(baseline_index) & set(current_index)

    if not shared:
        return Incompatible(
            reason=IncompatibleReason.NO_SHARED_ENDPOINT,
            detail={
                "baseline_endpoints": sorted(e for e in baseline_index if e is not None),
                "current_endpoints": sorted(e for e in current_index if e is not None),
            },
        )

    # Aggregate first, then endpoints alphabetically: a stable order, with the
    # whole-run number where a reader looks first.
    ordered = sorted(shared, key=lambda endpoint: (endpoint is not None, endpoint or ""))

    comparisons = [
        compare_metrics(
            MetricSchema.model_validate(baseline_index[endpoint], from_attributes=True),
            MetricSchema.model_validate(current_index[endpoint], from_attributes=True),
        )
        for endpoint in ordered
    ]

    return ComparisonResult(
        comparisons=comparisons,
        baseline_only_endpoints=sorted(
            (e for e in set(baseline_index) - shared), key=lambda e: (e is not None, e or "")
        ),
        current_only_endpoints=sorted(
            (e for e in set(current_index) - shared), key=lambda e: (e is not None, e or "")
        ),
    )
