"""Smoke tests for packages/schemas/python/entities.py.

Per testing-strategy.md#unit-tests: packages/schemas' models should validate
known-good fixtures and reject known-bad ones. This is a starting slice, not
exhaustive coverage of every entity — extend it as each entity gets a real
consumer.

Import the module, not bare names: several classes here are literally named
Test* (TestPlan, TestType, TestRun, TestStage, TestPlanStatus, TestRunStatus),
which pytest's default `python_classes = Test*` collection heuristic would
otherwise try (and warn about) treating as test classes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.schemas.python import entities


def test_project_accepts_valid_data():
    project = entities.Project(
        id=uuid4(),
        name="demo",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert project.name == "demo"
    assert project.description is None


def test_test_type_enum_values():
    assert entities.TestType.LOAD.value == "load"
    assert entities.TestType.REGRESSION == "regression"


def test_test_plan_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        # Missing target_id, test_type, rationale, and every other required field.
        entities.TestPlan(id=uuid4(), project_id=uuid4())


def test_hypothesis_requires_evidence_list_but_allows_empty():
    # entities.Hypothesis itself doesn't enforce non-empty evidence (that's
    # HypothesisOutput.evidence in agent_io.py, via Field(min_length=1)) —
    # this pins down that distinction so it doesn't quietly drift.
    hypothesis = entities.Hypothesis(
        id=uuid4(),
        finding_id=uuid4(),
        statement="Connection pool exhaustion at high concurrency",
        confidence=0.7,
        status=entities.HypothesisStatus.PROPOSED,
        evidence=[],
    )
    assert hypothesis.evidence == []
