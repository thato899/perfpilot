import pytest

from evaluations.harness import EvaluationCase
from evaluations.live import LiveBudget, LiveResponse, run_live


def test_live_runner_enforces_case_bound():
    with pytest.raises(ValueError, match="limit is 1"):
        run_live(
            [
                EvaluationCase("Test Planner", "one", "accepted", lambda: None),
                EvaluationCase("Test Planner", "two", "accepted", lambda: None),
            ],
            lambda _: LiveResponse(None, 1, 0, 1),
            budget=LiveBudget(max_cases=1),
        )


def test_live_budget_rejects_unbounded_values():
    with pytest.raises(ValueError, match="limits must be positive"):
        LiveBudget(max_output_tokens=0)


def test_live_runner_enforces_usage_limits():
    result = run_live(
        [EvaluationCase("Test Planner", "one", "rejected", lambda: None)],
        lambda _: LiveResponse(None, 3, 0, 1),
        budget=LiveBudget(max_output_tokens=2),
    )[0]

    assert result.passed is True
    assert "output token limit" in result.failure_reason
