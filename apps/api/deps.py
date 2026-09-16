"""Shared FastAPI dependencies: auth, database session, Orchestrator.

The Orchestrator is injected here rather than imported directly by routers,
so swapping the stub for Thatayaone's real implementation is a one-line
change in this file and touches no endpoint code — the seam
team-workflow.md#how-the-contracts-enable-parallel-work describes.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .db.base import SessionLocal
from .errors import unauthorized
from .orchestrator_stub import StubOrchestrator

# Protocol the routers depend on. Today it's only satisfied by the stub;
# agents/orchestrator will satisfy it too, unchanged on this side.
Orchestrator = StubOrchestrator


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

    Returns the stub today. When agents/orchestrator lands, this returns
    that instead; every router keeps calling the same methods.
    """
    return StubOrchestrator()


# Annotated aliases rather than `= Depends(...)` defaults. Both work in
# FastAPI, but a call in an argument default trips ruff's B008 on every
# handler — and silencing that would mean loosening pyproject.toml, a shared
# root file, to suit one app. This is also the style FastAPI's own docs now
# lead with.
DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
OrchestratorDep = Annotated[Orchestrator, Depends(get_orchestrator)]
