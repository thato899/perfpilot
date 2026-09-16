"""Canned Orchestrator, standing in for agents/orchestrator.

Issue #12 says to build against a stubbed Orchestrator rather than wait on
Thatayaone's, per team-workflow.md. Everything here returns payloads that
*validate against packages/schemas* — the point is not to fake plausible
output, it's to exercise the real contract so the swap is a no-op for the
API. If a field's shape changes in agent_io.py, this file stops validating
and the endpoint tests fail, which is the desired early warning.

Nothing here reasons. It has no AI call and no branching on content: the
values mirror docs/demo-scenario.md so a dashboard driving the stub shows
the same numbers the demo narrative describes.

DELETE THIS FILE when agents/orchestrator lands. deps.get_orchestrator() is
the only place that references it.
"""

from __future__ import annotations

import uuid

from packages.schemas.python.agent_io import (
    InvestigationState,
    OrchestratorAction,
    OrchestratorDecision,
    RampStrategy,
    TestPlanOutput,
    TestPlanRequest,
    TestStagePlan,
)
from packages.schemas.python.entities import InvestigationStatus, TestType


class StubOrchestrator:
    """Canned responses matching the Orchestrator's documented contract."""

    def plan_test(self, request: TestPlanRequest) -> TestPlanOutput:
        """Stand-in for INVOKE_TEST_PLANNER.

        Echoes the caller's journeys and traffic expectations back into the
        plan rather than returning fixed values, so an endpoint test can
        tell whether the request actually reached the planner.
        """
        traffic = request.target_description.expected_traffic
        requirements = request.target_description.performance_requirements
        peak = traffic.peak_concurrent_users

        return TestPlanOutput(
            test_type=TestType.CAPACITY,
            rationale=(
                "Stubbed plan: ramp to peak expected concurrency to locate the "
                "point where latency degrades."
            ),
            target_concurrency=peak,
            # Field names matter: RampStrategy declares type/step_size/
            # step_duration_s. Pydantic ignores unknown keys by default, so
            # inventing names here would silently produce an empty strategy.
            ramp_strategy=RampStrategy(
                type="step", step_size=max(peak // 4, 1), step_duration_s=120
            ),
            user_journeys=request.target_description.user_journeys,
            thresholds={
                "p95_ms": requirements.p95_ms,
                "max_error_rate": requirements.max_error_rate,
            },
            duration={"total_s": 600},
            stages=[
                TestStagePlan(target_vus=peak // 2, duration_s=300),
                TestStagePlan(target_vus=peak, duration_s=300),
            ],
            success_criteria=[
                f"p95 stays under {requirements.p95_ms}ms at {peak} concurrent users",
                f"error rate stays under {requirements.max_error_rate}",
            ],
        )

    def start_investigation(
        self, investigation_id: uuid.UUID, target_id: uuid.UUID
    ) -> OrchestratorDecision:
        """Stand-in for the UNDERSTAND -> PLAN transition."""
        return OrchestratorDecision(
            next_action=OrchestratorAction.INVOKE_TEST_PLANNER,
            specialist_input=None,
            updated_state=InvestigationState(
                investigation_id=investigation_id,
                target_id=target_id,
                status=InvestigationStatus.PLANNING.value,
            ),
        )

    def continue_investigation(
        self,
        state: InvestigationState,
        test_run_id: uuid.UUID,
    ) -> OrchestratorDecision:
        """Stand-in for POST /api/investigations/{id}/continue.

        Always answers COMPLETE. The real continuation policy is a state
        machine over findings and confidence (orchestrator.md) — modelling
        that here would mean writing the logic twice and getting a second,
        divergent version of it. Terminating immediately keeps the stub
        obviously a stub, and keeps every endpoint test deterministic.
        """
        state.current_test_run_id = test_run_id
        state.status = InvestigationStatus.REPORTING.value
        return OrchestratorDecision(
            next_action=OrchestratorAction.COMPLETE,
            specialist_input=None,
            updated_state=state,
            reasoning_ref=None,
        )
