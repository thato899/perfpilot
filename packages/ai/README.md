# packages/ai

**Owner:** Developer 1/Thatayaone (AI / Orchestration)

The `AIService` provider abstraction every agent calls instead of an AI provider SDK directly (`GeminiProvider`, `DeepSeekProvider`, future providers). Structured-output generation + validation-retry lives here once, not duplicated per agent.

This package is scaffolded with a working Gemini provider path and a shared `AIService`, matching the intended architecture described in [ADR-004](../../docs/decisions/ADR-004-ai-provider-abstraction.md).

## Current shape

- `src/config.ts` resolves provider/model values from env
- `src/gemini-provider.ts` calls Gemini's REST API
- `src/ai-service.ts` centralizes text and structured-output calls, including one validation retry
- `src/index.ts` exports the package API
- `tests/ai-service.test.ts` exercises config resolution, text generation, and structured retry behavior

> Runtime verification is currently blocked in this container because Node and pnpm are not installed, so I could not execute the TypeScript test suite here. The code is in place, but the environment needs the project’s Node toolchain available before the package can be proven green.
