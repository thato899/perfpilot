"""Canned k6 execution wrapper, standing in for agents/load-engineer.

Issue #13 wires Celery so that Developer 2/Govenor's execution wrapper can
run as a background job instead of inline. The wrapper itself is his
(CODEOWNERS: agents/load-engineer/), and it doesn't exist yet — so this
stands in, behind the same kind of seam the Orchestrator uses.

What it does NOT fake is the safety behaviour. security-model.md puts the
ceiling enforcement *at execution time*, in the Load Engineer, and
load-engineer.md requires the allow-list to be re-checked immediately
before invoking k6. Both are implemented here for real, because they're the
part that must not quietly go missing when the stub is swapped out — the
replacement has to keep them, and the tests that cover them should keep
passing unchanged.

Metric values mirror docs/demo-scenario.md so a dashboard driving this
shows the numbers the demo narrative describes.

DELETE THIS FILE when agents/load-engineer lands. deps.get_load_engineer()
is the only place that references it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from packages.schemas.python.agent_io import (
    ClampedInfo,
    LoadExecutionRequest,
    LoadExecutionResult,
    LoadExecutionStatus,
)
from packages.schemas.python.entities import Metric

from .config import Settings


class TargetNotAllowedError(RuntimeError):
    """Raised when a target fails the allow-list check at execution time.

    Separate from the API's 403 because this fires in the worker, after the
    request that queued the run is long gone: a target can be allow-listed
    when a plan is approved and removed before it executes. load-engineer.md
    calls for exactly this second check.
    """


class StubLoadEngineer:
    """Canned execution. No k6 process is started."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def execute(self, request: LoadExecutionRequest) -> LoadExecutionResult:
        # Defence in depth. The API checked this when the run was queued;
        # by the time a worker picks the job up that answer may be stale.
        if not self._settings.host_is_allowed(request.target.base_url):
            raise TargetNotAllowedError(request.target.base_url)

        requested_vus = request.test_plan.target_concurrency
        ceiling = self._settings.max_virtual_users
        executed_vus = min(requested_vus, ceiling)

        # Clamped, not rejected: "the run proceeds at the ceiling and is
        # flagged clamped in its result" (security-model.md). Refusing here
        # would lose the partial signal a capped run still gives you.
        clamped = None
        if executed_vus < requested_vus:
            clamped = ClampedInfo(
                requested_vus=requested_vus,
                executed_vus=executed_vus,
                reason=f"MAX_VIRTUAL_USERS={ceiling}",
            )

        now = datetime.now(UTC)
        return LoadExecutionResult(
            test_run_id=request.test_run_id,
            status=LoadExecutionStatus.SUCCEEDED,
            k6_script_ref=f"stub://script/{request.test_run_id}",
            raw_output_ref=f"stub://k6-summary/{request.test_run_id}",
            clamped=clamped,
            metrics=[
                Metric(
                    id=uuid.uuid4(),
                    test_run_id=request.test_run_id,
                    # None = aggregate across the whole run. A real wrapper
                    # also emits per-endpoint rows; one summary row is the
                    # shape issue #9 is leaning toward for Phase 1.
                    endpoint=None,
                    p50_ms=120.0,
                    p90_ms=980.0,
                    p95_ms=2800.0,
                    p99_ms=5100.0,
                    throughput_rps=310.5,
                    error_rate=0.02,
                    concurrency=executed_vus,
                    http_status_distribution={"200": 14500, "500": 300},
                    recorded_at=now,
                )
            ],
        )
