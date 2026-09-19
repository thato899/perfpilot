import pytest

from agents.reporting.fixtures.investigation_states import demo_scenario_request
from agents.reporting.report_builder import build_report_generated
from packages.validation import StructuredOutputError


def test_generated_report_retries_and_preserves_deterministic_values():
    request = demo_scenario_request()
    # The fixture builder supplies a valid deterministic report; use its output
    # as the corrected model response and tamper the first response only.
    from agents.reporting.report_builder import build_report

    corrected = build_report(request).model_dump()
    responses = iter([{"bad": True}, corrected])
    report = build_report_generated(lambda _: next(responses), request, prompt="report")
    assert report.capacity == request.capacity_estimate
    assert report.regression == request.regression_comparison


def test_generated_report_rejects_changed_numeric_values():
    request = demo_scenario_request()
    from agents.reporting.report_builder import build_report

    invalid = build_report(request).model_dump()
    invalid["capacity"]["sustainable_concurrency"] += 1
    with pytest.raises(StructuredOutputError):
        build_report_generated(lambda _: invalid, request, prompt="report")
