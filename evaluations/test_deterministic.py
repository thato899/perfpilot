"""Bounded offline grounding and hallucination-resistance suite."""

from __future__ import annotations

from copy import deepcopy

import pytest

from agents.orchestrator.orchestrator import Orchestrator
from agents.reporting.report_builder import validate_report
from evaluations.fixtures import (
    investigator_module,
    investigator_request,
    planner_request,
    valid_investigation,
    valid_plan,
    valid_report,
)
from evaluations.harness import EvaluationCase, run_suite
from packages.schemas.python.agent_io import OrchestratorAction


def generated(agent, request, value):
    action = (
        OrchestratorAction.INVOKE_TEST_PLANNER
        if request.__class__.__name__ == "TestPlanRequest"
        else OrchestratorAction.INVOKE_INVESTIGATOR
    )
    return agent.invoke_specialist(action, lambda _: value, request, prompt="fixture evaluation")


def test_required_deterministic_failure_classes():
    planner = planner_request()
    investigation = investigator_request()
    from agents.reporting.fixtures.investigation_states import demo_scenario_request
    from agents.reporting.report_builder import build_report_generated

    report_request = demo_scenario_request()
    report = valid_report().model_dump()
    investigator = valid_investigation(investigation).model_dump()

    invalid_metric = deepcopy(investigator)
    invalid_metric["observations"][0]["metric_ref"] = "metric:fabricated"
    missing_evidence = deepcopy(investigator)
    missing_evidence["hypotheses"][0]["evidence"] = []
    invalid_source = deepcopy(investigator)
    invalid_source["hypotheses"][0]["evidence"][0]["source_ref"] = "infra:imaginary"
    invalid_confidence = deepcopy(investigator)
    invalid_confidence["hypotheses"][0]["confidence"] = 1.5
    mutated_report = deepcopy(report)
    mutated_report["capacity"]["sustainable_concurrency"] += 1

    cases = [
        EvaluationCase(
            "Test Planner", "valid-grounded-output", "accepted", lambda: valid_plan(planner)
        ),
        EvaluationCase(
            "Test Planner",
            "malformed-schema-output",
            "rejected",
            lambda: generated(Orchestrator(), planner, {"bad": True}),
        ),
        EvaluationCase(
            "Performance Investigator",
            "missing-metric-reference",
            "rejected",
            lambda: generated(Orchestrator(), investigation, invalid_metric),
        ),
        EvaluationCase(
            "Performance Investigator",
            "fabricated-metric",
            "rejected",
            lambda: generated(Orchestrator(), investigation, invalid_metric),
        ),
        EvaluationCase(
            "Performance Investigator",
            "missing-evidence",
            "rejected",
            lambda: generated(Orchestrator(), investigation, missing_evidence),
        ),
        EvaluationCase(
            "Performance Investigator",
            "invalid-source-reference",
            "rejected",
            lambda: generated(Orchestrator(), investigation, invalid_source),
        ),
        EvaluationCase(
            "Performance Investigator",
            "invalid-confidence",
            "rejected",
            lambda: generated(Orchestrator(), investigation, invalid_confidence),
        ),
        EvaluationCase(
            "Reporting Agent",
            "numeric-mutation",
            "rejected",
            lambda: build_report_generated(
                lambda _: mutated_report, report_request, prompt="fixture"
            ),
        ),
        EvaluationCase(
            "Test Planner",
            "hostile-target-text",
            "accepted",
            lambda: valid_plan(planner_request(hostile=True)),
        ),
        EvaluationCase(
            "Orchestrator",
            "unsupported-boundary-action",
            "rejected",
            lambda: Orchestrator().invoke_specialist(
                OrchestratorAction.WAIT, lambda _: {}, planner, prompt="fixture"
            ),
        ),
    ]

    results = run_suite(cases)
    assert all(result.passed for result in results), [result.as_dict() for result in results]


def test_unsupported_hypothesis_and_contradictory_metric_are_rejected_by_truth_checks():
    request = investigator_request()
    output = valid_investigation(request)
    unsupported_output = output.model_copy(deep=True)
    unsupported_output.hypotheses[0].statement = "Cache saturation"
    contradictory_output = output.model_copy(deep=True)
    contradictory_output.observations[0].statement = "p95 remained within threshold"

    def unsupported(value):
        assert "database connection pool" in value.hypotheses[0].statement.lower()

    def contradictory(value):
        metric = request.test_run.metrics[0]
        assert metric.p95_ms > request.thresholds["p95_ms"]
        assert "within threshold" not in value.observations[0].statement.lower()

    results = run_suite(
        [
            EvaluationCase(
                "Performance Investigator",
                "unsupported-hypothesis",
                "rejected",
                lambda: unsupported_output,
                unsupported,
            ),
            EvaluationCase(
                "Performance Investigator",
                "contradictory-metric",
                "rejected",
                lambda: contradictory_output,
                contradictory,
            ),
        ]
    )
    assert all(result.passed for result in results), [result.as_dict() for result in results]


def test_report_truth_validator_catches_mutation_without_invoking_a_model():
    from agents.reporting.fixtures.investigation_states import demo_scenario_request

    request = demo_scenario_request()
    original = valid_report()
    report = original.model_copy(
        update={
            "capacity": original.capacity.model_copy(
                update={"sustainable_concurrency": original.capacity.sustainable_concurrency + 1}
            )
        }
    )
    assert any(
        "capacity was altered" in violation for violation in validate_report(report, request)
    )


def test_investigator_truth_validator_catches_invalid_reference_directly():
    request = investigator_request()
    output = valid_investigation(request)
    output.observations[0].metric_ref = "metric:missing"
    with pytest.raises(ValueError, match="invalid metric_ref"):
        investigator_module().validate_output(output, request)
