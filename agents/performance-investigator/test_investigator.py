import uuid

import pytest

from packages.schemas.python.agent_io import (
    InfrastructureMetrics,
    InvestigationAnalysisRequest,
    TestRunMetricsRef,
)
from packages.schemas.python.entities import Metric

from .investigator import InvestigatorValidationError, PerformanceInvestigator, validate_output


def metric(run_id, p95=420, concurrency=500):
    return Metric(
        id=uuid.uuid4(),
        test_run_id=run_id,
        p50_ms=100,
        p90_ms=300,
        p95_ms=p95,
        p99_ms=600,
        throughput_rps=100,
        error_rate=0.001,
        concurrency=concurrency,
        http_status_distribution={"200": 100},
        recorded_at="2026-01-01T00:00:00Z",
    )


def request(current, baseline=None, infra=None, comparison=None):
    return InvestigationAnalysisRequest(
        test_run=TestRunMetricsRef(id=current[0].test_run_id, metrics=current),
        baseline_test_run=TestRunMetricsRef(
            id=(baseline or current)[0].test_run_id, metrics=baseline or current
        ),
        comparison=comparison or {},
        thresholds={"p95_ms": 500, "max_error_rate": 0.01},
        infrastructure_metrics=infra,
    )


def test_healthy_metrics_have_no_hypothesis():
    output = PerformanceInvestigator().analyze(request([metric(uuid.uuid4())]))
    assert output.finding.severity.value == "INFO"
    assert output.hypotheses == []


def test_latency_violation_with_db_evidence_recommends_experiment():
    run = uuid.uuid4()
    output = PerformanceInvestigator().analyze(
        request(
            [metric(run, p95=2800, concurrency=750)],
            infra=InfrastructureMetrics(db_connection_pool_utilization=0.98),
        )
    )
    assert output.finding.severity.value == "HIGH"
    assert output.hypotheses[0].recommended_experiment.variable_to_isolate == "db_pool_size"


def test_invalid_metric_reference_is_rejected():
    req = request([metric(uuid.uuid4(), p95=1000)])
    output = PerformanceInvestigator().analyze(req)
    output.observations[0].metric_ref = str(uuid.uuid4())
    with pytest.raises(InvestigatorValidationError):
        validate_output(output, req)


def test_experiment_comparison_strengthens_hypothesis():
    run = uuid.uuid4()
    output = PerformanceInvestigator().reanalyze_after_experiment(
        request(
            [metric(run, p95=1500, concurrency=750)],
            infra=InfrastructureMetrics(db_connection_pool_utilization=0.98),
            comparison={"p95_delta_pct": -42.0},
        )
    )
    assert output.hypotheses[0].confidence == pytest.approx(0.87)
