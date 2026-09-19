"""Deterministic investigation continuation policy.

The orchestrator owns lifecycle transitions; specialists only return typed
data.  Numeric comparisons and confidence decisions are deliberately kept
outside the model layer.
"""

from __future__ import annotations

import uuid
from typing import Any

from packages.schemas.python.agent_io import (
    DecisionLogEntry,
    InvestigationState,
    OrchestratorAction,
    OrchestratorDecision,
    TestPlanOutput,
)
from packages.schemas.python.entities import InvestigationStatus


class OrchestratorError(ValueError):
    """A specialist result cannot safely advance the investigation."""


class Orchestrator:
    def __init__(self, *, confidence_threshold: float = 0.8, max_experiments: int = 3):
        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1")
        if max_experiments < 0:
            raise ValueError("max_experiments must not be negative")
        self.confidence_threshold = confidence_threshold
        self.max_experiments = max_experiments

    def plan_test(self, request: Any) -> TestPlanOutput:
        import importlib.util
        from pathlib import Path

        path = Path(__file__).parents[1] / "test-planner" / "test_planner.py"
        spec = importlib.util.spec_from_file_location("perfpilot_test_planner", path)
        if spec is None or spec.loader is None:
            raise OrchestratorError("test planner is unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.TestPlanner().create_plan(request)

    def start_investigation(
        self, investigation_id: uuid.UUID, target_id: uuid.UUID
    ) -> OrchestratorDecision:
        state = InvestigationState(
            investigation_id=investigation_id,
            target_id=target_id,
            status=InvestigationStatus.PLANNING.value,
        )
        return self._decision(
            state, OrchestratorAction.INVOKE_TEST_PLANNER, "initial investigation"
        )

    def continue_investigation(
        self, state: InvestigationState, test_run_id: uuid.UUID
    ) -> OrchestratorDecision:
        if state.status == InvestigationStatus.COMPLETE.value:
            return self._decision(state, OrchestratorAction.COMPLETE, "terminal state")
        state = state.model_copy(deep=True, update={"current_test_run_id": test_run_id})
        if state.status in {InvestigationStatus.PLANNING.value, InvestigationStatus.RUNNING.value}:
            return self._decision(state, OrchestratorAction.INVOKE_INVESTIGATOR, "test completed")
        if state.status == InvestigationStatus.INVESTIGATING.value:
            if not state.findings:
                state.status = InvestigationStatus.REPORTING.value
                return self._decision(
                    state, OrchestratorAction.INVOKE_REPORTING_AGENT, "healthy result"
                )
            confidence = max((h.confidence for h in state.hypotheses), default=1.0)
            needs_experiment = confidence < self.confidence_threshold
            if needs_experiment and len(state.experiments) < self.max_experiments:
                state.status = InvestigationStatus.EXPERIMENTING.value
                return self._decision(
                    state, OrchestratorAction.INVOKE_TEST_PLANNER, "confidence below threshold"
                )
            state.status = InvestigationStatus.REPORTING.value
            reason = "experiment budget exhausted" if needs_experiment else "confidence sufficient"
            return self._decision(state, OrchestratorAction.INVOKE_REPORTING_AGENT, reason)
        if state.status == InvestigationStatus.EXPERIMENTING.value:
            state.status = InvestigationStatus.INVESTIGATING.value
            return self._decision(
                state, OrchestratorAction.INVOKE_INVESTIGATOR, "experiment completed"
            )
        if state.status == InvestigationStatus.REPORTING.value:
            state.status = InvestigationStatus.COMPLETE.value
            return self._decision(state, OrchestratorAction.COMPLETE, "report persisted")
        raise OrchestratorError(f"unsupported investigation status: {state.status}")

    def _decision(
        self, state: InvestigationState, action: OrchestratorAction, reason: str
    ) -> OrchestratorDecision:
        state.decisions.append(
            DecisionLogEntry(step=state.status, decision=reason, made_by="orchestrator")
        )
        return OrchestratorDecision(next_action=action, updated_state=state)
