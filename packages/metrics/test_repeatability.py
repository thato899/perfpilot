from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.metrics.metrics import compare_metrics
from packages.metrics.repeatability import (
    INVALID,
    VALID,
    EnvironmentMetadata,
    TrialRecord,
    build_repeatability_report,
)
from packages.schemas.python.entities import Metric

FINGERPRINT = "v1:same-plan"
OTHER_FINGERPRINT = "v1:different-plan"


def environment() -> EnvironmentMetadata:
    return EnvironmentMetadata(
        k6_version="k6 v0.57.0",
        target_base_url="http://localhost:8765",
        target_build="local-static",
        python_version="3.11.0",
        platform="Linux-test",
        max_virtual_users=5000,
        max_test_duration_seconds=1800,
        script_sha256="abc123",
    )


def metric(**overrides) -> Metric:
    values = {
        "id": uuid4(),
        "test_run_id": uuid4(),
        "endpoint": "/health",
        "p50_ms": 10.0,
        "p90_ms": 12.0,
        "p95_ms": 15.0,
        "p99_ms": 20.0,
        "throughput_rps": 100.0,
        "error_rate": 0.0,
        "concurrency": 2,
        "http_status_distribution": {"200": 100},
        "recorded_at": datetime(2026, 9, 30, tzinfo=UTC),
    }
    values.update(overrides)
    return Metric(**values)


def trial(
    index: int, *, validity: str = VALID, reason: str | None = None, **overrides
) -> TrialRecord:
    return TrialRecord(
        trial_index=index,
        validity=validity,
        invalid_reason=reason,
        scenario_fingerprint=FINGERPRINT,
        k6_version="k6 v0.57.0",
        target_build="local-static",
        raw_result_ref=f"trial-{index:02d}.k6-summary.json",
        script_ref="script.js",
        metric=None if validity == INVALID else metric(**overrides),
    )


def test_report_ranges_exclude_invalid_trials_and_keep_them():
    trials = [
        trial(1, p95_ms=15.0, p50_ms=10.0, p99_ms=20.0, throughput_rps=100.0),
        trial(2, p95_ms=17.0, p50_ms=11.0, p99_ms=22.0, throughput_rps=98.0),
        trial(3, validity=INVALID, reason="k6 execution timed out"),
        trial(4, p95_ms=16.0, p50_ms=10.5, p99_ms=21.0, throughput_rps=99.0, error_rate=0.01),
        trial(5, validity=INVALID, reason="raw summary was not written"),
    ]

    report = build_repeatability_report(
        trials,
        scenario_fingerprint=FINGERPRINT,
        scenario_document={"test_type": "load"},
        environment=environment(),
    )

    assert [item.trial_index for item in report.trials] == [1, 2, 3, 4, 5]
    assert report.valid_count == 3
    assert report.invalid_count == 2
    assert report.trials[2].invalid_reason == "k6 execution timed out"
    spans = {item.name: item for item in report.ranges}
    assert spans["p95_ms"].minimum == 15.0
    assert spans["p95_ms"].maximum == 17.0
    assert spans["p95_ms"].span == 2.0
    assert spans["p95_ms"].valid_samples == 3
    assert spans["error_rate"].span == 0.01
    assert report.observed_p95_span_ms == 2.0


def test_pairwise_conclusions_come_from_compare_metrics():
    trials = [
        trial(1, p95_ms=15.0),
        trial(2, p95_ms=15.4),
        trial(3, p95_ms=18.0, throughput_rps=110.0),
    ]

    report = build_repeatability_report(
        trials,
        scenario_fingerprint=FINGERPRINT,
        scenario_document={"test_type": "load"},
        environment=environment(),
    )

    baseline = report.trials[0].metric
    assert baseline is not None
    expected = [
        compare_metrics(baseline, report.trials[index].metric)
        for index in (1, 2)
        if report.trials[index].metric is not None
    ]
    assert [item.conclusion for item in report.pairwise] == [
        comparison.conclusion.value for comparison in expected
    ]
    assert [item.p95_delta_ms for item in report.pairwise] == [
        comparison.p95_delta_ms for comparison in expected
    ]
    assert report.pairwise[0].baseline_trial_index == 1
    assert report.pairwise[1].current_trial_index == 3


def test_small_and_large_p95_deltas_share_a_conclusion():
    trials = [trial(index, p95_ms=15.0) for index in range(1, 6)]

    report = build_repeatability_report(
        trials,
        scenario_fingerprint=FINGERPRINT,
        scenario_document={"test_type": "load"},
        environment=environment(),
    )

    assert report.observed_p95_span_ms == 0.0
    assert [example.label for example in report.policy_examples] == [
        "within_observed_span",
        "outside_observed_span",
    ]
    noise, material = report.policy_examples
    assert noise.p95_delta_ms == pytest.approx(0.001)
    assert material.p95_delta_ms == pytest.approx(100.001)
    assert noise.conclusion == "regression"
    assert material.conclusion == "regression"
    assert noise.status == "available"
    assert report.distinguishes_noise_from_material_change is False
    assert "does not change compare_metrics" in report.recommendation
    assert "inconclusive" in report.recommendation


def test_mismatched_scenario_is_kept_and_excluded_from_the_span():
    mismatched = trial(2, p95_ms=500.0)
    mismatched = mismatched.model_copy(update={"scenario_fingerprint": OTHER_FINGERPRINT})
    trials = [trial(1, p95_ms=15.0), mismatched]

    report = build_repeatability_report(
        trials,
        scenario_fingerprint=FINGERPRINT,
        scenario_document={"test_type": "load"},
        environment=environment(),
    )

    assert report.trials[1].validity == INVALID
    assert report.trials[1].invalid_reason == "scenario identity does not match the repeated plan"
    assert report.trials[1].metric is not None
    assert report.valid_count == 1
    assert report.ranges[0].name == "p50_ms"
    p95 = next(item for item in report.ranges if item.name == "p95_ms")
    assert p95.minimum == 15.0
    assert p95.maximum == 15.0
    assert p95.valid_samples == 1


def test_empty_valid_sample_does_not_invent_a_noise_span():
    report = build_repeatability_report(
        [trial(1, validity=INVALID, reason="target_not_authorized")],
        scenario_fingerprint=FINGERPRINT,
        scenario_document={"test_type": "load"},
        environment=environment(),
    )

    assert report.ranges == []
    assert report.pairwise == []
    assert report.policy_examples == []
    assert report.observed_p95_span_ms is None
    assert report.distinguishes_noise_from_material_change is False
    assert "No valid trial was parsed" in report.recommendation
    assert report.trials[0].invalid_reason == "target_not_authorized"
