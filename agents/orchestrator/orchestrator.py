"""Deterministic investigation continuation policy.

The orchestrator owns lifecycle transitions; specialists only return typed
data.  Numeric comparisons and confidence decisions are deliberately kept
outside the model layer.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from typing import Any

from packages.schemas.python.agent_io import (
    DecisionLogEntry,
    InvestigationState,
    OrchestratorAction,
    OrchestratorDecision,
    OrchestratorEventType,
    OrchestratorStep,
    TestPlanOutput,
)
from packages.schemas.python.entities import HypothesisStatus, InvestigationStatus


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
        path = Path(__file__).parents[1] / "test-planner" / "test_planner.py"
        spec = importlib.util.spec_from_file_location("perfpilot_test_planner", path)
        if spec is None or spec.loader is None:
            raise OrchestratorError("test planner is unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.TestPlanner().create_plan(request)

    def step(self, step: OrchestratorStep) -> OrchestratorDecision:
        """Apply one explicit event to the deterministic lifecycle.

        Runtime callers may still use ``continue_investigation`` for the
        persisted test-run callback, but this event-shaped boundary is the
        canonical fixture/test interface for every lifecycle transition.
        """
        state = step.investigation_state
        event = step.event
        if state.status == InvestigationStatus.COMPLETE.value:
            return self._decision(state, OrchestratorAction.COMPLETE, "terminal state")
        if state.status == InvestigationStatus.FAILED.value:
            return self._decision(state, OrchestratorAction.WAIT, "terminal failure")
        if event.type is OrchestratorEventType.TIMEOUT:
            return self.fail_investigation(state, "timeout")

        if event.type is OrchestratorEventType.TEST_RUN_COMPLETED:
            status = event.payload.get("status", "succeeded")
            if status != "succeeded":
                return self.fail_investigation(state, f"test run ended with {status}")
            run_id = self._event_run_id(event.payload, state)
            if run_id is None:
                return self.fail_investigation(state, "test_run_id is required")
            return self.continue_investigation(state, run_id)

        if event.type is OrchestratorEventType.USER_REQUESTED_CONTINUE:
            if state.status == InvestigationStatus.PLANNING.value and event.payload.get(
                "run_status"
            ) in {"queued", "running"}:
                state = state.model_copy(
                    deep=True, update={"status": InvestigationStatus.RUNNING.value}
                )
                return self._decision(state, OrchestratorAction.WAIT, "test run queued")
            if event.payload.get("action") == "experiment_approved":
                if state.status != InvestigationStatus.EXPERIMENTING.value:
                    return self.fail_investigation(state, "experiment approval in invalid state")
                state = state.model_copy(
                    deep=True, update={"status": InvestigationStatus.RUNNING.value}
                )
                return self._decision(
                    state, OrchestratorAction.INVOKE_LOAD_ENGINEER, "experiment approved"
                )
            run_id = self._event_run_id(event.payload, state)
            if run_id is None:
                return self._decision(state, OrchestratorAction.WAIT, "awaiting test run")
            return self.continue_investigation(state, run_id)

        return self.fail_investigation(state, f"unsupported event: {event.type.value}")

    @staticmethod
    def _event_run_id(payload: dict[str, Any], state: InvestigationState) -> uuid.UUID | None:
        value = payload.get("test_run_id") or state.current_test_run_id
        if value is None:
            return None
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError):
            return None

    def fail_investigation(self, state: InvestigationState, reason: str) -> OrchestratorDecision:
        failed = state.model_copy(deep=True, update={"status": InvestigationStatus.FAILED.value})
        return self._decision(failed, OrchestratorAction.WAIT, reason)

    def invoke_specialist(self, action: OrchestratorAction, generate, request, *, prompt: str):
        """Invoke an AI-capable specialist through its public validation seam."""
        if action is OrchestratorAction.INVOKE_TEST_PLANNER:
            module = self._load_module("test-planner", "test_planner.py", "perfpilot_test_planner")
            return module.TestPlanner().create_plan_generated(generate, request, prompt=prompt)
        if action is OrchestratorAction.INVOKE_INVESTIGATOR:
            module = self._load_module(
                "performance-investigator", "investigator.py", "perfpilot_investigator"
            )
            return module.PerformanceInvestigator().analyze_generated(
                generate, request, prompt=prompt
            )
        if action is OrchestratorAction.INVOKE_REPORTING_AGENT:
            from agents.reporting.report_builder import build_report_generated

            return build_report_generated(generate, request, prompt=prompt)
        raise OrchestratorError(f"unsupported specialist action: {action.value}")

    @staticmethod
    def _load_module(directory: str, filename: str, module_name: str):
        path = Path(__file__).parents[1] / directory / filename
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise OrchestratorError(f"specialist is unavailable: {directory}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

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
        if state.status == InvestigationStatus.FAILED.value:
            return self._decision(state, OrchestratorAction.WAIT, "terminal failure")
        state = state.model_copy(deep=True, update={"current_test_run_id": test_run_id})
        if state.status in {InvestigationStatus.PLANNING.value, InvestigationStatus.RUNNING.value}:
            state.status = InvestigationStatus.INVESTIGATING.value
            return self._decision(state, OrchestratorAction.INVOKE_INVESTIGATOR, "test completed")
        if state.status == InvestigationStatus.INVESTIGATING.value:
            if not state.findings:
                state.status = InvestigationStatus.REPORTING.value
                return self._decision(
                    state, OrchestratorAction.INVOKE_REPORTING_AGENT, "healthy result"
                )
            active_hypotheses = [
                h for h in state.hypotheses if h.status is not HypothesisStatus.REJECTED
            ]
            confidence = max((h.confidence for h in active_hypotheses), default=1.0)
            needs_experiment = confidence < self.confidence_threshold
            consumed = (
                state.experiment_budget.consumed
                if state.experiment_budget is not None
                else len(state.experiments)
            )
            max_experiments = (
                state.experiment_budget.max_experiments
                if state.experiment_budget is not None
                else self.max_experiments
            )
            if needs_experiment and consumed < max_experiments:
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
