"""Tests for agents/reporting/report_builder.py.

Covers: the demo-scenario fixture producing a valid, correctly-grounded
Report; the "fully healthy, no findings" case from reporting-agent.md's
Failure states table; the pass-through guardrails (capacity/regression/
key_metrics/confidence must never be altered); and that recommendations are
gated on hypothesis status (supported only), while bottleneck_analysis
covers every hypothesis regardless of status.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from agents.reporting.fixtures.investigation_states import (
    demo_scenario_request,
    healthy_run_request,
)
from agents.reporting.report_builder import build_report, validate_report
from packages.schemas.python.entities import Evidence, HypothesisStatus, Severity


def test_demo_scenario_produces_a_valid_grounded_report():
    request = demo_scenario_request()
    report = build_report(request)

    # Numbers computed elsewhere (packages/metrics) must pass through
    # unaltered — this agent never recomputes them.
    assert report.capacity == request.capacity_estimate
    assert report.regression == request.regression_comparison
    assert report.key_metrics == request.key_metrics

    assert len(report.findings) == 1
    assert report.findings[0].severity == Severity.HIGH

    # Exactly one SUPPORTED hypothesis in the fixture -> exactly one recommendation.
    assert len(report.recommendations) == 1
    recommendation = report.recommendations[0]
    assert recommendation.finding_id == report.findings[0].id
    assert recommendation.priority == Severity.HIGH
    assert "database connection pool" in recommendation.statement.lower()

    assert len(report.bottleneck_analysis) == 1
    bottleneck = report.bottleneck_analysis[0]
    assert bottleneck.confidence == pytest.approx(0.87)
    assert len(bottleneck.evidence) == 2

    expected_operating_level = str(request.capacity_estimate.recommended_operating_concurrency)
    assert expected_operating_level in report.executive_summary

    assert validate_report(report, request) == []


def test_healthy_run_produces_valid_empty_report_not_an_error():
    request = healthy_run_request()
    report = build_report(request)

    assert report.findings == []
    assert report.bottleneck_analysis == []
    assert report.recommendations == []
    # Positive tone, not silent/empty — per the Failure states table.
    summary = report.executive_summary.lower()
    assert "healthy" in summary or "cleanly" in summary
    assert validate_report(report, request) == []


def test_recommendations_only_include_supported_hypotheses():
    request = demo_scenario_request()
    # Downgrade the one hypothesis to "testing" (not yet confirmed) — it
    # should still show up in bottleneck_analysis (a direct rendering of the
    # Investigator's output) but must not generate a recommendation, since
    # reporting-agent.md grounds recommendations in *confirmed* hypotheses.
    request.investigation_state.hypotheses[0].status = HypothesisStatus.TESTING

    report = build_report(request)

    assert report.recommendations == []
    assert len(report.bottleneck_analysis) == 1


def test_build_report_rejects_a_hypothesis_pointing_at_a_missing_finding():
    request = demo_scenario_request()
    request.investigation_state.hypotheses[0].finding_id = uuid4()  # no matching finding

    with pytest.raises(ValueError, match="not in investigation_state.findings"):
        build_report(request)


def test_validate_report_catches_an_altered_capacity():
    request = demo_scenario_request()
    report = build_report(request)

    tampered = report.model_copy(
        update={
            "capacity": report.capacity.model_copy(
                update={"sustainable_concurrency": report.capacity.sustainable_concurrency + 1}
            )
        }
    )

    violations = validate_report(tampered, request)
    assert any("capacity was altered" in v for v in violations)


def test_validate_report_catches_an_unevidenced_recommendation():
    request = demo_scenario_request()
    report = build_report(request)

    bogus_recommendation = report.recommendations[0].model_copy(update={"finding_id": str(uuid4())})
    tampered = report.model_copy(update={"recommendations": [bogus_recommendation]})

    violations = validate_report(tampered, request)
    assert any("no matching hypothesis" in v for v in violations)


def test_evidence_source_ref_is_preserved_in_rendered_bottleneck_text():
    request = demo_scenario_request()
    report = build_report(request)

    rendered = report.bottleneck_analysis[0].evidence
    source_refs = [e.source_ref for e in request.investigation_state.hypotheses[0].evidence]
    for ref in source_refs:
        assert any(ref in line for line in rendered)


def test_render_evidence_matches_evidence_model_directly():
    from agents.reporting.report_builder import _render_evidence

    rendered = _render_evidence(Evidence(statement="X reached 99%", source_ref="metric:x"))
    assert rendered == "X reached 99% (source: metric:x)"
