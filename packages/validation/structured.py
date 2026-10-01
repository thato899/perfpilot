"""Common structured-output parsing, semantic validation, and retry policy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import ValidationError

T = TypeVar("T")


class StructuredOutputError(ValueError):
    """Raised when a specialist cannot produce a valid structured result."""

    def __init__(self, message: str, *, attempts: int = 2):
        super().__init__(message)
        self.attempts = attempts


def invoke_with_validation(
    generate: Callable[[str], Any],
    parse: Callable[[Any], T],
    prompt: str,
    *,
    semantic_validate: Callable[[T], None] | None = None,
    max_retries: int = 1,
) -> T:
    """Generate and validate structured output, retrying with feedback.

    ``generate`` receives the original prompt once and then a feedback prompt
    after each invalid response. No default or fabricated value is returned.
    """
    if max_retries < 0:
        raise ValueError("max_retries must not be negative")
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        request = prompt if attempt == 0 else _retry_prompt(prompt, last_error)
        generated = generate(request)
        try:
            value = parse(generated)
            if semantic_validate:
                semantic_validate(value)
            return value
        except Exception as error:  # normalize parser and semantic failures
            last_error = error
    raise StructuredOutputError(
        f"structured output failed validation after {max_retries + 1} attempts: "
        f"{_safe_error(last_error)}",
        attempts=max_retries + 1,
    ) from last_error


def _retry_prompt(prompt: str, error: Exception | None) -> str:
    return (
        "Your previous response failed validation. Return only corrected structured output.\n"
        f"Validation error: {_safe_error(error)}\n\nOriginal request:\n{prompt}"
    )


def _safe_error(error: Exception | None) -> str:
    if isinstance(error, ValidationError):
        return "; ".join(
            f"{'.'.join(map(str, item['loc']))}: {item['type']}"
            for item in error.errors(include_input=False)
        )[:500]
    if error is None:
        return "unknown"
    return type(error).__name__
