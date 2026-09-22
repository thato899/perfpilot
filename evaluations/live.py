"""Opt-in bounded adapter for live-provider evaluation.

The provider remains injected by the caller so importing this module never
creates credentials, network clients, retries, or an accidental bill.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .harness import EvaluationCase, EvaluationResult, run_suite

_DEFAULT_BUDGET = None


@dataclass(frozen=True)
class LiveBudget:
    max_cases: int = 5
    max_output_tokens: int = 2_000
    max_cost_usd: float = 1.00
    max_runtime_seconds: int = 120

    def __post_init__(self) -> None:
        if self.max_cases <= 0 or self.max_output_tokens <= 0:
            raise ValueError("live evaluation limits must be positive")
        if self.max_cost_usd <= 0 or self.max_runtime_seconds <= 0:
            raise ValueError("live evaluation limits must be positive")


@dataclass(frozen=True)
class LiveResponse:
    output: Any
    output_tokens: int
    cost_usd: float
    runtime_seconds: float


def run_live(
    cases: list[EvaluationCase],
    generate: Callable[[str], LiveResponse],
    *,
    budget: LiveBudget | None = _DEFAULT_BUDGET,
) -> list[EvaluationResult]:
    """Run at most ``budget.max_cases`` cases through an injected provider.

    The provider adapter returns usage metadata so this function can enforce
    token, cost, and wall-clock limits without retrying or hiding failures.
    """
    budget = budget or LiveBudget()
    if len(cases) > budget.max_cases:
        raise ValueError(f"live evaluation has {len(cases)} cases; limit is {budget.max_cases}")

    def invoke(case: EvaluationCase):
        response = generate(case.case_id)
        if response.output_tokens > budget.max_output_tokens:
            raise ValueError("live response exceeded output token limit")
        if response.cost_usd > budget.max_cost_usd:
            raise ValueError("live response exceeded cost limit")
        if response.runtime_seconds > budget.max_runtime_seconds:
            raise ValueError("live response exceeded runtime limit")
        return response.output

    live_cases = [
        EvaluationCase(
            agent=case.agent,
            case_id=case.case_id,
            expected=case.expected,
            invoke=lambda case=case: invoke(case),
            truth_check=case.truth_check,
            provider="live-injected",
            model=case.model,
        )
        for case in cases
    ]
    return run_suite(live_cases)


__all__ = ["LiveBudget", "LiveResponse", "run_live"]
