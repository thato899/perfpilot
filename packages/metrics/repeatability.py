"""Summarize run-to-run variation without changing comparison semantics.

The harness runner collects identical k6 trials. This module only reads those
already-parsed trials, calls ``compare_metrics`` for its conclusions, and
records whether that contract separates a small same-plan latency delta from
a much larger one. It does not execute load and it does not alter
``compare_metrics``.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from packages.metrics.metrics import ComparisonConclusion, compare_metrics
from packages.schemas.python.entities import Metric

SCHEMA_VERSION = "perfpilot.repeatability.v1"
SPAN_FIELDS: tuple[str, ...] = (
    "p50_ms",
    "p95_ms",
    "p99_ms",
    "throughput_rps",
    "error_rate",
)

VALID = "valid"
INVALID = "invalid"


class EnvironmentMetadata(BaseModel):
    """Versions and bounds recorded with a repeatability sample.

    This is harness evidence, not a production API contract.
    """

    model_config = ConfigDict(extra="forbid")

    k6_version: str
    target_base_url: str
    target_build: str
    python_version: str
    platform: str
    max_virtual_users: int = Field(ge=1)
    max_test_duration_seconds: int = Field(ge=1)
    script_sha256: str


class TrialRecord(BaseModel):
    """One repeated trial, kept whether or not its sample is usable."""

    model_config = ConfigDict(extra="forbid")

    trial_index: int = Field(ge=1)
    validity: str
    invalid_reason: str | None = None
    scenario_fingerprint: str
    k6_version: str
    target_build: str
    raw_result_ref: str | None = None
    script_ref: str | None = None
    metric: Metric | None = None


class MetricSpan(BaseModel):
    """Minimum, maximum, and width of one metric across valid trials."""

    model_config = ConfigDict(extra="forbid")

    name: str
    minimum: float
    maximum: float
    span: float
    valid_samples: int = Field(ge=0)


class PairwiseConclusion(BaseModel):
    """A canonical comparison between two valid trials of the same plan."""

    model_config = ConfigDict(extra="forbid")

    baseline_trial_index: int = Field(ge=1)
    current_trial_index: int = Field(ge=1)
    status: str
    conclusion: str
    p50_delta_ms: float | None = None
    p95_delta_ms: float | None = None
    p99_delta_ms: float | None = None
    throughput_delta_rps: float | None = None
    error_rate_delta: float | None = None


class PolicyExample(BaseModel):
    """A comparison illustration. It is not itself a collected trial."""

    model_config = ConfigDict(extra="forbid")

    label: str
    p95_delta_ms: float
    status: str
    conclusion: str
    note: str


class RepeatabilityReport(BaseModel):
    """Noise ranges and the current comparison contract's reading of them."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    scenario_fingerprint: str
    scenario_document: dict[str, Any]
    environment: EnvironmentMetadata
    trials: list[TrialRecord]
    valid_count: int = Field(ge=0)
    invalid_count: int = Field(ge=0)
    ranges: list[MetricSpan]
    pairwise: list[PairwiseConclusion]
    observed_p95_span_ms: float | None = None
    distinguishes_noise_from_material_change: bool
    policy_examples: list[PolicyExample]
    recommendation: str


def build_repeatability_report(
    trials: list[TrialRecord],
    *,
    scenario_fingerprint: str,
    scenario_document: dict[str, Any],
    environment: EnvironmentMetadata,
) -> RepeatabilityReport:
    """Build the noise report from every supplied trial.

    A trial marked valid is kept, but it is excluded from ranges when its
    scenario fingerprint differs or it has no parsed metric. Those cases are
    rewritten to invalid with a reason. Invalid trials are never dropped.
    """
    normalized = [_normalize_trial(trial, scenario_fingerprint) for trial in trials]
    valid = [trial for trial in normalized if trial.validity == VALID and trial.metric is not None]
    invalid_count = len(normalized) - len(valid)
    ranges = _ranges(valid)
    pairwise = _pairwise(valid)
    observed = _field_span(valid, "p95_ms")
    examples, distinguishes = _policy_examples(valid, observed)
    return RepeatabilityReport(
        schema_version=SCHEMA_VERSION,
        scenario_fingerprint=scenario_fingerprint,
        scenario_document=scenario_document,
        environment=environment,
        trials=normalized,
        valid_count=len(valid),
        invalid_count=invalid_count,
        ranges=ranges,
        pairwise=pairwise,
        observed_p95_span_ms=observed,
        distinguishes_noise_from_material_change=distinguishes,
        policy_examples=examples,
        recommendation=_recommendation(
            valid_count=len(valid),
            observed_p95_span_ms=observed,
            examples=examples,
            distinguishes=distinguishes,
        ),
    )


def _normalize_trial(trial: TrialRecord, scenario_fingerprint: str) -> TrialRecord:
    if trial.validity == VALID and trial.scenario_fingerprint != scenario_fingerprint:
        return trial.model_copy(
            update={
                "validity": INVALID,
                "invalid_reason": "scenario identity does not match the repeated plan",
            }
        )
    if trial.validity == VALID and trial.metric is None:
        return trial.model_copy(
            update={
                "validity": INVALID,
                "invalid_reason": trial.invalid_reason or "valid trial is missing a parsed metric",
            }
        )
    if trial.validity == INVALID and not trial.invalid_reason:
        return trial.model_copy(update={"invalid_reason": "unspecified invalid sample"})
    return trial


def _ranges(valid: list[TrialRecord]) -> list[MetricSpan]:
    spans: list[MetricSpan] = []
    for name in SPAN_FIELDS:
        span = _field_span(valid, name)
        if span is None:
            continue
        values = [float(getattr(trial.metric, name)) for trial in valid if trial.metric is not None]
        spans.append(
            MetricSpan(
                name=name,
                minimum=min(values),
                maximum=max(values),
                span=span,
                valid_samples=len(values),
            )
        )
    return spans


def _field_span(valid: list[TrialRecord], name: str) -> float | None:
    if not valid:
        return None
    values = [float(getattr(trial.metric, name)) for trial in valid if trial.metric is not None]
    if not values:
        return None
    return max(values) - min(values)


def _pairwise(valid: list[TrialRecord]) -> list[PairwiseConclusion]:
    if len(valid) < 2:
        return []
    baseline = valid[0]
    assert baseline.metric is not None
    conclusions: list[PairwiseConclusion] = []
    for current in valid[1:]:
        assert current.metric is not None
        comparison = compare_metrics(baseline.metric, current.metric)
        conclusions.append(
            PairwiseConclusion(
                baseline_trial_index=baseline.trial_index,
                current_trial_index=current.trial_index,
                status=comparison.status.value,
                conclusion=comparison.conclusion.value,
                p50_delta_ms=comparison.p50_delta_ms,
                p95_delta_ms=comparison.p95_delta_ms,
                p99_delta_ms=comparison.p99_delta_ms,
                throughput_delta_rps=comparison.throughput_delta_rps,
                error_rate_delta=comparison.error_rate_delta,
            )
        )
    return conclusions


def _policy_examples(
    valid: list[TrialRecord], observed_p95_span: float | None
) -> tuple[list[PolicyExample], bool]:
    if not valid or observed_p95_span is None:
        return [], False
    baseline = valid[0].metric
    assert baseline is not None
    noise_delta = observed_p95_span if observed_p95_span > 0 else 0.001
    material_delta = max(noise_delta * 10, noise_delta + 100)
    noise = _illustrated_comparison(
        baseline,
        noise_delta,
        label="within_observed_span",
        note=(
            "Illustration, not a collected trial. p95 is increased by the observed "
            "same-plan span, or by 0.001 ms when that span is zero. Other metrics "
            "stay equal."
        ),
    )
    material = _illustrated_comparison(
        baseline,
        material_delta,
        label="outside_observed_span",
        note=(
            "Illustration, not a collected trial. p95 is increased by a delta outside "
            "the observed same-plan span. Other metrics stay equal."
        ),
    )
    distinguishes = noise.conclusion != material.conclusion and (
        noise.conclusion == ComparisonConclusion.UNCHANGED.value
    )
    return [noise, material], distinguishes


def _illustrated_comparison(
    baseline: Metric, p95_delta_ms: float, *, label: str, note: str
) -> PolicyExample:
    current = baseline.model_copy(update={"id": uuid4(), "p95_ms": baseline.p95_ms + p95_delta_ms})
    comparison = compare_metrics(baseline, current)
    return PolicyExample(
        label=label,
        p95_delta_ms=p95_delta_ms,
        status=comparison.status.value,
        conclusion=comparison.conclusion.value,
        note=note,
    )


def _format_ms(value: float) -> str:
    """Format a millisecond value without binary float noise."""
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def _recommendation(
    *,
    valid_count: int,
    observed_p95_span_ms: float | None,
    examples: list[PolicyExample],
    distinguishes: bool,
) -> str:
    if valid_count == 0 or observed_p95_span_ms is None or len(examples) < 2:
        return (
            "No valid trial was parsed, so this sample cannot characterize run-to-run noise. "
            "Invalid trials are retained with their reasons. compare_metrics is unchanged."
        )
    noise, material = examples[0], examples[1]
    if distinguishes:
        return (
            "The current comparison contract labeled the within-span p95 illustration "
            "differently from the larger illustration. Confirm that result before treating "
            "it as a noise policy. This report does not change compare_metrics."
        )
    return (
        f"Observed same-plan p95 span is {_format_ms(observed_p95_span_ms)} ms across "
        f"{valid_count} valid trials. compare_metrics labels a {_format_ms(noise.p95_delta_ms)} "
        f"ms p95 increase as {noise.conclusion} and a {_format_ms(material.p95_delta_ms)} ms "
        f"p95 increase as {material.conclusion}. Those conclusions have no noise or "
        "materiality state, so a "
        "fluctuation inside the measured span can receive the same conclusion as a much "
        "larger change. A future reviewed policy could treat absolute deltas inside the "
        "measured same-plan span as inconclusive. This report does not change compare_metrics."
    )
