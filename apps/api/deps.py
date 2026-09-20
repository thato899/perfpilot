"""Shared FastAPI dependencies: auth, database session, Orchestrator.

The Orchestrator is injected here rather than imported directly by routers.
Production resolves the real implementation while tests can install an
explicit stub, preserving the seam described in
team-workflow.md#how-the-contracts-enable-parallel-work.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from agents.orchestrator.orchestrator import Orchestrator as RealOrchestrator

from .config import Settings, get_settings
from .db.base import SessionLocal
from .errors import unauthorized
from .load_engineer import K6LoadEngineer
from .load_engineer_stub import StubLoadEngineer

# The API depends on public agent seams. Production resolves the real
# implementations; the Load Engineer stub is selected only by an explicit
# test/development setting.
Orchestrator = RealOrchestrator
LoadEngineer = K6LoadEngineer | StubLoadEngineer


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def require_auth(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Single static bearer token, per api-contract.md's MVP auth.

    Fails closed on an unset secret: an empty API_AUTH_SECRET means every
    request is rejected, not that every request is allowed. Getting that
    backwards would silently expose a deployment whose env var didn't load.
    """
    if not settings.api_auth_secret:
        raise unauthorized("Server has no API_AUTH_SECRET configured.")

    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise unauthorized()

    # compare_digest, not ==: a plain comparison short-circuits on the first
    # differing byte and leaks the secret's prefix to a timing attack.
    if not secrets.compare_digest(token, settings.api_auth_secret):
        raise unauthorized()


def get_orchestrator() -> Orchestrator:
    """The Orchestrator seam.

    Keep the API dependent on the public orchestrator seam, not its internals.
    """
    settings = get_settings()
    return RealOrchestrator(max_experiments=settings.max_experiments_per_investigation)


def get_load_engineer() -> LoadEngineer:
    """The Load Engineer seam — the k6 execution wrapper.

    Called from the Celery task, not from a router: execution happens off
    the request path (system-architecture.md), so this is deliberately not
    a FastAPI dependency.
    """
    settings = get_settings()
    if settings.load_engineer_mode == "stub":
        return StubLoadEngineer(settings)
    return K6LoadEngineer(settings)


# Annotated aliases rather than `= Depends(...)` defaults. Both work in
# FastAPI, but a call in an argument default trips ruff's B008 on every
# handler — and silencing that would mean loosening pyproject.toml, a shared
# root file, to suit one app. This is also the style FastAPI's own docs now
# lead with.
DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
OrchestratorDep = Annotated[Orchestrator, Depends(get_orchestrator)]
