from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from packages.schemas.python import agent_io

MODULE_PATH = Path(__file__).with_name("load_engineer.py")
MODULE_SPEC = importlib.util.spec_from_file_location("load_engineer", MODULE_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
load_engineer = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules["load_engineer"] = load_engineer
MODULE_SPEC.loader.exec_module(load_engineer)

LoadEngineerError = load_engineer.LoadEngineerError
K6ExecutionError = load_engineer.K6ExecutionError
SafetyLimits = load_engineer.SafetyLimits
generate_k6_script = load_engineer.generate_k6_script
prepare_load = load_engineer.prepare_load
run_k6 = load_engineer.run_k6
validate_target = load_engineer.validate_target


def make_test_plan():
    return agent_io.TestPlanOutput(
        test_type="capacity",
        rationale="Find the sustainable capacity ceiling.",
        target_concurrency=1000,
        ramp_strategy=agent_io.RampStrategy(type="step"),
        user_journeys=["/api/quiz/submit"],
        thresholds={"p95_ms": 500, "max_error_rate": 0.02},
        duration={"total_s": 90},
        stages=[
            agent_io.TestStagePlan(target_vus=500, duration_s=30),
            agent_io.TestStagePlan(target_vus=1000, duration_s=60),
        ],
        success_criteria=["p95 stays below 500ms"],
    )


def test_validate_target_rejects_host_outside_allow_list():
    with pytest.raises(LoadEngineerError, match="target_not_authorized"):
        validate_target(
            agent_io.TargetRef(base_url="https://example.com"), {"demo.perfpilot.local"}
        )


def test_prepare_load_clamps_users_and_duration():
    prepared = prepare_load(
        make_test_plan(), SafetyLimits(max_virtual_users=750, max_duration_seconds=45)
    )

    assert prepared.clamped is not None
    assert prepared.clamped.requested_vus == 1000
    assert prepared.clamped.executed_vus == 750
    assert prepared.test_plan.target_concurrency == 750
    assert [stage.target_vus for stage in prepared.test_plan.stages] == [500, 750]
    assert sum(stage.duration_s for stage in prepared.test_plan.stages) == 45


def test_generate_k6_script_contains_stages_and_thresholds():
    script = generate_k6_script(
        make_test_plan(), agent_io.TargetRef(base_url="https://demo.perfpilot.local")
    )

    assert "https://demo.perfpilot.local" in script
    assert '"target":500' in script
    assert '"target":1000' in script
    assert "p(95)<500.0" in script
    assert "rate<0.02" in script
    assert '"summaryTrendStats":["avg","min","med","max","p(90)","p(95)","p(99)"]' in script


def test_prepare_load_requires_stages():
    plan = make_test_plan().model_copy(update={"stages": []})

    with pytest.raises(LoadEngineerError, match="at least one stage"):
        prepare_load(plan, SafetyLimits(max_virtual_users=1000, max_duration_seconds=60))


def test_run_k6_rechecks_target_and_builds_bounded_command(tmp_path):
    calls = []

    def fake_runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = run_k6(
        tmp_path / "script.js",
        tmp_path / "summary.json",
        agent_io.TargetRef(base_url="https://demo.perfpilot.local"),
        allowed_hosts={"demo.perfpilot.local"},
        timeout_seconds=60,
        k6_binary="k6-test",
        runner=fake_runner,
    )

    assert result.returncode == 0
    assert calls[0][0] == (
        "k6-test",
        "run",
        "--summary-export",
        str(tmp_path / "summary.json"),
        str(tmp_path / "script.js"),
    )
    assert calls[0][1]["timeout"] == 60
    assert calls[0][1]["env"]["TARGET_BASE_URL"] == "https://demo.perfpilot.local"


def test_run_k6_surfaces_process_failures(tmp_path):
    def fake_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="bad script")

    with pytest.raises(K6ExecutionError, match="bad script"):
        run_k6(
            tmp_path / "script.js",
            tmp_path / "summary.json",
            agent_io.TargetRef(base_url="https://demo.perfpilot.local"),
            allowed_hosts={"demo.perfpilot.local"},
            timeout_seconds=60,
            runner=fake_runner,
        )
