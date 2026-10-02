"""Explicit, bounded live-provider smoke against existing evidence fixtures."""

from __future__ import annotations

import argparse
import os
from time import monotonic

from agents.reporting.fixtures.investigation_states import demo_scenario_request
from agents.reporting.report_builder import build_report_generated
from apps.api.config import get_settings
from evaluations.fixtures import (
    investigator_module,
    investigator_request,
    planner_module,
    planner_request,
)
from packages.ai.runtime import AIConfig, AIConfigurationError, AIProviderError, AIService
from packages.validation import StructuredOutputError


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run bounded live AI specialist fixtures")
    parser.add_argument(
        "--agent",
        choices=("all", "test_planner", "performance_investigator", "reporting"),
        default="all",
        help="run one specialist fixture or all three in order",
    )
    args = parser.parse_args(argv)
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
        if args.agent != "all" and args.agent != agent:
            continue
        started = monotonic()
        try:
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
        except (AIConfigurationError, AIProviderError, StructuredOutputError) as exc:
            elapsed = monotonic() - started
            raise SystemExit(f"{agent}: failed after {elapsed:.1f}s ({exc})") from None
        print(
            f"{agent}: validated in {monotonic() - started:.1f}s "
            f"({service.config.provider}/{service.config.model})"
        )
        if output is None:
            raise RuntimeError("validated output is missing")


if __name__ == "__main__":
    main()
