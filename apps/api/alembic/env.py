"""Alembic environment.

Reads the connection URL from DATABASE_URL (never from alembic.ini, so no
connection string is committed) and autogenerates against the metadata in
apps/api/db/models.py.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# `models` is imported for its side effect: importing it registers every
# table on Base.metadata. Without it, autogenerate sees an empty schema and
# cheerfully writes a migration that drops the entire database.
from apps.api.db import models  # noqa: F401
from apps.api.db.base import Base, get_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_database_url())

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):  # noqa: ANN001, ANN201
    """Keep alembic's own bookkeeping table out of autogenerate."""
    if type_ == "table" and name == "alembic_version":
        return False
    return True


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting — `alembic upgrade head --sql`.

    Useful when a DBA has to review or apply the DDL by hand rather than
    letting the app connect with migration rights.
    """
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect and apply migrations."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Without these two, autogenerate silently ignores a column whose
            # type or server default changed — the most common way a
            # migration set drifts from its models.
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
