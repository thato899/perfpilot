"""SQLAlchemy models — the persisted form of docs/database/database-design.md.

That document is the prose source of truth; `packages/schemas/python/entities.py`
is the typed contract the API validates against; this file is what actually
exists in Postgres. All three must agree.

Enums are IMPORTED from packages/schemas rather than redeclared, so there is
exactly one definition of what `test_type` may contain. Redeclaring them here
would let the database and the contract drift apart silently, which is the
failure mode packages/schemas exists to prevent.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import DateTime as SADateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.schemas.python.entities import (
    AgentName,
    ExperimentConclusion,
    HypothesisStatus,
    InvestigationObjective,
    InvestigationStatus,
    Severity,
    TestPlanStatus,
    TestRunStatus,
    TestType,
)

from .base import Base, TimestampMixin


def pg_enum(py_enum: type[PyEnum], name: str) -> Enum:
    """Postgres ENUM that stores the enum's VALUE, not its Python name.

    SQLAlchemy's default is to persist `TestType.LOAD` as the string "LOAD".
    Every enum in packages/schemas is a `str, Enum` whose value is lowercase
    ("load"), and that value is what Pydantic serializes and what the API
    contract documents. Without `values_callable` the database would hold
    "LOAD" while every JSON payload said "load" — a mismatch that only
    surfaces on the first read-back.
    """
    return Enum(
        py_enum,
        name=name,
        values_callable=lambda enum_cls: [member.value for member in enum_cls],
    )


def pk() -> Mapped[uuid.UUID]:
    """UUID primary key — database-design.md, "All entities"."""
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


# ---------------------------------------------------------------------------
# Project / Target
# ---------------------------------------------------------------------------


class Project(TimestampMixin, Base):
    __tablename__ = "project"

    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    targets: Mapped[list[Target]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    test_plans: Mapped[list[TestPlan]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    investigations: Mapped[list[Investigation]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Target(TimestampMixin, Base):
    __tablename__ = "target"

    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # The API refuses to create a Target with authorization_confirmed=false
    # (api-contract.md returns 422), so this is never persisted false in
    # practice — but the column stays nullable=False with no default rather
    # than defaulting true, so a direct insert can't quietly bypass the check.
    authorization_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    authorization_confirmed_by: Mapped[str | None] = mapped_column(String(255))
    authorization_confirmed_at: Mapped[datetime | None] = mapped_column(SADateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="targets")
    test_plans: Mapped[list[TestPlan]] = relationship(back_populates="target")


# ---------------------------------------------------------------------------
# Test planning and execution
# ---------------------------------------------------------------------------


class TestPlan(TimestampMixin, Base):
    __tablename__ = "test_plan"

    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("target.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # A normal column, not JSONB, precisely so "find all plans with
    # test_type = stress" can be indexed — database-design.md calls this out.
    test_type: Mapped[TestType] = mapped_column(pg_enum(TestType, "test_type"), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    target_concurrency: Mapped[int] = mapped_column(Integer, nullable=False)

    # JSONB for the documented-shape-but-never-queried-inside fields. See
    # database-design.md's "Why JSONB for ramp_strategy/stages/etc."
    ramp_strategy: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    user_journeys: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    duration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    stages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    success_criteria: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    controlled_variable: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    status: Mapped[TestPlanStatus] = mapped_column(
        pg_enum(TestPlanStatus, "test_plan_status"), nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="test_plans")
    target: Mapped[Target] = relationship(back_populates="test_plans")
    test_runs: Mapped[list[TestRun]] = relationship(back_populates="test_plan")


class TestRun(TimestampMixin, Base):
    __tablename__ = "test_run"

    id: Mapped[uuid.UUID] = pk()
    test_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_plan.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("target.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[TestRunStatus] = mapped_column(
        pg_enum(TestRunStatus, "test_run_status"), nullable=False
    )
    k6_script_ref: Mapped[str | None] = mapped_column(String(1024))
    raw_output_ref: Mapped[str | None] = mapped_column(String(1024))
    clamped: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(SADateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(SADateTime(timezone=True))

    test_plan: Mapped[TestPlan] = relationship(back_populates="test_runs")
    stages_actual: Mapped[list[TestStage]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )
    metrics: Mapped[list[Metric]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Partial index for the worker's "what's still in flight" poll, per
        # database-design.md's indexing notes. Partial because finished runs
        # are the overwhelming majority and never match this predicate.
        Index(
            "ix_test_run_status_active",
            "status",
            postgresql_where="status IN ('queued', 'running')",
        ),
    )


class TestStage(TimestampMixin, Base):
    """A run's *actual* stage progression, denormalized at execution time.

    Kept separate from TestPlan.stages so clamping (see security-model.md's
    safety ceiling) is recorded as what really happened, not what was asked
    for — database-design.md is explicit about this.
    """

    __tablename__ = "test_stage"

    id: Mapped[uuid.UUID] = pk()
    test_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_vus: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_s: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)

    test_run: Mapped[TestRun] = relationship(back_populates="stages_actual")

    __table_args__ = (
        # Not stated in database-design.md, but implied by "sequence": two
        # stages of one run can't occupy the same position. Flagged in the PR
        # rather than added silently. Left unnamed so base.py's naming
        # convention applies — an explicit name here would be the one
        # constraint in the schema that doesn't follow it.
        UniqueConstraint("test_run_id", "sequence_index"),
    )


class Metric(TimestampMixin, Base):
    """Written exclusively by packages/metrics parsing k6 output.

    Never written by an agent directly — see
    system-architecture.md#ai-output-reliability.
    """

    __tablename__ = "metric"

    id: Mapped[uuid.UUID] = pk()
    test_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # NULL means "aggregate across the whole run", per database-design.md.
    endpoint: Mapped[str | None] = mapped_column(String(2048))

    p50_ms: Mapped[float] = mapped_column(Float, nullable=False)
    p90_ms: Mapped[float] = mapped_column(Float, nullable=False)
    p95_ms: Mapped[float] = mapped_column(Float, nullable=False)
    p99_ms: Mapped[float] = mapped_column(Float, nullable=False)
    throughput_rps: Mapped[float] = mapped_column(Float, nullable=False)
    error_rate: Mapped[float] = mapped_column(Float, nullable=False)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False)
    http_status_distribution: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False)

    # Carries both shapes issue #9 is deciding between: one summary row per
    # run (recorded_at = completion) or interval-bucketed rows (recorded_at =
    # bucket time). Summary-at-completion is a strict subset, so this column
    # is correct either way and the decision doesn't force a migration.
    recorded_at: Mapped[datetime] = mapped_column(SADateTime(timezone=True), nullable=False)

    test_run: Mapped[TestRun] = relationship(back_populates="metrics")


# ---------------------------------------------------------------------------
# Investigation loop
# ---------------------------------------------------------------------------


class Investigation(TimestampMixin, Base):
    __tablename__ = "investigation"

    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("target.id", ondelete="CASCADE"), nullable=False, index=True
    )
    objective: Mapped[InvestigationObjective] = mapped_column(
        pg_enum(InvestigationObjective, "investigation_objective"), nullable=False
    )
    status: Mapped[InvestigationStatus] = mapped_column(
        pg_enum(InvestigationStatus, "investigation_status"), nullable=False
    )

    # Two nullable FKs to the same table. No ORM relationship() is declared
    # for either — SQLAlchemy can't infer the join when two FKs point at one
    # target, and #12 reads them by id anyway. The ER diagram also shows a
    # many-to-many Investigation-to-TestRun edge, but the normative Entities
    # section defines only these two columns, so no join table is created.
    baseline_test_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_run.id", ondelete="SET NULL")
    )
    current_test_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_run.id", ondelete="SET NULL")
    )

    # Enforces MAX_EXPERIMENTS_PER_INVESTIGATION — see orchestrator.md.
    experiments_run: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    project: Mapped[Project] = relationship(back_populates="investigations")
    findings: Mapped[list[Finding]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )
    report: Mapped[Report | None] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )
    ai_executions: Mapped[list[AIExecution]] = relationship(back_populates="investigation")

    __table_args__ = (
        # Expressed as "not terminal" rather than listing the five in-flight
        # statuses: shorter, and a status added later is treated as active by
        # default, which is the safe direction for a "what's still running"
        # index. Only a new *terminal* status would need this updated.
        Index(
            "ix_investigation_status_active",
            "status",
            postgresql_where="status NOT IN ('complete', 'failed')",
        ),
    )


class Finding(TimestampMixin, Base):
    __tablename__ = "finding"

    id: Mapped[uuid.UUID] = pk()
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    severity: Mapped[Severity] = mapped_column(pg_enum(Severity, "severity"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # List of {statement, metric_ref} — see performance-investigator.md.
    observations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)

    investigation: Mapped[Investigation] = relationship(back_populates="findings")
    hypotheses: Mapped[list[Hypothesis]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )


class Hypothesis(TimestampMixin, Base):
    __tablename__ = "hypothesis"

    id: Mapped[uuid.UUID] = pk()
    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("finding.id", ondelete="CASCADE"), nullable=False, index=True
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[HypothesisStatus] = mapped_column(
        pg_enum(HypothesisStatus, "hypothesis_status"), nullable=False
    )
    # List of {statement, source_ref}.
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    recommended_experiment: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    finding: Mapped[Finding] = relationship(back_populates="hypotheses")
    experiments: Mapped[list[Experiment]] = relationship(
        back_populates="hypothesis", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list[Recommendation]] = relationship(
        back_populates="hypothesis", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # database-design.md specifies "confidence: float (0-1)". The
        # Orchestrator's continuation policy compares this against a 0.8
        # threshold, so an out-of-range value would silently change control
        # flow rather than error.
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="confidence_range"),
    )


class Experiment(TimestampMixin, Base):
    __tablename__ = "experiment"

    id: Mapped[uuid.UUID] = pk()
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hypothesis.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_plan.id", ondelete="CASCADE"), nullable=False
    )
    test_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_run.id", ondelete="CASCADE"), nullable=False
    )
    variable_changed: Mapped[str] = mapped_column(String(255), nullable=False)
    # Typed `Any` in the contract — a pool size, a flag, a string. JSONB
    # keeps the original type instead of stringifying it.
    baseline_value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    experiment_value: Mapped[Any] = mapped_column(JSONB, nullable=False)

    hypothesis: Mapped[Hypothesis] = relationship(back_populates="experiments")
    result: Mapped[ExperimentResult | None] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )


class ExperimentResult(TimestampMixin, Base):
    __tablename__ = "experiment_result"

    id: Mapped[uuid.UUID] = pk()
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiment.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # The deterministic diff from packages/metrics — p95_delta_ms, etc.
    # Never an AI judgment; see data-flow.md's COMPARE step.
    comparison: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    conclusion: Mapped[ExperimentConclusion] = mapped_column(
        pg_enum(ExperimentConclusion, "experiment_conclusion"), nullable=False
    )

    experiment: Mapped[Experiment] = relationship(back_populates="result")


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendation"

    id: Mapped[uuid.UUID] = pk()
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hypothesis.id", ondelete="CASCADE"), nullable=False, index=True
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    # Reuses the Severity enum — database-design.md says "priority (enum
    # matching Finding severity)", so it shares the type rather than
    # declaring a parallel one that could drift.
    priority: Mapped[Severity] = mapped_column(pg_enum(Severity, "severity"), nullable=False)

    hypothesis: Mapped[Hypothesis] = relationship(back_populates="recommendations")


class Report(TimestampMixin, Base):
    __tablename__ = "report"

    id: Mapped[uuid.UUID] = pk()
    # Unique: one report per investigation in the MVP. Regenerating
    # supersedes rather than duplicating — database-design.md.
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigation.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    capacity: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    key_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    bottleneck_analysis: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    regression: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    investigation: Mapped[Investigation] = relationship(back_populates="report")


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class AIExecution(TimestampMixin, Base):
    """Audit log of every agent call — the observability trail.

    Every field an agent output cites should be traceable back through this
    table (system-architecture.md#observability).
    """

    __tablename__ = "ai_execution"

    id: Mapped[uuid.UUID] = pk()
    # Nullable: ad hoc script generation may not belong to an investigation.
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("investigation.id", ondelete="SET NULL"), index=True
    )
    test_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_run.id", ondelete="SET NULL")
    )
    agent: Mapped[AgentName] = mapped_column(pg_enum(AgentName, "agent_name"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(SADateTime(timezone=True), nullable=False)

    # Pointers to stored payloads, not the payloads themselves — keeps this
    # table small enough to stay queryable, and keeps prompt/response bodies
    # out of the row a dashboard lists.
    input_reference: Mapped[str] = mapped_column(String(1024), nullable=False)
    output_reference: Mapped[str] = mapped_column(String(1024), nullable=False)

    decision: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)

    investigation: Mapped[Investigation | None] = relationship(back_populates="ai_executions")
