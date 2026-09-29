"""freeze scenario identity on each test run (issue #68)

Adds `test_run.scenario_fingerprint` and `test_run.scenario`, and nothing else.

Both columns are NULLABLE and existing rows are deliberately left NULL. That is
not a backfill this migration forgot: a run created before this point has no
record of what it executed, and its `TestPlan` may have been edited since, so
any value derived from that plan would look authoritative while being
unprovable. NULL is the explicit "unknown" state, and `apps/api/baselines.py`
refuses comparisons involving such a run with a typed reason
(`{baseline,current}_run_identity_unknown`) rather than guessing.

That also makes the upgrade safe against a live database: two nullable columns
and two CHECK constraints that every existing row already satisfies, so there
is no table rewrite and nothing legacy data can fail on.

NOTE for whoever next runs `--autogenerate`: it will also want to rename four
`investigation_event` unique constraints. That is pre-existing drift between
#35's migration and the naming convention in `db/base.py` — identical columns,
different generated names — first raised during #34 and still unfixed. It is
deliberately NOT fixed here: `investigation_event` is another owner's table and
renaming its constraints inside this PR would be an unrelated schema change.

Revision ID: 18985f0f7606
Revises: 49218513a29e
Create Date: 2026-09-29 11:46:57.319067
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "18985f0f7606"
down_revision: str | None = "49218513a29e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "test_run", sa.Column("scenario_fingerprint", sa.String(length=80), nullable=True)
    )
    op.add_column(
        "test_run", sa.Column("scenario", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    # Autogenerate does not emit CHECK constraints, so both are written by hand
    # and mirror what `db/models.py` declares. The names here are the BARE
    # names: `db/base.py`'s naming convention prefixes `ck_test_run_` itself,
    # and passing an already-prefixed name produces
    # `ck_test_run_ck_test_run_...`, which then reads as permanent drift to
    # every later `--autogenerate`.
    op.create_check_constraint(
        "scenario_identity_complete",
        "test_run",
        "(scenario_fingerprint IS NULL) = (scenario IS NULL)",
    )
    op.create_check_constraint(
        "scenario_fingerprint_versioned",
        "test_run",
        "scenario_fingerprint IS NULL OR scenario_fingerprint LIKE '%:%'",
    )


def downgrade() -> None:
    # Dropping the columns would take their CHECK constraints with them, but
    # both are dropped explicitly first so a partially-applied upgrade
    # downgrades cleanly rather than failing on something unexpected.
    op.drop_constraint("scenario_fingerprint_versioned", "test_run", type_="check")
    op.drop_constraint("scenario_identity_complete", "test_run", type_="check")
    op.drop_column("test_run", "scenario")
    op.drop_column("test_run", "scenario_fingerprint")
