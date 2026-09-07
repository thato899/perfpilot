# packages/ai

**Owner:** Developer 1 (AI / Orchestration)

The `AIService` provider abstraction every agent calls instead of an AI provider SDK directly (`GeminiProvider`, `DeepSeekProvider`, future providers). Structured-output generation + validation-retry lives here once, not duplicated per agent.

Not implemented yet — this is Phase 1 work. Rationale and interface shape: [ADR-004](../../docs/decisions/ADR-004-ai-provider-abstraction.md).
