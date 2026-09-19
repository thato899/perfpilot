import pytest

from .structured import StructuredOutputError, invoke_with_validation


def test_valid_output_passes_without_retry():
    calls = []
    assert (
        invoke_with_validation(lambda prompt: calls.append(prompt) or "ok", str, "request") == "ok"
    )
    assert len(calls) == 1


def test_invalid_output_is_retried_with_feedback():
    responses = iter(["bad", "good"])
    prompts = []

    def generate(prompt):
        prompts.append(prompt)
        return next(responses)

    def parse(value):
        if value != "good":
            raise ValueError("expected good")
        return value

    assert invoke_with_validation(generate, parse, "request") == "good"
    assert len(prompts) == 2
    assert "expected good" in prompts[1]


def test_two_invalid_outputs_fail_explicitly():
    with pytest.raises(StructuredOutputError) as error:
        invoke_with_validation(
            lambda _: "bad", lambda _: (_ for _ in ()).throw(ValueError("invalid")), "request"
        )
    assert error.value.attempts == 2


def test_semantic_validation_uses_same_retry_boundary():
    responses = iter(["candidate", "valid"])
    invoke_with_validation(
        lambda _: next(responses),
        str,
        "request",
        semantic_validate=lambda value: (
            (_ for _ in ()).throw(ValueError("bad ref")) if value == "candidate" else None
        ),
    )
