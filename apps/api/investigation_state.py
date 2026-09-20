"""Shared persistence helpers for the Phase 2 investigation state contract."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.schemas.python.agent_io import (
    ExperimentBudget,
    OrchestratorEvent,
    OrchestratorEventType,
)
from packages.schemas.python.entities import InvestigationEventType

from .db import models as m


def append_event(
    session: Session,
    investigation_id: UUID,
    event_type: InvestigationEventType,
    payload: dict[str, Any] | None = None,
    *,
    idempotency_key: str | None = None,
) -> m.InvestigationEvent:
    """Append one ordered event while serializing writers per investigation.

    Callers make their state mutation in the same transaction. The row lock
    and unique idempotency key make duplicate HTTP/Celery delivery return the
    existing event rather than creating a second transition.
    """
    investigation = session.scalar(
        select(m.Investigation).where(m.Investigation.id == investigation_id).with_for_update()
    )
    if investigation is None:
        raise ValueError(f"unknown investigation: {investigation_id}")

    if idempotency_key:
        existing = session.scalar(
            select(m.InvestigationEvent).where(
                m.InvestigationEvent.investigation_id == investigation_id,
                m.InvestigationEvent.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing

    investigation.event_sequence += 1
    event = m.InvestigationEvent(
        investigation_id=investigation_id,
        sequence=investigation.event_sequence,
        event_type=event_type,
        payload=payload or {},
        idempotency_key=idempotency_key,
    )
    session.add(event)
    session.flush()
    return event


def event_contract(event: m.InvestigationEvent) -> OrchestratorEvent:
    return OrchestratorEvent(
        id=event.id,
        sequence=event.sequence,
        type=OrchestratorEventType(event.event_type.value),
        payload=dict(event.payload),
        idempotency_key=event.idempotency_key,
        occurred_at=event.created_at,
    )


def budget_contract(investigation: m.Investigation) -> ExperimentBudget:
    max_experiments = max(0, investigation.max_experiments)
    consumed = max(0, investigation.experiments_run)
    remaining = max(0, max_experiments - consumed)
    return ExperimentBudget(
        max_experiments=max_experiments,
        consumed=consumed,
        remaining=remaining,
        exhausted=remaining == 0,
    )
