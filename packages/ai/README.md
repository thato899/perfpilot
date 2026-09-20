# packages/ai

**Owner:** Developer 1/Thatayaone (AI / Orchestration)

The `AIService` provider abstraction every agent calls instead of an AI provider SDK directly (`GeminiProvider`, `DeepSeekProvider`, future providers). Structured-output generation + validation-retry lives here once, not duplicated per agent.

This package contains the working Gemini provider path and shared `AIService`, matching the architecture described in [ADR-004](../../docs/decisions/ADR-004-ai-provider-abstraction.md). Agents use its structured-output boundary; deterministic metrics and lifecycle decisions remain in code.

## Current shape

- `src/config.ts` resolves provider/model values from env
- `src/gemini-provider.ts` calls Gemini's REST API
- `src/ai-service.ts` centralizes text and structured-output calls, including one validation retry
- `src/index.ts` exports the package API
- `tests/ai-service.test.ts` exercises config resolution, text generation, provider routing, and structured retry behavior

Run the package checks from the repository root:

```bash
pnpm --filter @perfpilot/ai typecheck
pnpm --filter @perfpilot/ai test
```
