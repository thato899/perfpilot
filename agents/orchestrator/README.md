# agents/orchestrator

**Owner:** Developer 1/Thatayaone (AI / Orchestration)

The Performance Orchestrator — owns `InvestigationState`, sequences the four specialist agents, and applies the deterministic continuation policy.

The deterministic continuation policy is implemented in `orchestrator.py`. It accepts an `OrchestratorStep` and returns an `OrchestratorDecision` without calling an AI provider, a specialist, a database, or the filesystem.

Configuration comes from `CONFIDENCE_THRESHOLD` (default `0.8`) and `MAX_EXPERIMENTS_PER_INVESTIGATION` (default `3`). Focused policy tests are in `test_orchestrator.py`.

Full contract: [docs/agents/orchestrator.md](../../docs/agents/orchestrator.md). Input/output types: `packages/schemas/python/agent_io.py` (`OrchestratorStep`, `OrchestratorDecision`).
