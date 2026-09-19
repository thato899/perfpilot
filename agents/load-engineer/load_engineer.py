"""Safe k6 preparation and script generation for the Load Engineer."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from packages.schemas.python.agent_io import ClampedInfo, TargetRef, TestPlanOutput, TestStagePlan


class LoadEngineerError(ValueError):
    """Raised when a load request cannot be prepared safely."""


class K6ExecutionError(RuntimeError):
    """Raised when the k6 process cannot complete successfully."""


@dataclass(frozen=True)
class SafetyLimits:
    max_virtual_users: int
    max_duration_seconds: int


@dataclass(frozen=True)
class PreparedLoad:
    test_plan: TestPlanOutput
    clamped: ClampedInfo | None


def validate_target(target: TargetRef, allowed_hosts: set[str]) -> None:
    """Reject malformed or non-allow-listed targets before generating load."""
    parsed = urlparse(target.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise LoadEngineerError("target must be an HTTP(S) URL with a hostname")
    if parsed.hostname.lower() not in {host.lower() for host in allowed_hosts}:
        raise LoadEngineerError("target_not_authorized")


def _clamped_stages(plan: TestPlanOutput, limits: SafetyLimits) -> list[TestStagePlan]:
    remaining_seconds = limits.max_duration_seconds
    stages: list[TestStagePlan] = []
    for stage in plan.stages:
        if remaining_seconds <= 0:
            break
        duration = min(stage.duration_s, remaining_seconds)
        if duration > 0:
            stages.append(
                TestStagePlan(
                    target_vus=min(stage.target_vus, limits.max_virtual_users),
                    duration_s=duration,
                )
            )
            remaining_seconds -= duration
    return stages


def prepare_load(plan: TestPlanOutput, limits: SafetyLimits) -> PreparedLoad:
    """Clamp VUs and total stage duration to configured hard ceilings."""
    if limits.max_virtual_users <= 0 or limits.max_duration_seconds <= 0:
        raise LoadEngineerError("safety limits must be positive")
    if not plan.stages:
        raise LoadEngineerError("test plan must contain at least one stage")

    requested_vus = max(plan.target_concurrency, *(stage.target_vus for stage in plan.stages))
    requested_duration = sum(stage.duration_s for stage in plan.stages)
    needs_clamp = (
        requested_vus > limits.max_virtual_users or requested_duration > limits.max_duration_seconds
    )
    if not needs_clamp:
        return PreparedLoad(test_plan=plan, clamped=None)

    executed_vus = min(requested_vus, limits.max_virtual_users)
    clamped_plan = plan.model_copy(
        update={
            "target_concurrency": min(plan.target_concurrency, limits.max_virtual_users),
            "stages": _clamped_stages(plan, limits),
        }
    )
    reasons = []
    if requested_vus > limits.max_virtual_users:
        reasons.append("MAX_VIRTUAL_USERS ceiling")
    if requested_duration > limits.max_duration_seconds:
        reasons.append("MAX_TEST_DURATION_SECONDS ceiling")
    return PreparedLoad(
        test_plan=clamped_plan,
        clamped=ClampedInfo(
            requested_vus=requested_vus,
            executed_vus=executed_vus,
            reason="; ".join(reasons),
        ),
    )


def generate_k6_script(plan: TestPlanOutput, target: TargetRef) -> str:
    """Render a minimal k6 script for the plan's first journey."""
    if not plan.user_journeys:
        raise LoadEngineerError("test plan must contain at least one user journey")
    path = plan.user_journeys[0]
    request_path = path if path.startswith("/") else "/"
    stages = [
        {"target": stage.target_vus, "duration": f"{stage.duration_s}s"} for stage in plan.stages
    ]
    thresholds = {
        "http_req_duration": [f"p(95)<{plan.thresholds['p95_ms']}"],
        "http_req_failed": [f"rate<{plan.thresholds['max_error_rate']}"],
    }
    options = {
        "stages": stages,
        "thresholds": thresholds,
        # k6's default summary stops at p95, while the persisted Metric
        # contract requires p99 as well.
        "summaryTrendStats": ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
    }
    return "\n".join(
        [
            "import http from 'k6/http';",
            "import { check } from 'k6';",
            "",
            f"const target = {json.dumps(target.base_url.rstrip('/'))};",
            f"const path = {json.dumps(request_path)};",
            "",
            "export const options = " + json.dumps(options, separators=(",", ":")) + ";",
            "",
            "export default function () {",
            "  const response = http.get(`${target}${path}`);",
            "  check(response, { 'status is successful': (res) => res.status < 400 });",
            "}",
        ]
    )


def run_k6(
    script_path: Path,
    output_path: Path,
    target: TargetRef,
    *,
    allowed_hosts: set[str],
    timeout_seconds: int,
    k6_binary: str = "k6",
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    """Run k6 after the defense-in-depth target and timeout checks."""
    validate_target(target, allowed_hosts)
    if timeout_seconds <= 0:
        raise LoadEngineerError("timeout_seconds must be positive")
    command: Sequence[str] = (
        k6_binary,
        "run",
        "--summary-export",
        str(output_path),
        str(script_path),
    )
    environment = os.environ.copy()
    environment["TARGET_BASE_URL"] = target.base_url.rstrip("/")
    try:
        result = runner(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            env=environment,
        )
    except subprocess.TimeoutExpired as error:
        raise K6ExecutionError("k6 execution timed out") from error
    if result.returncode != 0:
        raise K6ExecutionError(result.stderr.strip() or "k6 execution failed")
    return result
