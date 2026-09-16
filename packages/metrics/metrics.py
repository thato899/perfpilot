"""Deterministic calculations for k6 output.

This module is deliberately independent of AI services. It converts a k6
summary into validated schema objects and computes comparisons from those
objects.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from packages.schemas.python.entities import Metric


class MetricsError(ValueError):
    """Raised when k6 output is missing required metric data."""


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MetricsError(f"{field_name} must be a number")
    return float(value)


def _metric_value(metrics: dict[str, Any], metric_name: str, value_name: str) -> float:
    metric = metrics.get(metric_name)
    if not isinstance(metric, dict):
        raise MetricsError(f"missing k6 metric: {metric_name}")
    values = metric.get("values")
    if not isinstance(values, dict) or value_name not in values:
        raise MetricsError(f"missing k6 value: {metric_name}.{value_name}")
    return _number(values[value_name], f"{metric_name}.{value_name}")


def _status_distribution(summary: dict[str, Any]) -> dict[str, int]:
    distribution = summary.get("http_status_distribution", {})
    if not isinstance(distribution, dict):
        raise MetricsError("http_status_distribution must be an object")
    result: dict[str, int] = {}
    for status, count in distribution.items():
        numeric_count = _number(count, f"http_status_distribution.{status}")
        if numeric_count < 0 or not numeric_count.is_integer():
            raise MetricsError(f"http_status_distribution.{status} must be a non-negative integer")
        result[str(status)] = int(numeric_count)
    return result


def parse_k6_summary(
    summary: dict[str, Any],
    *,
    test_run_id: UUID,
    concurrency: int,
    endpoint: str | None = None,
    metric_id: UUID | None = None,
    recorded_at: datetime | None = None,
) -> Metric:
    """Parse one k6 JSON summary into a validated aggregate Metric.

    k6 reports durations in milliseconds. The parser expects the standard
    ``handleSummary`` shape, with metrics nested below ``metrics``.
    """
    if concurrency < 0:
        raise MetricsError("concurrency must be non-negative")
    metrics = summary.get("metrics")
    if not isinstance(metrics, dict):
        raise MetricsError("summary.metrics must be an object")

    requests = _metric_value(metrics, "http_reqs", "count")
    duration_seconds = _number(summary.get("duration_seconds", 0), "duration_seconds")
    if duration_seconds < 0:
        raise MetricsError("duration_seconds must be non-negative")
    throughput = _metric_value(metrics, "http_reqs", "rate")
    if duration_seconds == 0 and requests > 0 and throughput == 0:
        raise MetricsError("cannot calculate throughput without duration_seconds or http_reqs.rate")

    return Metric(
        id=metric_id or uuid4(),
        test_run_id=test_run_id,
        endpoint=endpoint,
        p50_ms=_metric_value(metrics, "http_req_duration", "med"),
        p90_ms=_metric_value(metrics, "http_req_duration", "p(90)"),
        p95_ms=_metric_value(metrics, "http_req_duration", "p(95)"),
        p99_ms=_metric_value(metrics, "http_req_duration", "p(99)"),
        throughput_rps=throughput,
        error_rate=_metric_value(metrics, "http_req_failed", "rate"),
        concurrency=concurrency,
        http_status_distribution=_status_distribution(summary),
        recorded_at=recorded_at or datetime.now(UTC),
    )


def threshold_passed(metric: Metric, *, p95_ms: float, max_error_rate: float) -> bool:
    """Return whether a metric satisfies both performance requirements."""
    if p95_ms < 0 or max_error_rate < 0:
        raise MetricsError("thresholds must be non-negative")
    return metric.p95_ms <= p95_ms and metric.error_rate <= max_error_rate


def compare_metrics(baseline: Metric, current: Metric) -> dict[str, float]:
    """Calculate deterministic p95 deltas and regression percentage."""
    if baseline.p95_ms <= 0:
        raise MetricsError("baseline p95_ms must be greater than zero")
    delta_ms = current.p95_ms - baseline.p95_ms
    return {
        "p95_delta_ms": delta_ms,
        "p95_delta_pct": (delta_ms / baseline.p95_ms) * 100,
        "error_rate_delta": current.error_rate - baseline.error_rate,
        "throughput_delta_rps": current.throughput_rps - baseline.throughput_rps,
    }


def estimate_capacity(
    metrics: list[Metric],
    *,
    p95_ms: float,
    max_error_rate: float,
) -> dict[str, int | str]:
    """Find the highest concurrency whose metric passes both thresholds."""
    if not metrics:
        raise MetricsError("at least one metric is required")
    passing = [
        metric.concurrency
        for metric in metrics
        if threshold_passed(metric, p95_ms=p95_ms, max_error_rate=max_error_rate)
    ]
    if not passing:
        return {
            "sustainable_concurrency": 0,
            "recommended_operating_concurrency": 0,
            "method": "highest tested concurrency meeting p95 and error-rate thresholds",
        }
    sustainable = max(passing)
    return {
        "sustainable_concurrency": sustainable,
        "recommended_operating_concurrency": sustainable,
        "method": "highest tested concurrency meeting p95 and error-rate thresholds",
    }
