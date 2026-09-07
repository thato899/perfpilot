# agents/load-engineer

**Owner:** Developer 2 (Performance Engine)

Turns an approved `TestPlan` into an executable k6 script, runs it safely (enforcing the configured VU/duration ceiling), and hands raw output to `packages/metrics`.

Not implemented yet — this is Phase 1 work. Full contract: [docs/agents/load-engineer.md](../../docs/agents/load-engineer.md). Input/output types: `packages/schemas/python/agent_io.py` (`LoadExecutionRequest`, `LoadExecutionResult`).
