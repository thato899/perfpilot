import importlib.util
from pathlib import Path

from packages.schemas.python.agent_io import (
    ExpectedTraffic,
    PerformanceRequirements,
    TargetDescription,
    TestPlanRequest,
)
from packages.schemas.python.entities import InvestigationObjective, TestType

spec = importlib.util.spec_from_file_location(
    "test_planner", Path(__file__).with_name("test_planner.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
TestPlanner = module.TestPlanner


def request(objective=InvestigationObjective.DETERMINE_CAPACITY, context=None):
    return TestPlanRequest(
        target_description=TargetDescription(
            application_name="demo",
            user_journeys=["/checkout"],
            expected_traffic=ExpectedTraffic(
                normal_concurrent_users=100, peak_concurrent_users=1000
            ),
            performance_requirements=PerformanceRequirements(p95_ms=500, max_error_rate=0.01),
        ),
        objective=objective,
        experiment_context=context,
    )


def test_demo_capacity_plan_is_valid():
    plan = TestPlanner().create_plan(request())
    assert plan.test_type is TestType.CAPACITY
    assert [stage.target_vus for stage in plan.stages] == [10, 50, 100, 250, 500, 750, 1000]
    assert plan.thresholds["p95_ms"] == 500
