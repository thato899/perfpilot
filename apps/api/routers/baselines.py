"""Baseline selection and comparison — issue #34 (P2-API-1).

Four routes: promote a run to a baseline, list a target's baselines, fetch
one, and compare a run against one. The HTTP layer here owns authorization
and persistence; `apps/api/baselines.py` owns eligibility; `packages/metrics`
owns every number. Nothing in this file does arithmetic.

The comparison route requires `baseline_id`. That is the point of the ticket
rather than an omission — an endpoint that picked a baseline when none was
named would be the "unrelated or silently selected result" it exists to stop.
When a caller does not know which baseline to use, the list route tells them.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from packages.schemas.python.entities import TestType

from ..baselines import (
    Incompatible,
    baseline_facts,
    build_comparison,
    check_eligibility,
    check_pair,
    load_metrics,
    run_facts,
)
from ..db import models as m
from ..deps import AppSettings, DbSession, require_auth
from ..errors import conflict, forbidden_target, not_found
from ..schemas import (
    BaselineRef,
    BaselinesResponse,
    ComparisonResponse,
    ErrorResponse,
    SelectBaselineRequest,
)

router = APIRouter(prefix="/api", tags=["baselines"], dependencies=[Depends(require_auth)])

ERRORS: dict[int | str, dict] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _ref(row: m.Baseline) -> BaselineRef:
    return BaselineRef(
        id=row.id,
        target_id=row.target_id,
        test_run_id=row.test_run_id,
        label=row.label,
        selected_by=row.selected_by,
        test_type=row.test_type.value,
        target_concurrency=row.target_concurrency,
        scenario_fingerprint=row.scenario_fingerprint,
    )


def _authorized_target(db: DbSession, settings: AppSettings, target_id: UUID) -> m.Target:
    """Load a target the caller is allowed to act on.

    The same two gates the rest of the API applies: the target must exist, and
    its host must still be allow-listed and confirmed. Re-checked here rather
    than trusted from whenever the target was created, because authorization
    can be revoked between then and now — and a baseline is a durable record
    that outlives the request that made it.
    """
    target = db.get(m.Target, target_id)
    if target is None:
        raise not_found("Target", target_id)
    if not target.authorization_confirmed or not settings.host_is_allowed(target.base_url):
        raise forbidden_target(target.base_url)
    return target


def _refuse(failure: Incompatible) -> None:
    raise conflict(failure.reason.value, failure.message, failure.detail)


def _by_key(db: DbSession, target_id: UUID, idempotency_key: str) -> m.Baseline | None:
    return db.scalar(
        select(m.Baseline).where(
            m.Baseline.target_id == target_id,
            m.Baseline.idempotency_key == idempotency_key,
        )
    )


def _key_reused(idempotency_key: str, existing: m.Baseline):
    """The same key, a different run — a genuine conflict, not a retry.

    Honouring it would silently change which run the caller believes is their
    baseline, which is the one thing an idempotency key is supposed to make
    impossible.
    """
    return conflict(
        "idempotency_key_reused",
        "That idempotency key was already used to select a different baseline.",
        {
            "idempotency_key": idempotency_key,
            "existing_baseline_id": str(existing.id),
            "existing_test_run_id": str(existing.test_run_id),
        },
    )


@router.post(
    "/targets/{target_id}/baselines",
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def select_baseline(
    target_id: UUID,
    body: SelectBaselineRequest,
    db: DbSession,
    settings: AppSettings,
    response: Response,
) -> BaselineRef:
    """Promote a succeeded run to a baseline for its target.

    Repeating the call with the same run is safe and returns the existing
    record with `200` rather than creating a second one or erroring — the
    ticket's idempotency requirement. A different run under a previously used
    idempotency key is a genuine conflict and is refused, because silently
    honouring it would let a retry change which run the caller believes is
    their baseline.
    """
    target = _authorized_target(db, settings, target_id)

    run = db.get(m.TestRun, body.test_run_id)
    if run is None:
        raise not_found("TestRun", body.test_run_id)
    if run.target_id != target.id:
        # Not a 404: the run exists, it simply belongs to another target, and
        # saying so is more useful than pretending it is missing. It is also
        # the environment rule applied at selection time.
        raise conflict(
            "environment_mismatch",
            "That test run was executed against a different target.",
            {"test_run_id": str(run.id), "run_target_id": str(run.target_id)},
        )

    facts = run_facts(db, run)
    failure = check_eligibility(facts, as_baseline=True)
    if failure is not None:
        _refuse(failure)

    # The key is checked BEFORE the existing-run lookup, not after. A key
    # already bound to a different run is a conflict whether or not this run
    # also happens to be a baseline already — and checking in the other order
    # let the (target, run) repeat return 200 first, so a caller retrying with
    # a key that meant something else got a success and walked away believing
    # their key now referred to this run.
    if body.idempotency_key is not None:
        replayed = _by_key(db, target.id, body.idempotency_key)
        if replayed is not None:
            if replayed.test_run_id != run.id:
                raise _key_reused(body.idempotency_key, replayed)
            response.status_code = status.HTTP_200_OK
            return _ref(replayed)

    existing = db.scalar(
        select(m.Baseline).where(
            m.Baseline.target_id == target.id,
            m.Baseline.test_run_id == run.id,
        )
    )
    if existing is not None:
        # Already a baseline, and any supplied key is free. The key is
        # deliberately not written onto the existing row: a repeat read should
        # not quietly mutate the record it is reporting, and the answer stays
        # the same however many times it is asked.
        response.status_code = status.HTTP_200_OK
        return _ref(existing)

    row = m.Baseline(
        target_id=target.id,
        test_run_id=run.id,
        label=body.label,
        selected_by=body.selected_by,
        test_type=TestType(facts.test_type),
        target_concurrency=facts.target_concurrency,
        scenario_fingerprint=facts.scenario_fingerprint,
        scenario=dict(facts.scenario),
        idempotency_key=body.idempotency_key,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Two requests raced. Which uniqueness rule they collided on decides
        # the answer, so both are re-read rather than assuming it was the run:
        # assuming that turned a concurrent key collision into a 500, which is
        # the one outcome an idempotency key exists to prevent.
        winner = db.scalar(
            select(m.Baseline).where(
                m.Baseline.target_id == target.id,
                m.Baseline.test_run_id == run.id,
            )
        )
        if winner is not None:
            response.status_code = status.HTTP_200_OK
            return _ref(winner)
        if body.idempotency_key is not None:
            claimed = _by_key(db, target.id, body.idempotency_key)
            if claimed is not None:
                raise _key_reused(body.idempotency_key, claimed) from None
        raise  # pragma: no cover - neither rule matched; not ours to swallow

    db.refresh(row)
    return _ref(row)


@router.get("/targets/{target_id}/baselines", response_model=BaselinesResponse, responses=ERRORS)
def list_baselines(target_id: UUID, db: DbSession, settings: AppSettings) -> BaselinesResponse:
    """Every baseline recorded for a target, newest first."""
    target = _authorized_target(db, settings, target_id)
    rows = db.scalars(
        select(m.Baseline)
        .where(m.Baseline.target_id == target.id)
        .order_by(m.Baseline.created_at.desc(), m.Baseline.id)
    ).all()
    return BaselinesResponse(baselines=[_ref(row) for row in rows])


@router.get("/baselines/{baseline_id}", responses=ERRORS)
def get_baseline(baseline_id: UUID, db: DbSession, settings: AppSettings) -> BaselineRef:
    row = db.get(m.Baseline, baseline_id)
    if row is None:
        raise not_found("Baseline", baseline_id)
    _authorized_target(db, settings, row.target_id)
    return _ref(row)


@router.get(
    "/test-runs/{run_id}/comparison",
    response_model=ComparisonResponse,
    responses=ERRORS,
)
def compare_against_baseline(
    run_id: UUID,
    baseline_id: UUID,
    db: DbSession,
    settings: AppSettings,
) -> ComparisonResponse:
    """Compare a run against one named baseline.

    `baseline_id` is a required query parameter. Every refusal below is a 409
    carrying the typed reason from `apps/api/baselines.py`, so a caller can
    tell "these are not comparable, and here is why" from "something broke" —
    and never receives a comparison against a baseline it did not ask for.
    """
    run = db.get(m.TestRun, run_id)
    if run is None:
        raise not_found("TestRun", run_id)
    _authorized_target(db, settings, run.target_id)

    baseline = db.get(m.Baseline, baseline_id)
    if baseline is None:
        raise not_found("Baseline", baseline_id)
    # The baseline's own target is authorized too, before anything is read out
    # of the row. Checking only the current run's target was an information
    # leak rather than a theoretical gap: naming a baseline on a target whose
    # authorization had been revoked returned a 409 whose detail carried that
    # target's id. A 403 is the right answer, and it has to come first.
    _authorized_target(db, settings, baseline.target_id)

    failure = check_pair(baseline_facts(baseline), run_facts(db, run))
    if failure is not None:
        _refuse(failure)

    result = build_comparison(
        baseline_run_id=baseline.test_run_id,
        current_run_id=run.id,
        baseline_metrics=load_metrics(db, baseline.test_run_id),
        current_metrics=load_metrics(db, run.id),
    )
    if isinstance(result, Incompatible):
        _refuse(result)

    return ComparisonResponse(
        baseline=_ref(baseline),
        current_test_run_id=run.id,
        comparisons=result.comparisons,
        baseline_only_endpoints=result.baseline_only_endpoints,
        current_only_endpoints=result.current_only_endpoints,
    )
