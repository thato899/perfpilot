"""Production Load Engineer adapter over the owned deterministic k6 module."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from uuid import UUID

from packages.metrics.metrics import parse_k6_summary
from packages.schemas.python.agent_io import (
    LoadExecutionRequest,
    LoadExecutionResult,
    LoadExecutionStatus,
)

from .config import Settings
from .load_engineer_stub import TargetNotAllowedError


def _load_engineer_module():
    path = Path(__file__).parents[2] / "agents" / "load-engineer" / "load_engineer.py"
    spec = importlib.util.spec_from_file_location("perfpilot_load_engineer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Load Engineer module is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class K6LoadEngineer:
    """Execute an approved plan with the real k6 binary and metrics parser."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def execute(self, request: LoadExecutionRequest) -> LoadExecutionResult:
        module = _load_engineer_module()
        if not self._settings.host_is_allowed(request.target.base_url):
            raise TargetNotAllowedError(request.target.base_url)
        limits = module.SafetyLimits(
            max_virtual_users=self._settings.max_virtual_users,
            max_duration_seconds=self._settings.max_test_duration_seconds,
        )
        prepared = module.prepare_load(request.test_plan, limits)
        results_dir = Path(self._settings.k6_results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        script_path = results_dir / f"{request.test_run_id}.js"
        output_path = results_dir / f"{request.test_run_id}.json"
        script_path.write_text(
            module.generate_k6_script(prepared.test_plan, request.target), encoding="utf-8"
        )
        module.run_k6(
            script_path,
            output_path,
            request.target,
            allowed_hosts=set(self._settings.allowed_target_hosts),
            timeout_seconds=self._settings.max_test_duration_seconds,
            k6_binary=self._settings.k6_binary_path,
        )
        summary = json.loads(output_path.read_text(encoding="utf-8"))
        executed_vus = max(stage.target_vus for stage in prepared.test_plan.stages)
        metric = parse_k6_summary(
            summary,
            test_run_id=UUID(str(request.test_run_id)),
            concurrency=executed_vus,
        )
        return LoadExecutionResult(
            test_run_id=request.test_run_id,
            status=LoadExecutionStatus.SUCCEEDED,
            k6_script_ref=str(script_path),
            raw_output_ref=str(output_path),
            metrics=[metric],
            clamped=prepared.clamped,
        )
