"""Run identical, bounded k6 trials outside the investigation loop.

The harness refuses plans that would exceed the configured VU or duration
ceiling, reuses one scenario fingerprint and one script for every trial, and
keeps failed samples in the report with a reason. Comparison arithmetic stays
in ``packages.metrics``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from apps.api.scenario_identity import plan_fingerprint
from packages.metrics.metrics import MetricsError, parse_k6_summary
from packages.metrics.repeatability import (
    VALID,
    EnvironmentMetadata,
    RepeatabilityReport,
    TrialRecord,
    build_repeatability_report,
)
from packages.schemas.python.agent_io import RampStrategy, TargetRef, TestPlanOutput, TestStagePlan

MIN_TRIALS = 5
SummaryReader = Callable[[Path], dict]
VersionProbe = Callable[[], str]
TrialRunner = Callable[[int, Path, Path], None]


class RepeatabilityConfigError(ValueError):
    """Raised when a repeatability run must not send any load."""


@dataclass(frozen=True)
class HarnessConfig:
    """Operator inputs for one finite repeatability batch."""

    plan: TestPlanOutput
    target: TargetRef
    allowed_hosts: frozenset[str]
    max_virtual_users: int
    max_test_duration_seconds: int
    trial_count: int
    target_build: str
    output_dir: Path
    k6_binary: str = "k6"
    authorization_confirmed: bool = False


@dataclass(frozen=True)
class PreparedRepeatability:
    """A plan that is safe to repeat, plus the single script every trial uses."""

    config: HarnessConfig
    script: str
    script_sha256: str
    scenario_fingerprint: str
    scenario_document: dict
    timeout_seconds: int


def controlled_plan(*, virtual_users: int, duration_seconds: int, journey: str) -> TestPlanOutput:
    """Build one short load plan for repeated local trials.

    Thresholds are intentionally loose. k6 exits non-zero when a threshold
    fails, and a threshold failure would hide the timing variation this
    harness is trying to measure. The VU and duration ceilings are enforced
    separately and are not relaxed here.
    """
    if virtual_users <= 0 or duration_seconds <= 0:
        raise RepeatabilityConfigError("virtual users and duration must be positive")
    path = journey if journey.startswith("/") else f"/{journey}"
    return TestPlanOutput(
        test_type="load",
        rationale="Identical local trials for run-to-run noise characterization.",
        target_concurrency=virtual_users,
        ramp_strategy=RampStrategy(type="constant"),
        user_journeys=[path],
        thresholds={"p95_ms": 60000, "max_error_rate": 1.0},
        duration={"total_s": duration_seconds},
        stages=[TestStagePlan(target_vus=virtual_users, duration_s=duration_seconds)],
        success_criteria=["record the bounded repeated trials"],
    )


def prepare_repeatability(config: HarnessConfig) -> PreparedRepeatability:
    """Validate authorization, ceilings, and scenario identity before any trial."""
    if not config.authorization_confirmed:
        raise RepeatabilityConfigError(
            "target authorization must be confirmed before the harness sends load"
        )
    if config.trial_count < MIN_TRIALS:
        raise RepeatabilityConfigError(f"trial_count must be at least {MIN_TRIALS}")
    if config.max_virtual_users <= 0 or config.max_test_duration_seconds <= 0:
        raise RepeatabilityConfigError("safety ceilings must be positive")
    if not config.target_build.strip():
        raise RepeatabilityConfigError("target_build must name the controlled target build")

    engineer = _load_engineer()
    try:
        engineer.validate_target(config.target, set(config.allowed_hosts))
    except engineer.LoadEngineerError as error:
        raise RepeatabilityConfigError(str(error)) from error
    limits = engineer.SafetyLimits(
        max_virtual_users=config.max_virtual_users,
        max_duration_seconds=config.max_test_duration_seconds,
    )
    prepared = engineer.prepare_load(config.plan, limits)
    if prepared.clamped is not None:
        raise RepeatabilityConfigError(
            "requested plan exceeds the configured safety ceiling; "
            "the harness will not clamp the workload or raise the ceiling"
        )
    script = engineer.generate_k6_script(prepared.test_plan, config.target)
    fingerprint, document = fingerprint_plan(prepared.test_plan)
    requested_duration = sum(stage.duration_s for stage in prepared.test_plan.stages)
    timeout_seconds = min(config.max_test_duration_seconds, requested_duration + 30)
    return PreparedRepeatability(
        config=config,
        script=script,
        script_sha256=hashlib.sha256(script.encode("utf-8")).hexdigest(),
        scenario_fingerprint=fingerprint,
        scenario_document=document,
        timeout_seconds=timeout_seconds,
    )


def execute_repeatability(
    config: HarnessConfig,
    *,
    run_trial: TrialRunner | None = None,
    read_summary: SummaryReader | None = None,
    probe_version: VersionProbe | None = None,
) -> RepeatabilityReport:
    """Run the prepared plan once per trial and summarize the collected sample.

    Configuration failures raise before any trial file is written. A failed
    k6 invocation, unreadable summary, or version probe is stored as an
    invalid trial and the remaining trials still run.
    """
    prepared = prepare_repeatability(config)
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    _clear_previous_trials(output_dir)
    script_path = output_dir / "script.js"
    script_path.write_text(prepared.script, encoding="utf-8")

    version_probe = probe_version or (lambda: _probe_k6_version(config.k6_binary))
    k6_version, probe_error = _read_version(version_probe)
    environment = EnvironmentMetadata(
        k6_version=k6_version,
        target_base_url=config.target.base_url,
        target_build=config.target_build,
        python_version=platform.python_version(),
        platform=platform.platform(),
        max_virtual_users=config.max_virtual_users,
        max_test_duration_seconds=config.max_test_duration_seconds,
        script_sha256=prepared.script_sha256,
    )
    reader = read_summary or _read_summary
    runner = run_trial or _default_runner(prepared)
    trials: list[TrialRecord] = []
    for index in range(1, config.trial_count + 1):
        summary_path = output_dir / f"trial-{index:02d}.k6-summary.json"
        trials.append(
            _one_trial(
                index=index,
                prepared=prepared,
                environment=environment,
                script_path=script_path,
                summary_path=summary_path,
                runner=runner,
                reader=reader,
                probe_error=probe_error,
            )
        )
    report = build_repeatability_report(
        trials,
        scenario_fingerprint=prepared.scenario_fingerprint,
        scenario_document=prepared.scenario_document,
        environment=environment,
    )
    report_path = output_dir / "repeatability-report.json"
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _one_trial(
    *,
    index: int,
    prepared: PreparedRepeatability,
    environment: EnvironmentMetadata,
    script_path: Path,
    summary_path: Path,
    runner: TrialRunner,
    reader: SummaryReader,
    probe_error: str | None,
) -> TrialRecord:
    common = {
        "trial_index": index,
        "scenario_fingerprint": prepared.scenario_fingerprint,
        "k6_version": environment.k6_version,
        "target_build": environment.target_build,
        "script_ref": script_path.as_posix(),
        "raw_result_ref": summary_path.as_posix(),
    }
    if probe_error is not None:
        return TrialRecord(validity="invalid", invalid_reason=probe_error, metric=None, **common)
    try:
        runner(index, script_path, summary_path)
        if not summary_path.is_file():
            raise MetricsError("raw summary was not written")
        summary = reader(summary_path)
        metric = parse_k6_summary(
            summary,
            test_run_id=uuid4(),
            concurrency=prepared.config.plan.target_concurrency,
            endpoint=prepared.scenario_document["user_journeys"][0],
        )
    except (MetricsError, OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        return TrialRecord(
            validity="invalid",
            invalid_reason=_reason(error),
            metric=None,
            **common,
        )
    return TrialRecord(validity=VALID, invalid_reason=None, metric=metric, **common)


def _default_runner(prepared: PreparedRepeatability) -> TrialRunner:
    engineer = _load_engineer()

    def run_trial(_index: int, script_path: Path, summary_path: Path) -> None:
        engineer.run_k6(
            script_path,
            summary_path,
            prepared.config.target,
            allowed_hosts=set(prepared.config.allowed_hosts),
            timeout_seconds=prepared.timeout_seconds,
            k6_binary=prepared.config.k6_binary,
        )

    return run_trial


def _read_version(probe: VersionProbe) -> tuple[str, str | None]:
    try:
        version = probe().strip()
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        return "unknown", f"k6 version probe failed: {_reason(error)}"
    if not version:
        return "unknown", "k6 version probe failed: k6 returned an empty version"
    return version, None


def _probe_k6_version(binary: str) -> str:
    result = subprocess.run(
        [binary, "version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "k6 version command failed"
        raise RuntimeError(detail)
    line = result.stdout.strip().splitlines()
    return line[0] if line else ""


def _read_summary(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MetricsError("k6 summary must be an object")
    return payload


def fingerprint_plan(plan: TestPlanOutput) -> tuple[str, dict]:
    """Hash the v1 scenario fields of a test plan.

    ``plan_fingerprint`` expects JSON-shaped stage and ramp values, which is
    how a persisted plan stores them. A ``TestPlanOutput`` keeps those as
    models, so this adapts the same fields without a second identity rule.
    """
    return plan_fingerprint(
        SimpleNamespace(
            test_type=plan.test_type,
            target_concurrency=plan.target_concurrency,
            ramp_strategy=plan.ramp_strategy.model_dump(),
            user_journeys=list(plan.user_journeys),
            duration=dict(plan.duration),
            stages=[stage.model_dump() for stage in plan.stages],
        )
    )


def _clear_previous_trials(output_dir: Path) -> None:
    for stale in output_dir.glob("trial-*.k6-summary.json"):
        stale.unlink()


def _reason(error: BaseException) -> str:
    text = str(error).strip() or error.__class__.__name__
    return text[:500]


def _load_engineer():
    path = Path(__file__).with_name("load_engineer.py")
    spec = importlib.util.spec_from_file_location("perfpilot_load_engineer", path)
    if spec is None or spec.loader is None:
        raise RepeatabilityConfigError("Load Engineer module is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
