"""Grounded Performance Investigator.

This module interprets deterministic metric/comparison values. It never
calculates percentages, thresholds, or capacity; those values arrive in the
request from ``packages.metrics``.
"""

from __future__ import annotations

from packages.schemas.python.agent_io import (
    FindingSummary,
    HypothesisOutput,
    InvestigationAnalysisRequest,
    InvestigatorOutput,
)
from packages.schemas.python.entities import Evidence, RecommendedExperiment, Severity
from packages.validation import invoke_with_validation


class InvestigatorValidationError(ValueError):
    """The proposed analysis is not grounded in the supplied evidence."""


def validate_output(output: InvestigatorOutput, request: InvestigationAnalysisRequest) -> None:
    metric_refs = {str(metric.id) for metric in request.test_run.metrics}
    metric_refs.update(str(metric.id) for metric in request.baseline_test_run.metrics)
    source_refs = metric_refs | {
        f"infrastructure_metrics.{name}"
        for name, value in (
            request.infrastructure_metrics.model_dump() if request.infrastructure_metrics else {}
        ).items()
        if value is not None
    }
    for observation in output.observations:
        if observation.metric_ref not in metric_refs:
            raise InvestigatorValidationError(f"invalid metric_ref: {observation.metric_ref}")
    for hypothesis in output.hypotheses:
        if not hypothesis.evidence:
            raise InvestigatorValidationError(f"hypothesis {hypothesis.id} has no evidence")
        for evidence in hypothesis.evidence:
            if evidence.source_ref not in source_refs:
                raise InvestigatorValidationError(f"invalid source_ref: {evidence.source_ref}")
        if not 0 <= hypothesis.confidence <= 1:
            raise InvestigatorValidationError(f"invalid confidence: {hypothesis.confidence}")
        if hypothesis.recommended_experiment and not hypothesis.id:
            raise InvestigatorValidationError("experiment recommendation needs a hypothesis id")


class PerformanceInvestigator:
    def analyze_generated(
        self,
        generate,
        request: InvestigationAnalysisRequest,
        *,
        prompt: str = "Analyze the supplied performance evidence.",
    ) -> InvestigatorOutput:
        """Validate an AI-produced InvestigatorOutput through the shared seam."""
        return invoke_with_validation(
            generate,
            InvestigatorOutput.model_validate,
            prompt,
            semantic_validate=lambda output: validate_output(output, request),
        )

    def analyze(self, request: InvestigationAnalysisRequest) -> InvestigatorOutput:
        current = request.test_run.metrics
        if not current:
            raise InvestigatorValidationError("test_run must contain metrics")
        threshold = request.thresholds.get("p95_ms")
        max_error = request.thresholds.get("max_error_rate")
        if threshold is None or max_error is None:
            raise InvestigatorValidationError("p95_ms and max_error_rate thresholds are required")

        metric = max(current, key=lambda item: item.concurrency)
        observations = []
        breached = metric.p95_ms > threshold or metric.error_rate > max_error
        if breached:
            observations.append(
                {
                    "id": f"obs-{metric.id}",
                    "statement": (
                        "The highest tested load exceeds the supplied performance requirement."
                    ),
                    "metric_ref": str(metric.id),
                }
            )
        finding = FindingSummary(
            id=f"finding-{metric.test_run_id}",
            severity=Severity.HIGH if breached else Severity.INFO,
            summary=(
                "Performance degradation detected at the highest tested load."
                if breached
                else "No threshold breach detected."
            ),
        )
        hypotheses: list[HypothesisOutput] = []
        infra = request.infrastructure_metrics
        if (
            breached
            and infra
            and infra.db_connection_pool_utilization is not None
            and infra.db_connection_pool_utilization >= 0.9
        ):
            hypotheses.append(
                HypothesisOutput(
                    id=f"hypothesis-{metric.test_run_id}",
                    statement="Database connection pool contention",
                    evidence=[
                        Evidence(
                            statement=(
                                "DB connection pool utilization was "
                                f"{infra.db_connection_pool_utilization:.0%}."
                            ),
                            source_ref="infrastructure_metrics.db_connection_pool_utilization",
                        )
                    ],
                    confidence=0.6,
                    recommended_experiment=RecommendedExperiment(
                        variable_to_isolate="db_pool_size",
                        change="increase the pool size while preserving the baseline load profile",
                        expected_signal="p95 improves in the deterministic comparison",
                    ),
                )
            )
        result = InvestigatorOutput(
            finding=finding, observations=observations, hypotheses=hypotheses
        )
        validate_output(result, request)
        return result

    def reanalyze_after_experiment(
        self, request: InvestigationAnalysisRequest
    ) -> InvestigatorOutput:
        result = self.analyze(request)
        delta = request.comparison.get("p95_delta_pct")
        if result.hypotheses and isinstance(delta, (int, float)) and delta < 0:
            result.hypotheses[0].confidence = min(1.0, result.hypotheses[0].confidence + 0.27)
        elif result.hypotheses and isinstance(delta, (int, float)) and delta >= 0:
            result.hypotheses[0].confidence = max(0.0, result.hypotheses[0].confidence - 0.2)
        validate_output(result, request)
        return result
