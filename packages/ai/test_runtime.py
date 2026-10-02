"""Credential-free contract tests for the production Python provider bridge."""

import json
from types import SimpleNamespace
from urllib import error

import pytest

from apps.api.config import Settings, get_settings
from packages.ai.runtime import AIConfig, AIConfigurationError, AIProviderError, AIService
from packages.schemas.python.agent_io import TestPlanRequest


class FakeResponse:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit):
        return self.body[:limit]


def test_provider_selection_and_missing_credentials(monkeypatch):
    settings = Settings(api_auth_secret="test", ai_provider="ollama")
    config = AIConfig.from_settings(settings, "test_planner")
    assert (config.provider, config.model, config.api_key) == ("ollama", "qwen3:8b", "")
    for provider, key_name in (("gemini", "GEMINI_API_KEY"), ("deepseek", "DEEPSEEK_API_KEY")):
        monkeypatch.delenv(key_name, raising=False)
        with pytest.raises(AIConfigurationError, match="API key is required"):
            AIConfig.from_settings(
                Settings(api_auth_secret="test", ai_provider=provider), "reporting"
            )
    monkeypatch.setenv("AI_MODEL_TEST_PLANNER", "custom-local:latest")
    assert AIConfig.from_settings(settings, "test_planner").model == "custom-local:latest"
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/other")
    with pytest.raises(AIConfigurationError, match="plain HTTP"):
        AIConfig.from_settings(settings, "test_planner")


@pytest.mark.parametrize("provider", ["ollama", "deepseek", "gemini"])
def test_real_adapter_request_shape_and_redaction(monkeypatch, provider):
    from packages.ai import runtime

    captured = []
    result = {"test_type": "capacity"}
    response = {
        "ollama": {"done": True, "message": {"content": json.dumps(result)}},
        "deepseek": {
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(result)}}]
        },
        "gemini": {
            "candidates": [
                {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(result)}]}}
            ]
        },
    }[provider]

    def fake_open(req, timeout):
        captured.append((req, timeout))
        return FakeResponse(response)

    monkeypatch.setattr(runtime.request, "urlopen", fake_open)
    config = AIConfig(
        provider,
        "qwen3:8b" if provider == "ollama" else "test-model",
        "SECRET",
        "http://localhost:11434",
        3,
        256,
    )
    typed = TestPlanRequest.model_validate(
        {
            "target_description": {
                "application_name": "demo",
                "user_journeys": ["/health?token=PRIVATE"],
                "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
                "performance_requirements": {"p95_ms": 500, "max_error_rate": 0.01},
            },
            "objective": "determine_capacity",
        }
    )
    assert AIService(config).generate("test_planner", typed, "Plan") == result
    req, timeout = captured[0]
    payload = json.loads(req.data)
    assert timeout == 3
    assert "PRIVATE" not in req.data.decode()
    assert "SECRET" not in req.data.decode()
    assert payload["stream"] is False if provider != "gemini" else "contents" in payload
    assert (
        req.full_url.startswith("https://")
        if provider != "ollama"
        else req.full_url.endswith("/api/chat")
    )


def test_provider_errors_are_sanitized_and_not_retried(monkeypatch):
    from packages.ai import runtime

    calls = []

    def fail(req, timeout):
        calls.append(req)
        raise error.URLError("SECRET connection details")

    monkeypatch.setattr(runtime.request, "urlopen", fail)
    service = AIService(AIConfig("deepseek", "deepseek-chat", "SECRET", timeout_seconds=1))
    with pytest.raises(AIProviderError, match="deepseek request failed") as exc:
        service._request("prompt")
    assert "SECRET" not in str(exc.value)
    assert len(calls) == 1


def test_malformed_model_json_is_retried_by_validation_boundary(monkeypatch):
    from agents.orchestrator.orchestrator import Orchestrator
    from packages.ai import runtime

    monkeypatch.setenv("AI_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    get_settings.cache_clear()
    typed = TestPlanRequest.model_validate(
        {
            "target_description": {
                "application_name": "demo",
                "user_journeys": ["/health"],
                "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
                "performance_requirements": {"p95_ms": 500, "max_error_rate": 0.01},
            },
            "objective": "determine_capacity",
        }
    )
    from evaluations.fixtures import valid_plan

    valid = valid_plan(typed).model_dump(mode="json")
    bodies = iter(
        [
            {"done": True, "message": {"content": "not-json"}},
            {"done": True, "message": {"content": json.dumps(valid)}},
        ]
    )
    calls = []

    def fake_open(req, timeout):
        calls.append(req)
        return FakeResponse(next(bodies))

    monkeypatch.setattr(runtime.request, "urlopen", fake_open)
    assert Orchestrator().plan_test(typed).target_concurrency == 2
    assert len(calls) == 2
    get_settings.cache_clear()


def test_worker_investigator_dispatches_to_selected_provider(monkeypatch):
    from apps.api import tasks
    from evaluations.fixtures import investigator_request, valid_investigation
    from packages.ai import runtime

    monkeypatch.setenv("AI_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    get_settings.cache_clear()
    fixture = investigator_request()
    run = SimpleNamespace(id=fixture.test_run.id, metrics=fixture.test_run.metrics)
    plan = SimpleNamespace(thresholds=fixture.thresholds)
    calls = []

    def fake_generate(self, agent, typed_request, instruction):
        calls.append((self.config.provider, agent, typed_request, instruction))
        return valid_investigation(typed_request).model_dump(mode="json")

    monkeypatch.setattr(runtime.AIService, "generate", fake_generate)
    output = tasks._run_investigator(run, run, plan, SimpleNamespace(hypotheses=[]))
    assert output.finding.severity.value == "HIGH"
    assert calls[0][0:2] == ("ollama", "performance_investigator")
    assert calls[0][2].test_run.metrics[0].p95_ms == 2800
    get_settings.cache_clear()


def test_orchestrator_uses_provider_and_retries_invalid_structure(monkeypatch):
    from agents.orchestrator.orchestrator import Orchestrator

    monkeypatch.setenv("AI_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    get_settings.cache_clear()
    planner = Orchestrator()
    request = TestPlanRequest.model_validate(
        {
            "target_description": {
                "application_name": "demo",
                "user_journeys": ["/health"],
                "expected_traffic": {"normal_concurrent_users": 1, "peak_concurrent_users": 2},
                "performance_requirements": {"p95_ms": 500, "max_error_rate": 0.01},
            },
            "objective": "determine_capacity",
        }
    )
    from packages.ai import runtime

    valid = (
        planner._load_module("test-planner", "test_planner.py", "test_planner_runtime")
        .TestPlanner()
        .create_plan(request)
        .model_dump(mode="json")
    )
    responses = iter([{"invalid": True}, valid])
    calls = []

    def fake_request(self, prompt):
        calls.append(prompt)
        return next(responses)

    monkeypatch.setattr(runtime.AIService, "_request", fake_request)
    assert planner.plan_test(request).target_concurrency == 2
    assert len(calls) == 2
    assert "failed validation" in calls[1]
    assert planner.last_ai_service.config.provider == "ollama"
    get_settings.cache_clear()


def test_live_smoke_can_select_reporting_fixture_without_other_agents(monkeypatch, capsys):
    from agents.reporting.report_builder import build_report
    from packages.ai import smoke

    monkeypatch.setenv("AI_LIVE_SMOKE", "1")
    monkeypatch.setattr(
        smoke,
        "get_settings",
        lambda: Settings(api_auth_secret="test", ai_provider_enabled=True, ai_provider="ollama"),
    )
    calls = []

    def fake_generate(self, agent, typed_request, instruction):
        calls.append(agent)
        return build_report(typed_request).model_dump(mode="json")

    monkeypatch.setattr(smoke.AIService, "generate", fake_generate)
    smoke.main(["--agent", "reporting"])
    assert calls == ["reporting"]
    assert "reporting: validated in" in capsys.readouterr().out
