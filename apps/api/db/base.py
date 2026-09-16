"""Declarative base, naming conventions, and session plumbing."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import DateTime, MetaData, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

# Postgres auto-names constraints it wasn't given a name for, and those names
# differ between the database Alembic autogenerates against and any other.
# Pinning them here means a constraint can always be found by name in a
# downgrade, and autogenerate stops proposing spurious drop/create churn.
# See https://alembic.sqlalchemy.org/en/latest/naming.html
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for every model in this package."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """`created_at`/`updated_at`, per database-design.md's "All entities".

    Both defaults are `server_default`/`onupdate` at the database level rather
    than Python-side, so a row written by a migration, a psql session, or a
    future service in another language still gets correct timestamps.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def get_database_url() -> str:
    """Connection URL, from `DATABASE_URL` (see .env.example).

    Normalised to the `postgresql+psycopg` driver: `.env.example` and Render
    both supply a bare `postgresql://` URL, which SQLAlchemy would route to
    psycopg2 — a driver this project doesn't install. apps/api pins psycopg 3.
    """
    url = os.environ.get(
        "DATABASE_URL", "postgresql://perfpilot:perfpilot@localhost:5432/perfpilot"
    )
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(get_database_url(), pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Yield a session and always close it — FastAPI dependency shape.

    Left here rather than in a routers module so issue #12 can wire it up
    with `Depends(get_session)` without inventing its own.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
