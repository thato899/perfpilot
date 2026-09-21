"""Deterministic calculations for k6 output.

This module is deliberately independent of AI services. It converts a k6
summary into validated schema objects and computes comparisons from those
objects.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from packages.schemas.python.entities import Metric


class MetricsError(ValueError):
    """Raised when k6 output is missing required metric data."""


class ComparisonStatus(str, Enum):
    """Whether two metrics can be compared as a performance pair."""

    AVAILABLE = "available"
    INCOMPATIBLE = "incompatible"
    UNAVAILABLE = "unavailable"


class MetricComparison(BaseModel):
    """Typed, serializable comparison contract for baseline and current metrics.

    Delta sign convention: current minus baseline. A positive latency/error
    delta is worse; a positive throughput delta is better. Percent deltas use
    the baseline value as the denominator and are rounded to six decimals.
    """

    model_config = ConfigDict(extra="forbid")

    status: ComparisonStatus
    reason: str | None = None
    baseline_metric_id: UUID | None = None
    current_metric_id: UUID | None = None
    baseline_test_run_id: UUID | None = None
    current_test_run_id: UUID | None = None
    baseline_concurrency: int | None = Field(default=None, ge=0)
    current_concurrency: int | None = Field(default=None, ge=0)
    p50_delta_ms: float | None = None
    p50_delta_pct: float | None = None
    p90_delta_ms: float | None = None
    p90_delta_pct: float | None = None
    p95_delta_ms: float | None = None
    p95_delta_pct: float | None = None
    p99_delta_ms: float | None = None
    p99_delta_pct: float | None = None
    throughput_delta_rps: float | None = None
    throughput_delta_pct: float | None = None
    error_rate_delta: float | None = None
    error_rate_delta_pct: float | None = None

    def __getitem__(self, key: str) -> float | str | UUID | int | None:
        """Keep Phase 1 dictionary-style consumers source-compatible."""
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.model_dump())


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MetricsError(f"{field_name} must be a number")
    return float(value)


def _metric_value(metrics: dict[str, Any], metric_name: str, value_name: str) -> float:
    metric = metrics.get(metric_name)
    if not isinstance(metric, dict):
        raise MetricsError(f"missing k6 metric: {metric_name}")
    # Fixture summaries historically nested values under ``values``. k6's
    # native summary-export format emits the same fields directly on the
    # metric object, so accept both shapes at this boundary.
    values = metric.get("values", metric)
    if not isinstance(values, dict):
        raise MetricsError(f"missing k6 value: {metric_name}.{value_name}")
    actual_name = value_name
    # Native k6 exports http_req_failed as ``value``; the domain schema calls
    # that number an error-rate, matching the fixture adapter's ``rate`` key.
    if actual_name not in values and value_name == "rate" and "value" in values:
        actual_name = "value"
    if actual_name not in values:
        raise MetricsError(f"missing k6 value: {metric_name}.{value_name}")
    return _number(values[actual_name], f"{metric_name}.{value_name}")


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


def _delta(current: float, baseline: float) -> tuple[float, float | None]:
    delta = current - baseline
    if baseline == 0:
        return delta, None
    return delta, round((delta / baseline) * 100, 6)


def compare_metrics(baseline: Metric, current: Metric) -> MetricComparison:
    """Compare compatible baseline/current metrics deterministically.

    Metrics must describe the same endpoint scope. Concurrency is retained in
    the result because capacity-stage comparisons intentionally compare
    different concurrency levels. A missing baseline denominator is
    represented as ``unavailable`` rather than an invented percentage;
    incompatible records return a typed reason without calculating misleading
    deltas.
    """
    if baseline.endpoint != current.endpoint:
        return MetricComparison(
            status=ComparisonStatus.INCOMPATIBLE,
            reason="metrics must have the same endpoint scope",
            baseline_metric_id=baseline.id,
            current_metric_id=current.id,
            baseline_test_run_id=baseline.test_run_id,
            current_test_run_id=current.test_run_id,
            baseline_concurrency=baseline.concurrency,
            current_concurrency=current.concurrency,
        )
    if baseline.p95_ms <= 0:
        return MetricComparison(
            status=ComparisonStatus.UNAVAILABLE,
            reason="baseline p95_ms must be greater than zero",
            baseline_metric_id=baseline.id,
            current_metric_id=current.id,
            baseline_test_run_id=baseline.test_run_id,
            current_test_run_id=current.test_run_id,
            baseline_concurrency=baseline.concurrency,
            current_concurrency=current.concurrency,
        )

    p50_delta_ms, p50_delta_pct = _delta(current.p50_ms, baseline.p50_ms)
    p90_delta_ms, p90_delta_pct = _delta(current.p90_ms, baseline.p90_ms)
    p95_delta_ms, p95_delta_pct = _delta(current.p95_ms, baseline.p95_ms)
    p99_delta_ms, p99_delta_pct = _delta(current.p99_ms, baseline.p99_ms)
    throughput_delta_rps, throughput_delta_pct = _delta(
        current.throughput_rps, baseline.throughput_rps
    )
    error_rate_delta, error_rate_delta_pct = _delta(current.error_rate, baseline.error_rate)
    return MetricComparison(
        status=ComparisonStatus.AVAILABLE,
        baseline_metric_id=baseline.id,
        current_metric_id=current.id,
        baseline_test_run_id=baseline.test_run_id,
        current_test_run_id=current.test_run_id,
        baseline_concurrency=baseline.concurrency,
        current_concurrency=current.concurrency,
        p50_delta_ms=p50_delta_ms,
        p50_delta_pct=p50_delta_pct,
        p90_delta_ms=p90_delta_ms,
        p90_delta_pct=p90_delta_pct,
        p95_delta_ms=p95_delta_ms,
        p95_delta_pct=p95_delta_pct,
        p99_delta_ms=p99_delta_ms,
        p99_delta_pct=p99_delta_pct,
        throughput_delta_rps=throughput_delta_rps,
        throughput_delta_pct=throughput_delta_pct,
        error_rate_delta=error_rate_delta,
        error_rate_delta_pct=error_rate_delta_pct,
    )


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
