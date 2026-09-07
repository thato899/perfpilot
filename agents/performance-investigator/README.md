# agents/performance-investigator

**Owner:** Developer 1 (AI / Orchestration)

The most important AI component in the system: turns validated metrics into observations, evidence-backed hypotheses, confidence scores, and recommended follow-up experiments. Never presents speculation as fact — see the hallucination guardrails in its contract.

Not implemented yet — this is Phase 1 work. Full contract: [docs/agents/performance-investigator.md](../../docs/agents/performance-investigator.md). Input/output types: `packages/schemas/python/agent_io.py` (`InvestigationAnalysisRequest`, `InvestigatorOutput`).
