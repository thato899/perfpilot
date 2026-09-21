from __future__ import annotations

from uuid import uuid4

import pytest

from packages.metrics.metrics import (
    ComparisonStatus,
    MetricsError,
    compare_metrics,
    estimate_capacity,
    parse_k6_summary,
    threshold_passed,
)


@pytest.fixture
def test_run_id():
    return uuid4()


def summary(*, p95: float = 420, error_rate: float = 0.01, concurrency: int = 500):
    return {
        "duration_seconds": 60,
        "metrics": {
            "http_req_duration": {"values": {"med": 120, "p(90)": 300, "p(95)": p95, "p(99)": 900}},
            "http_reqs": {"values": {"count": 20_400, "rate": 340}},
            "http_req_failed": {"values": {"rate": error_rate}},
        },
        "http_status_distribution": {"200": 20_000, "500": 400},
        "concurrency": concurrency,
    }


def test_parse_k6_summary_returns_valid_metric(test_run_id):
    metric = parse_k6_summary(summary(), test_run_id=test_run_id, concurrency=500)

    assert metric.test_run_id == test_run_id
    assert metric.p50_ms == 120
    assert metric.p95_ms == 420
    assert metric.p99_ms == 900
    assert metric.throughput_rps == 340
    assert metric.error_rate == 0.01
    assert metric.http_status_distribution == {"200": 20_000, "500": 400}


def test_parse_native_k6_summary_export(test_run_id):
    payload = {
        "metrics": {
            "http_req_duration": {"med": 1.2, "p(90)": 1.8, "p(95)": 2.1, "p(99)": 3.0},
            "http_reqs": {"count": 100, "rate": 10},
            "http_req_failed": {"value": 0.02},
        }
    }

    metric = parse_k6_summary(payload, test_run_id=test_run_id, concurrency=2)

    assert metric.p95_ms == 2.1
    assert metric.throughput_rps == 10
    assert metric.error_rate == 0.02


def test_parse_k6_summary_rejects_missing_k6_metric(test_run_id):
    payload = summary()
    del payload["metrics"]["http_req_failed"]

    with pytest.raises(MetricsError, match="missing k6 metric"):
        parse_k6_summary(payload, test_run_id=test_run_id, concurrency=500)


def test_threshold_passed_requires_both_limits(test_run_id):
    metric = parse_k6_summary(summary(), test_run_id=test_run_id, concurrency=500)

    assert threshold_passed(metric, p95_ms=500, max_error_rate=0.02)
    assert not threshold_passed(metric, p95_ms=400, max_error_rate=0.02)
    assert not threshold_passed(metric, p95_ms=500, max_error_rate=0.005)


def test_compare_metrics_calculates_regression(test_run_id):
    baseline = parse_k6_summary(summary(p95=400), test_run_id=test_run_id, concurrency=500)
    current = parse_k6_summary(summary(p95=600), test_run_id=test_run_id, concurrency=750)

    comparison = compare_metrics(baseline, current)

    assert comparison["p95_delta_ms"] == 200
    assert comparison["p95_delta_pct"] == 50
    assert comparison["error_rate_delta"] == 0
    assert comparison.status == ComparisonStatus.AVAILABLE
    assert comparison["p50_delta_ms"] == 0
    assert comparison["p99_delta_pct"] == 0
    assert comparison["baseline_concurrency"] == 500
    assert comparison["current_concurrency"] == 750


def test_compare_metrics_rejects_different_endpoint_scope(test_run_id):
    baseline = parse_k6_summary(
        summary(p95=400), test_run_id=test_run_id, concurrency=500, endpoint="/before"
    )
    current = parse_k6_summary(
        summary(p95=600), test_run_id=test_run_id, concurrency=500, endpoint="/after"
    )

    comparison = compare_metrics(baseline, current)

    assert comparison.status == ComparisonStatus.INCOMPATIBLE
    assert comparison.reason == "metrics must have the same endpoint scope"
    assert comparison.p95_delta_pct is None


def test_compare_metrics_marks_zero_baseline_p95_unavailable(test_run_id):
    baseline = parse_k6_summary(summary(p95=0), test_run_id=test_run_id, concurrency=500)
    current = parse_k6_summary(summary(p95=600), test_run_id=test_run_id, concurrency=500)

    comparison = compare_metrics(baseline, current)

    assert comparison.status == ComparisonStatus.UNAVAILABLE
    assert comparison.reason == "baseline p95_ms must be greater than zero"


def test_estimate_capacity_returns_highest_passing_stage(test_run_id):
    metrics = [
        parse_k6_summary(
            summary(p95=300, concurrency=500), test_run_id=test_run_id, concurrency=500
        ),
        parse_k6_summary(
            summary(p95=420, concurrency=750), test_run_id=test_run_id, concurrency=750
        ),
        parse_k6_summary(
            summary(p95=2800, concurrency=1000), test_run_id=test_run_id, concurrency=1000
        ),
    ]

    estimate = estimate_capacity(metrics, p95_ms=500, max_error_rate=0.02)

    assert estimate["sustainable_concurrency"] == 750
    assert estimate["recommended_operating_concurrency"] == 750


def test_estimate_capacity_returns_zero_when_no_stage_passes(test_run_id):
    metric = parse_k6_summary(summary(p95=900), test_run_id=test_run_id, concurrency=500)

    estimate = estimate_capacity([metric], p95_ms=500, max_error_rate=0.02)

    assert estimate["sustainable_concurrency"] == 0
