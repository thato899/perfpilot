import uuid

from packages.schemas.python.agent_io import InvestigationState, OrchestratorAction
from packages.schemas.python.entities import InvestigationStatus

from .orchestrator import Orchestrator


def state(status: str, **kwargs) -> InvestigationState:
    return InvestigationState(
        investigation_id=uuid.uuid4(), target_id=uuid.uuid4(), status=status, **kwargs
    )


def test_initial_state_invokes_planner():
    decision = Orchestrator().start_investigation(uuid.uuid4(), uuid.uuid4())
    assert decision.next_action is OrchestratorAction.INVOKE_TEST_PLANNER


def test_healthy_result_reports_without_experiment():
    decision = Orchestrator().continue_investigation(
        state(InvestigationStatus.INVESTIGATING.value), uuid.uuid4()
    )
    assert decision.next_action is OrchestratorAction.INVOKE_REPORTING_AGENT


def test_low_confidence_uses_experiment_budget():
    from packages.schemas.python.entities import Finding, Hypothesis, HypothesisStatus, Severity

    finding = Finding(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        severity=Severity.HIGH,
        summary="slow",
        observations=[],
    )
    hypothesis = Hypothesis(
        id=uuid.uuid4(),
        finding_id=finding.id,
        statement="pool",
        confidence=0.4,
        status=HypothesisStatus.TESTING,
        evidence=[],
    )
    decision = Orchestrator(max_experiments=1).continue_investigation(
        state(InvestigationStatus.INVESTIGATING.value, findings=[finding], hypotheses=[hypothesis]),
        uuid.uuid4(),
    )
    assert decision.next_action is OrchestratorAction.INVOKE_TEST_PLANNER
    assert decision.updated_state.status == InvestigationStatus.EXPERIMENTING.value


def test_terminal_state_does_not_restart():
    decision = Orchestrator().continue_investigation(
        state(InvestigationStatus.COMPLETE.value), uuid.uuid4()
    )
    assert decision.next_action is OrchestratorAction.COMPLETE
