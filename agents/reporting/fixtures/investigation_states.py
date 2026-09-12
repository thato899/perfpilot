"""Fixture `ReportRequest`s for testing/demoing the Reporting Agent without
a real investigation having run (per docs/development/next-steps.md's
"produce a valid Report from fixture InvestigationState first").

`demo_scenario_request()` is the reference walkthrough from
docs/demo-scenario.md, made runnable — its numbers are the same ones
docs/agents/reporting-agent.md uses in its own illustrative Report example,
so this fixture doubles as an executable version of that doc's worked
example. `healthy_run_request()` covers the "no findings at all" case from
the same doc's Failure states table.
"""

from __future__ import annotations

from uuid import uuid4

from packages.schemas.python.agent_io import (
    CapacityEstimate,
    InvestigationState,
    RegressionComparison,
    ReportRequest,
)
from packages.schemas.python.entities import (
    Evidence,
    Finding,
    Hypothesis,
    HypothesisStatus,
    Observation,
    Severity,
)


def demo_scenario_request() -> ReportRequest:
    """The docs/demo-scenario.md walkthrough: a capacity investigation that
    finds DB-connection-pool contention at ~750 concurrent users, confirmed
    (87% confidence) after a follow-up experiment."""
    investigation_id = uuid4()
    finding_id = uuid4()

    observations = [
        Observation(
            id="obs-1",
            statement="p95 latency rose from 420ms to 2.8s at 750 concurrent users.",
            metric_ref="metric:p95_ms#stage-750",
        ),
        Observation(
            id="obs-2",
            statement="Database connection pool utilization reached 98% at 750 concurrent users.",
            metric_ref="metric:db_connection_pool_utilization#stage-750",
        ),
    ]

    finding = Finding(
        id=finding_id,
        investigation_id=investigation_id,
        severity=Severity.HIGH,
        summary="p95 latency degraded sharply at ~750 concurrent users; recovered after "
        "doubling the DB connection pool size in a follow-up experiment.",
        observations=observations,
    )

    hypothesis = Hypothesis(
        id=uuid4(),
        finding_id=finding_id,
        statement="Database connection pool contention.",
        confidence=0.87,
        status=HypothesisStatus.SUPPORTED,
        evidence=[
            Evidence(
                statement="DB connection pool utilization reached 98% at 750 concurrent users",
                source_ref="metric:db_connection_pool_utilization#stage-750",
            ),
            Evidence(
                statement="p95 latency improved ~42% after doubling the connection pool "
                "size (50 -> 100) in the follow-up experiment",
                source_ref="experiment:pool-size-doubled#comparison",
            ),
        ],
        recommended_experiment=None,  # already run and confirmed — nothing further pending
    )

    state = InvestigationState(
        investigation_id=investigation_id,
        target_id=uuid4(),
        status="reporting",
        observations=observations,
        findings=[finding],
        hypotheses=[hypothesis],
        experiments=[],
        decisions=[],
    )

    return ReportRequest(
        investigation_id=investigation_id,
        investigation_state=state,
        capacity_estimate=CapacityEstimate(
            sustainable_concurrency=620,
            recommended_operating_concurrency=500,
            method="packages/metrics capacity estimator — max concurrency before p95 "
            "exceeds the configured threshold, interpolated across step-ramp stages",
        ),
        regression_comparison=RegressionComparison(
            previous_p95_ms=420.0,
            current_p95_ms=890.0,
            regression_pct=112.0,
        ),
        key_metrics={
            "throughput_rps": 340,
            "p50_ms": 120,
            "p95_ms": 890,
            "p99_ms": 1450,
            "error_rate": 0.008,
            "peak_concurrency_tested": 1000,
        },
    )


def healthy_run_request() -> ReportRequest:
    """A fully healthy investigation: no anomalies, no findings, no
    hypotheses — per reporting-agent.md's Failure states table, this must
    still produce a *valid*, positively-toned report, not an error."""
    investigation_id = uuid4()

    state = InvestigationState(
        investigation_id=investigation_id,
        target_id=uuid4(),
        status="reporting",
        observations=[
            Observation(
                id="obs-1",
                statement="All stages from 10 to 1000 concurrent users stayed within "
                "configured thresholds.",
                metric_ref="metric:p95_ms#all-stages",
            )
        ],
        findings=[],
        hypotheses=[],
        experiments=[],
        decisions=[],
    )

    return ReportRequest(
        investigation_id=investigation_id,
        investigation_state=state,
        capacity_estimate=CapacityEstimate(
            sustainable_concurrency=1000,
            recommended_operating_concurrency=800,
            method="packages/metrics capacity estimator — max concurrency before p95 "
            "exceeds the configured threshold, interpolated across step-ramp stages",
        ),
        regression_comparison=RegressionComparison(
            previous_p95_ms=400.0,
            current_p95_ms=410.0,
            regression_pct=2.5,
        ),
        key_metrics={
            "throughput_rps": 410,
            "p50_ms": 95,
            "p95_ms": 410,
            "p99_ms": 640,
            "error_rate": 0.001,
            "peak_concurrency_tested": 1000,
        },
    )


__all__ = ["demo_scenario_request", "healthy_run_request"]
