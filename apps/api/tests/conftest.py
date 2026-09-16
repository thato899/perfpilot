"""Test fixtures: a migrated database and an authenticated client.

The database is real Postgres with Alembic migrations applied, not SQLite
and not a mock. The models use JSONB and native Postgres ENUMs, so anything
else would be testing a different schema than the one that ships — and the
migration set itself is what issue #11 delivered, so exercising it here
keeps the two honest.

Skipped rather than failed when no database is reachable: `pytest` has to
stay green for teammates who haven't started the compose stack, since CI
runs the whole suite on every PR regardless of who opened it.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest


def _env(name: str) -> str | None:
    """os.environ.get, but an empty value counts as unset.

    A variable exported as "" is a real and easy mistake (`export A=x B=$A`
    expands $A before A is assigned), and letting "" through produces a
    baffling SQLAlchemy parse error several frames away instead of falling
    back to the default.
    """
    value = os.environ.get(name)
    return value if value else None


TEST_DB_URL = (
    _env("TEST_DATABASE_URL")
    or _env("DATABASE_URL")
    or "postgresql://perfpilot:perfpilot@localhost:5432/perfpilot"
)

# Set before importing anything that reads it at import time (db.base builds
# its engine on import).
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ.setdefault("API_AUTH_SECRET", "test-secret-do-not-use-in-production")
os.environ.setdefault("ALLOWED_TARGET_HOSTS", "localhost,demo.perfpilot.local")

sqlalchemy = pytest.importorskip("sqlalchemy", reason="apps/api dependencies not installed")
pytest.importorskip("fastapi", reason="apps/api dependencies not installed")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from apps.api.config import get_settings  # noqa: E402
from apps.api.db import models as m  # noqa: E402
from apps.api.db.base import Base  # noqa: E402
from apps.api.main import app  # noqa: E402

AUTH = {"Authorization": f"Bearer {os.environ['API_AUTH_SECRET']}"}


def _database_reachable() -> bool:
    try:
        engine = create_engine(TEST_DB_URL.replace("postgresql://", "postgresql+psycopg://", 1))
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _database_reachable(), reason=f"no Postgres reachable at {TEST_DB_URL}"
)


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    """Create the schema once for the session.

    Uses Base.metadata rather than shelling out to Alembic: the drift check
    in #11 proves the two produce the same schema, and going through
    metadata keeps the suite runnable without an alembic.ini on the path.
    """
    if not _database_reachable():
        yield
        return
    engine = create_engine(TEST_DB_URL.replace("postgresql://", "postgresql+psycopg://", 1))
    Base.metadata.drop_all(engine)
    with engine.connect() as conn:
        # drop_all leaves ENUM types behind — the same Alembic gap #11's
        # downgrade() had to work around.
        for enum_name in (
            "agent_name",
            "experiment_conclusion",
            "hypothesis_status",
            "investigation_objective",
            "investigation_status",
            "severity",
            "test_plan_status",
            "test_run_status",
            "test_type",
        ):
            conn.execute(text(f"DROP TYPE IF EXISTS {enum_name} CASCADE"))
        conn.commit()
    Base.metadata.create_all(engine)
    get_settings.cache_clear()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    """Truncate between tests so each one starts from an empty database.

    TRUNCATE ... CASCADE rather than per-test transactions: the endpoints
    commit, so a wrapping transaction would have to be rolled back at a
    level the app doesn't know about, and that tends to hide bugs where a
    handler commits something it shouldn't.
    """
    yield
    if not _database_reachable():
        return
    engine = create_engine(TEST_DB_URL.replace("postgresql://", "postgresql+psycopg://", 1))
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        conn.commit()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def project(client: TestClient) -> dict:
    res = client.post("/api/projects", json={"name": "Demo project"}, headers=AUTH)
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture
def target(client: TestClient, project: dict) -> dict:
    res = client.post(
        f"/api/projects/{project['id']}/targets",
        json={
            "base_url": "https://demo.perfpilot.local",
            "name": "demo app",
            "authorization_confirmed": True,
            "authorization_confirmed_by": "kamogelo",
        },
        headers=AUTH,
    )
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture
def test_plan(client: TestClient, project: dict, target: dict) -> dict:
    res = client.post(
        "/api/tests/plan",
        json={
            "project_id": project["id"],
            "target_id": target["id"],
            "objective": "determine_capacity",
            "user_journeys": ["browse", "checkout"],
            "expected_traffic": {"normal_concurrent_users": 200, "peak_concurrent_users": 1000},
            "p95_ms": 2000.0,
            "max_error_rate": 0.01,
        },
        headers=AUTH,
    )
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture
def db_session() -> Iterator[object]:
    """Direct session, for seeding rows no endpoint creates yet.

    Findings, hypotheses and reports are written by agents (#2/#4/#15), not
    by this API — but the read endpoints that serve them still need testing,
    so those rows are inserted directly.
    """
    from apps.api.db.base import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_uuid() -> str:
    return str(uuid.uuid4())


__all__ = ["AUTH", "make_uuid", "m"]
