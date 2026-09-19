"""Deterministic Test Planner contract implementation."""

from __future__ import annotations

from packages.schemas.python.agent_io import (
    ControlledVariable,
    RampStrategy,
    TestPlanOutput,
    TestPlanRequest,
    TestStagePlan,
)
from packages.schemas.python.entities import InvestigationObjective, TestType

__test__ = False


class TestPlannerError(ValueError):
    pass


class TestPlanner:
    def create_plan(self, request: TestPlanRequest) -> TestPlanOutput:
        target = request.target_description
        traffic = target.expected_traffic
        requirements = target.performance_requirements
        if not target.user_journeys or traffic.peak_concurrent_users <= 0:
            raise TestPlannerError("traffic expectations and user journeys are required")
        if (
            request.objective == InvestigationObjective.DIAGNOSE_REGRESSION
            and not request.experiment_context
        ):
            raise TestPlannerError("diagnose_regression requires a baseline or experiment context")
        peak = traffic.peak_concurrent_users
        stages = [10, 50, 100, 250, 500, 750, peak]
        stages = sorted({min(max(value, 1), peak) for value in stages})
        controlled = None
        if request.experiment_context and request.experiment_context.variable_to_isolate:
            variable = request.experiment_context.variable_to_isolate
            controlled = ControlledVariable(
                name=variable, baseline_value="baseline", experiment_value="changed"
            )
            stages = [peak]
        return TestPlanOutput(
            test_type=TestType.CAPACITY
            if request.objective == InvestigationObjective.DETERMINE_CAPACITY
            else TestType.LOAD,
            rationale=(
                "Step through supplied traffic expectations to identify sustainable capacity."
            ),
            target_concurrency=peak,
            ramp_strategy=RampStrategy(type="step", step_size=1, step_duration_s=60),
            user_journeys=list(target.user_journeys),
            thresholds={
                "p95_ms": requirements.p95_ms,
                "max_error_rate": requirements.max_error_rate,
            },
            duration={"total_s": len(stages) * 60},
            stages=[TestStagePlan(target_vus=value, duration_s=60) for value in stages],
            success_criteria=[
                f"p95 < {requirements.p95_ms}ms",
                f"error rate < {requirements.max_error_rate}",
            ],
            controlled_variable=controlled,
        )
