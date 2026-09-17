from uuid import uuid4

from agents.orchestrator.orchestrator import Orchestrator, OrchestratorConfig
from packages.schemas.python.agent_io import (
    Finding,
    Hypothesis,
    InvestigationState,
    OrchestratorAction,
    OrchestratorEvent,
    OrchestratorEventType,
    OrchestratorStep,
    RecommendedExperiment,
    Severity,
)


def make_state() -> InvestigationState:
    finding_id = uuid4()
    return InvestigationState(
        investigation_id=uuid4(),
        target_id=uuid4(),
        status="investigating",
        findings=[
            Finding(
                id=finding_id,
                investigation_id=uuid4(),
                severity=Severity.HIGH,
                summary="Latency degradation",
                observations=[],
            )
        ],
        hypotheses=[
            Hypothesis(
                id=uuid4(),
                finding_id=finding_id,
                statement="Connection pool contention",
                confidence=0.5,
                status="testing",
                evidence=[],
                recommended_experiment=RecommendedExperiment(
                    variable_to_isolate="db_pool_size",
                    change="double the pool size",
                    expected_signal="p95 latency improves",
                ),
            )
        ],
    )


def step(state: InvestigationState, event_type: OrchestratorEventType) -> OrchestratorStep:
    return OrchestratorStep(
        investigation_state=state,
        event=OrchestratorEvent(type=event_type),
    )


def test_user_requested_continue_starts_test_planner() -> None:
    state = InvestigationState(
        investigation_id=uuid4(),
        target_id=uuid4(),
        status="planning",
    )

    decision = Orchestrator(config=OrchestratorConfig()).step(
        step(state, OrchestratorEventType.USER_REQUESTED_CONTINUE)
    )

    assert decision.next_action is OrchestratorAction.INVOKE_TEST_PLANNER
    assert len(decision.updated_state.decisions) == 1


def test_completed_run_without_findings_invokes_investigator() -> None:
    state = InvestigationState(
        investigation_id=uuid4(),
        target_id=uuid4(),
        status="investigating",
    )

    decision = Orchestrator().step(step(state, OrchestratorEventType.TEST_RUN_COMPLETED))

    assert decision.next_action is OrchestratorAction.INVOKE_INVESTIGATOR


def test_low_confidence_high_finding_with_recommendation_runs_experiment() -> None:
    decision = Orchestrator().step(step(make_state(), OrchestratorEventType.TEST_RUN_COMPLETED))

    assert decision.next_action is OrchestratorAction.INVOKE_TEST_PLANNER
    assert decision.specialist_input is not None
    assert decision.specialist_input["variable_to_isolate"] == "db_pool_size"


def test_multiple_experiments_exhaust_budget() -> None:
    state = make_state()
    state.experiments = [{"hypothesis_id": "old", "variable_changed": "one"}]
    state.experiments.append({"hypothesis_id": "old", "variable_changed": "two"})

    decision = Orchestrator(config=OrchestratorConfig(max_experiments=2)).step(
        step(state, OrchestratorEventType.TEST_RUN_COMPLETED)
    )

    assert decision.next_action is OrchestratorAction.COMPLETE


def test_confident_finding_invokes_reporting() -> None:
    state = make_state()
    state.hypotheses[0].confidence = 0.9

    decision = Orchestrator().step(step(state, OrchestratorEventType.TEST_RUN_COMPLETED))

    assert decision.next_action is OrchestratorAction.INVOKE_REPORTING_AGENT


def test_timeout_waits_without_invoking_specialist() -> None:
    decision = Orchestrator().step(step(make_state(), OrchestratorEventType.TIMEOUT))

    assert decision.next_action is OrchestratorAction.WAIT
