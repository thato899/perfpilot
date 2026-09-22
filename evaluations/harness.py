"""Small, deterministic runner for agent grounding evaluations.

The runner records the contract boundary separately from the truth assertion.
An output can be schema-valid and still fail an evaluation because the supplied
metrics or evidence do not support what it claims.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

ExpectedResult = Literal["accepted", "rejected"]
Outcome = Literal["accepted", "rejected"]

_REDACTION_PATTERNS = (
    (
        re.compile(r"(?i)(api[_ -]?key|token|secret|password|credential)\s*[:=]\s*[^\s,;]+"),
        r"\1=[REDACTED]",
    ),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
)
_SENSITIVE_KEY = re.compile(r"(?i)(api[_ -]?key|token|secret|password|credential)")


def redact(value: Any) -> Any:
    """Return a log-safe copy without mutating the fixture or model output."""
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _SENSITIVE_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        for pattern, replacement in _REDACTION_PATTERNS:
            value = pattern.sub(replacement, value)
        return value
    return value


@dataclass(frozen=True)
class EvaluationCase:
    agent: str
    case_id: str
    expected: ExpectedResult
    invoke: Callable[[], Any]
    truth_check: Callable[[Any], None] | None = None
    provider: str = "deterministic"
    model: str = "fixture-double"


@dataclass(frozen=True)
class EvaluationResult:
    agent: str
    case_id: str
    provider: str
    model: str
    expected: ExpectedResult
    actual: Outcome
    passed: bool
    failure_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return redact(
            {
                "agent": self.agent,
                "case": self.case_id,
                "provider": self.provider,
                "model": self.model,
                "expected": self.expected,
                "actual": self.actual,
                "passed": self.passed,
                "failure_reason": self.failure_reason,
            }
        )


def run_case(case: EvaluationCase) -> EvaluationResult:
    """Run one case and always return an actionable result record."""
    try:
        output = case.invoke()
    except Exception as error:
        actual: Outcome = "rejected"
        reason = f"contract rejection: {type(error).__name__}: {redact(str(error))}"
    else:
        actual = "accepted"
        reason = None
        if case.truth_check is not None:
            try:
                case.truth_check(output)
            except Exception as error:
                actual = "rejected"
                reason = f"truth assertion failed: {type(error).__name__}: {redact(str(error))}"

    passed = actual == case.expected
    if not passed and reason is None:
        reason = f"expected {case.expected}, got {actual}"
    return EvaluationResult(
        agent=case.agent,
        case_id=case.case_id,
        provider=case.provider,
        model=case.model,
        expected=case.expected,
        actual=actual,
        passed=passed,
        failure_reason=reason,
    )


def run_suite(cases: list[EvaluationCase]) -> list[EvaluationResult]:
    """Run cases in declaration order; deterministic cases never retry here."""
    return [run_case(case) for case in cases]


__all__ = ["EvaluationCase", "EvaluationResult", "redact", "run_case", "run_suite"]
