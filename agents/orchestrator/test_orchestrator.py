import uuid

import pytest

from packages.schemas.python.agent_io import (
    InvestigationState,
    OrchestratorAction,
    OrchestratorEvent,
    OrchestratorEventType,
    OrchestratorStep,
)
from packages.schemas.python.entities import HypothesisStatus, InvestigationStatus

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


def event(state_status: str, event_type: OrchestratorEventType, **payload):
    return OrchestratorStep(
        investigation_state=state(state_status),
        event=OrchestratorEvent(type=event_type, payload=payload),
    )


def test_planning_run_queued_becomes_running_and_waits():
    decision = Orchestrator().step(
        event(
            InvestigationStatus.PLANNING.value,
            OrchestratorEventType.USER_REQUESTED_CONTINUE,
            run_status="queued",
        )
    )
    assert decision.updated_state.status == InvestigationStatus.RUNNING.value
    assert decision.next_action is OrchestratorAction.WAIT


def test_successful_run_moves_to_investigating():
    decision = Orchestrator().step(
        event(
            InvestigationStatus.RUNNING.value,
            OrchestratorEventType.TEST_RUN_COMPLETED,
            test_run_id=str(uuid.uuid4()),
            status="succeeded",
        )
    )
    assert decision.updated_state.status == InvestigationStatus.INVESTIGATING.value
    assert decision.next_action is OrchestratorAction.INVOKE_INVESTIGATOR


def test_healthy_investigation_reports():
    decision = Orchestrator().step(
        event(
            InvestigationStatus.INVESTIGATING.value,
            OrchestratorEventType.TEST_RUN_COMPLETED,
            test_run_id=str(uuid.uuid4()),
        )
    )
    assert decision.updated_state.status == InvestigationStatus.REPORTING.value
    assert decision.next_action is OrchestratorAction.INVOKE_REPORTING_AGENT


def test_degraded_investigation_recommends_experiment():
    from packages.schemas.python.entities import Finding, Hypothesis, Severity

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
    current = state(
        InvestigationStatus.INVESTIGATING.value, findings=[finding], hypotheses=[hypothesis]
    )
    decision = Orchestrator().step(
        OrchestratorStep(
            investigation_state=current,
            event=OrchestratorEvent(
                type=OrchestratorEventType.TEST_RUN_COMPLETED,
                payload={"test_run_id": str(uuid.uuid4()), "status": "succeeded"},
            ),
        )
    )
    assert decision.updated_state.status == InvestigationStatus.EXPERIMENTING.value
    assert decision.next_action is OrchestratorAction.INVOKE_TEST_PLANNER


def test_approved_experiment_runs():
    current = state(InvestigationStatus.EXPERIMENTING.value)
    decision = Orchestrator().step(
        OrchestratorStep(
            investigation_state=current,
            event=OrchestratorEvent(
                type=OrchestratorEventType.USER_REQUESTED_CONTINUE,
                payload={"action": "experiment_approved"},
            ),
        )
    )
    assert decision.updated_state.status == InvestigationStatus.RUNNING.value
    assert decision.next_action is OrchestratorAction.INVOKE_LOAD_ENGINEER


def test_experiment_success_returns_to_investigating():
    decision = Orchestrator().step(
        event(
            InvestigationStatus.EXPERIMENTING.value,
            OrchestratorEventType.TEST_RUN_COMPLETED,
            test_run_id=str(uuid.uuid4()),
            status="succeeded",
        )
    )
    assert decision.updated_state.status == InvestigationStatus.INVESTIGATING.value
    assert decision.next_action is OrchestratorAction.INVOKE_INVESTIGATOR


def test_supported_hypothesis_reports():
    from packages.schemas.python.entities import Finding, Hypothesis, Severity

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
        confidence=0.9,
        status=HypothesisStatus.SUPPORTED,
        evidence=[],
    )
    current = state(
        InvestigationStatus.INVESTIGATING.value, findings=[finding], hypotheses=[hypothesis]
    )
    decision = Orchestrator().continue_investigation(current, uuid.uuid4())
    assert decision.updated_state.status == InvestigationStatus.REPORTING.value
    assert decision.next_action is OrchestratorAction.INVOKE_REPORTING_AGENT


def test_rejected_hypothesis_reports_without_restarting_experiment():
    from packages.schemas.python.entities import Finding, Hypothesis, Severity

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
        statement="rejected cause",
        confidence=0.1,
        status=HypothesisStatus.REJECTED,
        evidence=[],
    )
    decision = Orchestrator().continue_investigation(
        state(
            InvestigationStatus.INVESTIGATING.value,
            findings=[finding],
            hypotheses=[hypothesis],
        ),
        uuid.uuid4(),
    )
    assert decision.next_action is OrchestratorAction.INVOKE_REPORTING_AGENT


def test_experiment_budget_exhaustion_reports():
    from packages.schemas.python.entities import Finding, Hypothesis, Severity

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
    current = state(
        InvestigationStatus.INVESTIGATING.value,
        findings=[finding],
        hypotheses=[hypothesis],
        experiments=[{"id": str(uuid.uuid4())}] * 3,
    )
    decision = Orchestrator(max_experiments=3).continue_investigation(current, uuid.uuid4())
    assert decision.updated_state.status == InvestigationStatus.REPORTING.value
    assert decision.next_action is OrchestratorAction.INVOKE_REPORTING_AGENT


def test_reporting_completes():
    decision = Orchestrator().continue_investigation(
        state(InvestigationStatus.REPORTING.value), uuid.uuid4()
    )
    assert decision.updated_state.status == InvestigationStatus.COMPLETE.value
    assert decision.next_action is OrchestratorAction.COMPLETE


def test_failed_run_and_timeout_fail_without_restart():
    failed_run = Orchestrator().step(
        event(
            InvestigationStatus.RUNNING.value,
            OrchestratorEventType.TEST_RUN_COMPLETED,
            test_run_id=str(uuid.uuid4()),
            status="failed",
        )
    )
    timeout = Orchestrator().step(
        event(InvestigationStatus.INVESTIGATING.value, OrchestratorEventType.TIMEOUT)
    )
    assert failed_run.updated_state.status == InvestigationStatus.FAILED.value
    assert timeout.updated_state.status == InvestigationStatus.FAILED.value
    assert failed_run.next_action is OrchestratorAction.WAIT
    assert timeout.next_action is OrchestratorAction.WAIT


def test_failed_state_does_not_restart():
    decision = Orchestrator().step(
        event(InvestigationStatus.FAILED.value, OrchestratorEventType.USER_REQUESTED_CONTINUE)
    )
    assert decision.updated_state.status == InvestigationStatus.FAILED.value
    assert decision.next_action is OrchestratorAction.WAIT


def _planner_request():
    from packages.schemas.python.agent_io import (
        ExpectedTraffic,
        PerformanceRequirements,
        TargetDescription,
        TestPlanRequest,
    )
    from packages.schemas.python.entities import InvestigationObjective

    return TestPlanRequest(
        target_description=TargetDescription(
            application_name="demo",
            user_journeys=["/health"],
            expected_traffic=ExpectedTraffic(normal_concurrent_users=1, peak_concurrent_users=2),
            performance_requirements=PerformanceRequirements(p95_ms=500, max_error_rate=0.01),
        ),
        objective=InvestigationObjective.DETERMINE_CAPACITY,
    )


def test_public_specialist_boundary_retries_and_returns_typed_output():
    from packages.validation import StructuredOutputError

    orchestrator = Orchestrator()
    request = _planner_request()
    corrected = orchestrator.plan_test(request).model_dump()
    responses = iter([{"malformed": True}, corrected])
    prompts = []

    def generate(prompt):
        prompts.append(prompt)
        return next(responses)

    result = orchestrator.invoke_specialist(
        OrchestratorAction.INVOKE_TEST_PLANNER,
        generate,
        request,
        prompt="plan the test",
    )
    assert result.target_concurrency == 2
    assert len(prompts) == 2
    assert "failed validation" in prompts[1]

    with pytest.raises(StructuredOutputError) as error:
        orchestrator.invoke_specialist(
            OrchestratorAction.INVOKE_TEST_PLANNER,
            lambda _: {"malformed": True},
            request,
            prompt="plan the test",
        )
    assert error.value.attempts == 2
    escalated = orchestrator.fail_investigation(
        state(InvestigationStatus.RUNNING.value), "specialist validation failed"
    )
    assert escalated.updated_state.status == InvestigationStatus.FAILED.value
    assert escalated.next_action is OrchestratorAction.WAIT


def test_public_specialist_boundary_routes_investigator_and_reporting():
    from agents.reporting.fixtures.investigation_states import demo_scenario_request
    from agents.reporting.report_builder import build_report
    from packages.schemas.python.agent_io import (
        InvestigationAnalysisRequest,
        TestRunMetricsRef,
    )
    from packages.schemas.python.entities import Metric

    orchestrator = Orchestrator()
    run_id = uuid.uuid4()
    metric = Metric(
        id=uuid.uuid4(),
        test_run_id=run_id,
        p50_ms=10,
        p90_ms=20,
        p95_ms=30,
        p99_ms=40,
        throughput_rps=2,
        error_rate=0,
        concurrency=2,
        http_status_distribution={"200": 2},
        recorded_at="2026-01-01T00:00:00Z",
    )
    analysis_request = InvestigationAnalysisRequest(
        test_run=TestRunMetricsRef(id=run_id, metrics=[metric]),
        baseline_test_run=TestRunMetricsRef(id=run_id, metrics=[metric]),
        comparison={},
        thresholds={"p95_ms": 500, "max_error_rate": 0.01},
    )
    investigator = orchestrator._load_module(
        "performance-investigator", "investigator.py", "perfpilot_investigator"
    ).PerformanceInvestigator()
    investigator_output = investigator.analyze(analysis_request).model_dump()
    investigator_responses = iter([{"malformed": True}, investigator_output])
    assert (
        orchestrator.invoke_specialist(
            OrchestratorAction.INVOKE_INVESTIGATOR,
            lambda _: next(investigator_responses),
            analysis_request,
            prompt="analyze",
        ).finding.severity.value
        == "INFO"
    )

    report_request = demo_scenario_request()
    report_output = build_report(report_request).model_dump()
    report_responses = iter([{"malformed": True}, report_output])
    report = orchestrator.invoke_specialist(
        OrchestratorAction.INVOKE_REPORTING_AGENT,
        lambda _: next(report_responses),
        report_request,
        prompt="report",
    )
    assert report.key_metrics == report_request.key_metrics
