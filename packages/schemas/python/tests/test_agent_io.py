"""Smoke tests for packages/schemas/python/agent_io.py.

Also exercises agent_io.py's relative import of entities.py (`from .entities
import ...`) — confirms that resolves correctly under pytest's
--import-mode=importlib when the test imports packages.schemas.python.agent_io
as a namespace package (no __init__.py files anywhere in packages/schemas/python).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.schemas.python import agent_io


def test_investigation_state_defaults_to_empty_lists():
    state = agent_io.InvestigationState(
        investigation_id=uuid4(),
        target_id=uuid4(),
        status="planning",
    )
    assert state.observations == []
    assert state.findings == []
    assert state.hypotheses == []
    assert state.experiments == []
    assert state.decisions == []


def test_decision_log_entry_requires_all_fields():
    with pytest.raises(ValidationError):
        agent_io.DecisionLogEntry(step="plan")  # missing decision, made_by


def test_investigator_output_hypothesis_requires_at_least_one_evidence():
    # HypothesisOutput.evidence uses Field(min_length=1) specifically to
    # guard against an unevidenced hypothesis reaching a report — see
    # docs/agents/performance-investigator.md#guardrails-against-hallucination.
    with pytest.raises(ValidationError):
        agent_io.HypothesisOutput(
            id="hyp-1",
            statement="Likely a DB connection pool bottleneck",
            evidence=[],
            confidence=0.6,
        )
