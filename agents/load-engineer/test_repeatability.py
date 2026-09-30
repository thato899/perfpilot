from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from packages.schemas.python.agent_io import TargetRef

MODULE_PATH = Path(__file__).with_name("repeatability.py")
MODULE_SPEC = importlib.util.spec_from_file_location("perfpilot_k6_repeatability", MODULE_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
repeatability = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = repeatability
MODULE_SPEC.loader.exec_module(repeatability)

HarnessConfig = repeatability.HarnessConfig
RepeatabilityConfigError = repeatability.RepeatabilityConfigError
controlled_plan = repeatability.controlled_plan
execute_repeatability = repeatability.execute_repeatability


def summary(p95: float) -> dict:
    return {
        "metrics": {
            "http_req_duration": {"med": 5, "p(90)": 8, "p(95)": p95, "p(99)": p95 + 1},
            "http_reqs": {"count": 10, "rate": 2},
            "http_req_failed": {"value": 0},
        }
    }


def config(tmp_path: Path, **overrides) -> HarnessConfig:
    values = {
        "plan": controlled_plan(virtual_users=2, duration_seconds=5, journey="/health"),
        "target": TargetRef(base_url="http://localhost:8765"),
        "allowed_hosts": frozenset({"localhost"}),
        "max_virtual_users": 5000,
        "max_test_duration_seconds": 1800,
        "trial_count": 5,
        "target_build": "local-static",
        "output_dir": tmp_path,
        "authorization_confirmed": True,
    }
    values.update(overrides)
    return HarnessConfig(**values)


def write_summaries(p95_by_trial: dict[int, float]):
    def run_trial(index: int, _script_path: Path, summary_path: Path) -> None:
        if index not in p95_by_trial:
            raise RuntimeError("k6 exited 1")
        summary_path.write_text(json.dumps(summary(p95_by_trial[index])), encoding="utf-8")

    return run_trial


def test_execute_repeats_one_bounded_scenario(tmp_path: Path):
    calls: list[int] = []

    def run_trial(index: int, script_path: Path, summary_path: Path) -> None:
        calls.append(index)
        script = script_path.read_text(encoding="utf-8")
        assert script.count('"target":2') == 1
        assert '"duration":"5s"' in script
        summary_path.write_text(json.dumps(summary(10 + index / 10)), encoding="utf-8")

    report = execute_repeatability(
        config(tmp_path),
        run_trial=run_trial,
        probe_version=lambda: "k6 v0.57.0",
    )

    fingerprint, document = repeatability.fingerprint_plan(
        controlled_plan(virtual_users=2, duration_seconds=5, journey="/health")
    )
    assert calls == [1, 2, 3, 4, 5]
    assert report.scenario_fingerprint == fingerprint
    assert report.scenario_document == document
    assert {trial.scenario_fingerprint for trial in report.trials} == {fingerprint}
    assert report.valid_count == 5
    assert report.invalid_count == 0
    assert report.environment.k6_version == "k6 v0.57.0"
    assert report.environment.target_build == "local-static"
    assert report.environment.max_virtual_users == 5000
    assert all(
        trial.metric is not None and trial.metric.endpoint == "/health" for trial in report.trials
    )
    assert all(
        trial.metric is not None and trial.metric.concurrency == 2 for trial in report.trials
    )
    saved = json.loads((tmp_path / "repeatability-report.json").read_text(encoding="utf-8"))
    assert saved["schema_version"] == "perfpilot.repeatability.v1"
    assert saved["environment"]["script_sha256"] == report.environment.script_sha256


def test_failed_trial_is_retained_and_excluded_from_ranges(tmp_path: Path):
    report = execute_repeatability(
        config(tmp_path),
        run_trial=write_summaries({1: 10.0, 2: 10.5, 4: 11.0, 5: 10.2}),
        probe_version=lambda: "k6 v0.57.0",
    )

    assert report.trials[2].validity == "invalid"
    assert report.trials[2].invalid_reason == "k6 exited 1"
    assert report.trials[2].metric is None
    assert report.valid_count == 4
    assert report.invalid_count == 1
    p95 = next(item for item in report.ranges if item.name == "p95_ms")
    assert p95.valid_samples == 4
    assert p95.minimum == 10.0
    assert p95.maximum == 11.0


def test_version_probe_failure_sends_no_load(tmp_path: Path):
    def fail_probe() -> str:
        raise RuntimeError("k6 binary missing")

    def run_trial(*_args) -> None:
        raise AssertionError("k6 must not run when the version probe fails")

    report = execute_repeatability(
        config(tmp_path),
        run_trial=run_trial,
        probe_version=fail_probe,
    )

    assert report.valid_count == 0
    assert report.invalid_count == 5
    assert report.trials[0].invalid_reason == "k6 version probe failed: k6 binary missing"
    assert report.environment.k6_version == "unknown"


def test_over_ceiling_plan_is_refused_without_clamping(tmp_path: Path):
    def run_trial(*_args) -> None:
        raise AssertionError("over-ceiling plans must not send load")

    plan = controlled_plan(virtual_users=20, duration_seconds=5, journey="/health")
    with pytest.raises(RepeatabilityConfigError, match="will not clamp"):
        execute_repeatability(
            config(tmp_path, plan=plan, max_virtual_users=5),
            run_trial=run_trial,
            probe_version=lambda: "k6 v0.57.0",
        )
    assert not (tmp_path / "repeatability-report.json").exists()


def test_duration_ceiling_is_not_raised(tmp_path: Path):
    plan = controlled_plan(virtual_users=2, duration_seconds=40, journey="/health")
    with pytest.raises(RepeatabilityConfigError, match="safety ceiling"):
        execute_repeatability(
            config(tmp_path, plan=plan, max_test_duration_seconds=10),
            run_trial=lambda *_args: None,
            probe_version=lambda: "k6 v0.57.0",
        )


def test_unauthorized_target_and_short_batch_are_refused(tmp_path: Path):
    with pytest.raises(RepeatabilityConfigError, match="target_not_authorized"):
        execute_repeatability(
            config(
                tmp_path,
                target=TargetRef(base_url="https://example.com"),
            ),
            run_trial=lambda *_args: (_ for _ in ()).throw(AssertionError("load was sent")),
            probe_version=lambda: "k6 v0.57.0",
        )
    with pytest.raises(RepeatabilityConfigError, match="at least 5"):
        execute_repeatability(
            config(tmp_path, trial_count=4),
            run_trial=lambda *_args: (_ for _ in ()).throw(AssertionError("load was sent")),
            probe_version=lambda: "k6 v0.57.0",
        )
    with pytest.raises(RepeatabilityConfigError, match="authorization"):
        execute_repeatability(
            config(tmp_path, authorization_confirmed=False),
            run_trial=lambda *_args: (_ for _ in ()).throw(AssertionError("load was sent")),
            probe_version=lambda: "k6 v0.57.0",
        )


def test_previous_trial_files_are_not_left_beside_the_new_sample(tmp_path: Path):
    stale = tmp_path / "trial-06.k6-summary.json"
    stale.write_text("{}", encoding="utf-8")

    execute_repeatability(
        config(tmp_path),
        run_trial=write_summaries({1: 10, 2: 10, 3: 10, 4: 10, 5: 10}),
        probe_version=lambda: "k6 v0.57.0",
    )

    assert not stale.exists()
    assert (tmp_path / "trial-05.k6-summary.json").is_file()
