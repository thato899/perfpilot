import importlib.util
from pathlib import Path

import pytest

from packages.schemas.python.agent_io import (
    ExpectedTraffic,
    PerformanceRequirements,
    TargetDescription,
    TestPlanRequest,
)
from packages.schemas.python.entities import InvestigationObjective
from packages.validation import StructuredOutputError

spec = importlib.util.spec_from_file_location(
    "test_planner", Path(__file__).with_name("test_planner.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
TestPlanner = module.TestPlanner


def request():
    return TestPlanRequest(
        target_description=TargetDescription(
            application_name="demo",
            user_journeys=["/checkout"],
            expected_traffic=ExpectedTraffic(
                normal_concurrent_users=100, peak_concurrent_users=1000
            ),
            performance_requirements=PerformanceRequirements(p95_ms=500, max_error_rate=0.01),
        ),
        objective=InvestigationObjective.DETERMINE_CAPACITY,
    )


def test_planner_retries_malformed_ai_output_then_accepts():
    responses = iter([{"bad": True}, TestPlanner().create_plan(request()).model_dump()])
    prompts = []
    plan = TestPlanner().create_plan_generated(
        lambda prompt: prompts.append(prompt) or next(responses), request(), prompt="plan"
    )
    assert plan.target_concurrency == 1000
    assert len(prompts) == 2


def test_planner_fails_after_two_invalid_outputs():
    with pytest.raises(StructuredOutputError):
        TestPlanner().create_plan_generated(lambda _: {"bad": True}, request(), prompt="plan")
