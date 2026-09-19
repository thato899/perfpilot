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
from packages.validation import invoke_with_validation

__test__ = False


class TestPlannerError(ValueError):
    pass


class TestPlanner:
    def create_plan_generated(
        self, generate, request: TestPlanRequest, *, prompt: str
    ) -> TestPlanOutput:
        """Parse and semantically validate an AI-produced plan through the shared seam."""
        return invoke_with_validation(
            generate,
            TestPlanOutput.model_validate,
            prompt,
            semantic_validate=lambda plan: self.validate_plan(plan, request),
        )

    @staticmethod
    def validate_plan(plan: TestPlanOutput, request: TestPlanRequest) -> None:
        target = request.target_description
        if not plan.user_journeys or set(plan.user_journeys) != set(target.user_journeys):
            raise TestPlannerError("plan user journeys must match the request")
        if plan.thresholds.get("p95_ms") != target.performance_requirements.p95_ms:
            raise TestPlannerError("plan p95 threshold must match the request")
        if plan.thresholds.get("max_error_rate") != target.performance_requirements.max_error_rate:
            raise TestPlannerError("plan error threshold must match the request")
        context = request.experiment_context
        if context and context.variable_to_isolate:
            if (
                not plan.controlled_variable
                or plan.controlled_variable.name != context.variable_to_isolate
            ):
                raise TestPlannerError("experiment plan must isolate the requested variable")

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
            test_type=(
                TestType.CAPACITY
                if request.objective == InvestigationObjective.DETERMINE_CAPACITY
                else TestType.LOAD
            ),
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
