# agents/orchestrator

**Owner:** Developer 1/Thatayaone (AI / Orchestration)

The Performance Orchestrator — owns `InvestigationState`, sequences the four specialist agents, and applies the deterministic continuation policy.

Implemented in `orchestrator.py`. The class owns deterministic lifecycle
transitions and is injected into the API through `apps/api/deps.py`; specialist
outputs remain typed inputs and the orchestrator never performs metric math.
Full contract: [docs/agents/orchestrator.md](../../docs/agents/orchestrator.md).
