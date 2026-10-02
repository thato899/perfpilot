"""Persist provider identity and outcome without prompt, response, or secrets."""

from __future__ import annotations

from datetime import UTC, datetime

from packages.ai.runtime import PROMPT_VERSION
from packages.schemas.python.entities import AgentName

from .db import models as m


def record_ai_execution(
    session,
    service,
    agent: AgentName,
    *,
    investigation_id=None,
    test_run_id=None,
    outcome="validated",
    settings=None,
) -> None:
    if service is None and settings is None:
        return
    provider = service.config.provider if service else settings.ai_provider
    model = service.config.model if service else (settings.ai_provider_model or "unconfigured")
    session.add(
        m.AIExecution(
            investigation_id=investigation_id,
            test_run_id=test_run_id,
            agent=agent,
            timestamp=datetime.now(UTC),
            input_reference=f"typed:{agent.value}:{PROMPT_VERSION}",
            output_reference=f"{outcome}:typed:{agent.value}",
            decision=outcome,
            provider=provider[:64],
            model=model[:128],
        )
    )
