"""Explicit, bounded live-provider smoke against existing evidence fixtures."""

from __future__ import annotations

import os

from agents.reporting.fixtures.investigation_states import demo_scenario_request
from agents.reporting.report_builder import build_report_generated
from apps.api.config import get_settings
from evaluations.fixtures import (
    investigator_module,
    investigator_request,
    planner_module,
    planner_request,
)
from packages.ai.runtime import AIConfig, AIService


def main() -> None:
    if os.environ.get("AI_LIVE_SMOKE") != "1":
        raise SystemExit("Set AI_LIVE_SMOKE=1 to permit live provider calls")
    settings = get_settings()
    if not settings.ai_provider_enabled:
        raise SystemExit("Set AI_PROVIDER_ENABLED=true and select AI_PROVIDER")
    cases = (
        ("test_planner", planner_request(), "Plan a bounded capacity test."),
        (
            "performance_investigator",
            investigator_request(),
            "Interpret the threshold breach and propose a falsifiable experiment.",
        ),
        (
            "reporting",
            demo_scenario_request(),
            "Summarize evidence, canonical values, and grounded recommendations.",
        ),
    )
    for agent, typed_request, instruction in cases:
        service = AIService(AIConfig.from_settings(settings, agent))

        def generate(prompt, *, _service=service, _agent=agent, _request=typed_request):
            return _service.generate(_agent, _request, prompt)

        if agent == "test_planner":
            output = (
                planner_module()
                .TestPlanner()
                .create_plan_generated(generate, typed_request, prompt=instruction)
            )
        elif agent == "performance_investigator":
            output = (
                investigator_module()
                .PerformanceInvestigator()
                .analyze_generated(generate, typed_request, prompt=instruction)
            )
        else:
            output = build_report_generated(generate, typed_request, prompt=instruction)
        print(f"{agent}: validated ({service.config.provider}/{service.config.model})")
        if output is None:
            raise RuntimeError("validated output is missing")


if __name__ == "__main__":
    main()
