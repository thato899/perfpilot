"""Deterministic investigation continuation policy."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from packages.schemas.python.agent_io import (
    DecisionLogEntry,
    InvestigationState,
    OrchestratorAction,
    OrchestratorDecision,
    OrchestratorEventType,
    OrchestratorStep,
)


@dataclass(frozen=True)
class OrchestratorConfig:
    """Configuration for deterministic continuation decisions."""

    confidence_threshold: float = 0.8
    max_experiments: int = 3

    @classmethod
    def from_environment(cls) -> OrchestratorConfig:
        return cls(
            confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.8")),
            max_experiments=int(os.getenv("MAX_EXPERIMENTS_PER_INVESTIGATION", "3")),
        )


def decide(
    step: OrchestratorStep,
    config: OrchestratorConfig | None = None,
) -> OrchestratorDecision:
    """Return the next deterministic action for an investigation step."""

    policy = config or OrchestratorConfig.from_environment()
    state = step.investigation_state

    if step.event.type is OrchestratorEventType.TIMEOUT:
        return _decision(
            state,
            OrchestratorAction.WAIT,
            "investigation timed out; waiting for a resumable event",
        )

    if step.event.type is OrchestratorEventType.TEST_RUN_COMPLETED:
        if not state.findings:
            return _decision(
                state,
                OrchestratorAction.INVOKE_INVESTIGATOR,
                "completed run needs investigation",
            )
        return _continue_or_report(state, policy)

    if step.event.type is OrchestratorEventType.USER_REQUESTED_CONTINUE:
        if not state.findings:
            return _decision(
                state,
                OrchestratorAction.INVOKE_TEST_PLANNER,
                "user requested the initial test plan",
            )
        return _continue_or_report(state, policy)

    return _decision(state, OrchestratorAction.WAIT, "no action for this event")


def _continue_or_report(
    state: InvestigationState,
    config: OrchestratorConfig,
) -> OrchestratorDecision:
    if len(state.experiments) >= config.max_experiments:
        return _decision(state, OrchestratorAction.COMPLETE, "experiment budget exhausted")

    top_finding = _top_finding(state)
    top_hypothesis = _top_hypothesis(state, top_finding)

    if top_finding is None or top_finding.severity.value not in {"CRITICAL", "HIGH"}:
        return _decision(
            state,
            OrchestratorAction.INVOKE_REPORTING_AGENT,
            "no unresolved high-severity finding remains",
        )

    if top_hypothesis is None or top_hypothesis.confidence >= config.confidence_threshold:
        return _decision(
            state,
            OrchestratorAction.INVOKE_REPORTING_AGENT,
            "finding confidence meets the reporting threshold",
        )

    recommendation = top_hypothesis.recommended_experiment
    if recommendation is None or _experiment_already_run(
        state,
        top_hypothesis.id,
        recommendation.variable_to_isolate,
    ):
        return _decision(
            state,
            OrchestratorAction.INVOKE_REPORTING_AGENT,
            "no unexecuted recommended experiment remains",
        )

    return _decision(
        state,
        OrchestratorAction.INVOKE_TEST_PLANNER,
        "high-severity finding remains below the confidence threshold",
        specialist_input={
            "hypothesis_id": str(top_hypothesis.id),
            "variable_to_isolate": recommendation.variable_to_isolate,
            "change": recommendation.change,
            "expected_signal": recommendation.expected_signal,
        },
    )


def _top_finding(state: InvestigationState):
    if not state.findings:
        return None
    severity_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
    return max(state.findings, key=lambda finding: severity_rank[finding.severity.value])


def _top_hypothesis(state: InvestigationState, finding: Any):
    if finding is None:
        return None
    finding_id = str(finding.id)
    matching = [
        hypothesis for hypothesis in state.hypotheses if str(hypothesis.finding_id) == finding_id
    ]
    return max(matching, key=lambda hypothesis: hypothesis.confidence, default=None)


def _experiment_already_run(state: InvestigationState, hypothesis_id: Any, variable: str) -> bool:
    for experiment in state.experiments:
        if (
            str(experiment.get("hypothesis_id")) == str(hypothesis_id)
            and experiment.get("variable_changed") == variable
        ):
            return True
    return False


def _decision(
    state: InvestigationState,
    action: OrchestratorAction,
    reason: str,
    specialist_input: dict[str, Any] | None = None,
) -> OrchestratorDecision:
    updated_state = state.model_copy(deep=True)
    updated_state.decisions.append(
        DecisionLogEntry(
            step="orchestrator",
            decision=reason,
            made_by="orchestrator",
        )
    )
    return OrchestratorDecision(
        next_action=action,
        specialist_input=specialist_input,
        updated_state=updated_state,
    )


class Orchestrator:
    """Thin public facade for the deterministic continuation policy."""

    def __init__(self, config: OrchestratorConfig | None = None) -> None:
        self.config = config or OrchestratorConfig.from_environment()

    def step(self, step: OrchestratorStep) -> OrchestratorDecision:
        return decide(step, self.config)
