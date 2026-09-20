"""Phase 2 investigation state, experiment lifecycle, and event history.

Revision ID: 4b7e0c2f1a35
Revises: 81f156df0484
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "4b7e0c2f1a35"
down_revision: str | None = "81f156df0484"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE experiment_status AS ENUM "
        "('proposed', 'approved', 'queued', 'running', 'succeeded', 'failed', 'rejected')"
    )
    op.execute(
        "CREATE TYPE investigation_event_type AS ENUM "
        "('investigation_created', 'test_run_queued', 'test_run_started', "
        "'test_run_completed', 'finding_recorded', 'hypothesis_recorded', "
        "'experiment_proposed', 'experiment_approved', 'experiment_started', "
        "'experiment_completed', 'budget_exhausted', 'continue_requested', "
        "'report_persisted', 'recommendation_recorded')"
    )

    op.add_column(
        "investigation",
        sa.Column("max_experiments", sa.Integer(), server_default="3", nullable=False),
    )
    op.add_column(
        "investigation",
        sa.Column("event_sequence", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("finding", sa.Column("sequence_index", sa.Integer(), nullable=True))
    op.add_column("hypothesis", sa.Column("sequence_index", sa.Integer(), nullable=True))
    op.add_column("recommendation", sa.Column("sequence_index", sa.Integer(), nullable=True))

    op.add_column(
        "experiment",
        sa.Column(
            "status",
            postgresql.ENUM(name="experiment_status", create_type=False),
            server_default="proposed",
            nullable=False,
        ),
    )
    op.add_column("experiment", sa.Column("sequence_index", sa.Integer(), nullable=True))
    op.add_column("experiment", sa.Column("idempotency_key", sa.String(length=255)))
    op.alter_column("experiment", "test_plan_id", existing_type=sa.Uuid(), nullable=True)
    op.alter_column("experiment", "test_run_id", existing_type=sa.Uuid(), nullable=True)
    op.alter_column(
        "experiment", "baseline_value", existing_type=postgresql.JSONB(), nullable=True
    )
    op.alter_column(
        "experiment", "experiment_value", existing_type=postgresql.JSONB(), nullable=True
    )
    op.create_unique_constraint("uq_experiment_idempotency_key", "experiment", ["idempotency_key"])

    # Existing rows were execution records before lifecycle status existed.
    # Preserve their meaning instead of presenting completed runs as proposals.
    op.execute(
        "UPDATE experiment SET status = CASE "
        "WHEN EXISTS (SELECT 1 FROM experiment_result r WHERE r.experiment_id = experiment.id) "
        "THEN 'succeeded'::experiment_status "
        "WHEN EXISTS (SELECT 1 FROM test_run tr WHERE tr.id = experiment.test_run_id "
        "AND tr.status = 'failed') THEN 'failed'::experiment_status "
        "WHEN EXISTS (SELECT 1 FROM test_run tr WHERE tr.id = experiment.test_run_id "
        "AND tr.status = 'running') THEN 'running'::experiment_status "
        "ELSE 'queued'::experiment_status END"
    )

    op.create_table(
        "investigation_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "event_type",
            postgresql.ENUM(name="investigation_event_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"], ["investigation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_investigation_event"),
        sa.UniqueConstraint("investigation_id", "sequence", name="uq_investigation_event_sequence"),
        sa.UniqueConstraint(
            "investigation_id", "idempotency_key", name="uq_investigation_event_idempotency_key"
        ),
    )
    op.create_index(
        "ix_investigation_event_investigation_id",
        "investigation_event",
        ["investigation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_investigation_event_investigation_id", table_name="investigation_event")
    op.drop_table("investigation_event")
    op.drop_constraint("uq_experiment_idempotency_key", "experiment", type_="unique")
    op.drop_column("experiment", "idempotency_key")
    op.drop_column("experiment", "sequence_index")
    op.drop_column("experiment", "status")
    op.alter_column("experiment", "test_plan_id", existing_type=sa.Uuid(), nullable=False)
    op.alter_column("experiment", "test_run_id", existing_type=sa.Uuid(), nullable=False)
    op.alter_column(
        "experiment", "baseline_value", existing_type=postgresql.JSONB(), nullable=False
    )
    op.alter_column(
        "experiment", "experiment_value", existing_type=postgresql.JSONB(), nullable=False
    )
    op.drop_column("recommendation", "sequence_index")
    op.drop_column("hypothesis", "sequence_index")
    op.drop_column("finding", "sequence_index")
    op.drop_column("investigation", "event_sequence")
    op.drop_column("investigation", "max_experiments")
    op.execute("DROP TYPE investigation_event_type")
    op.execute("DROP TYPE experiment_status")
