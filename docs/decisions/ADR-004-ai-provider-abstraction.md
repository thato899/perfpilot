# ADR-004: AI Provider Abstraction

**Status:** Accepted

## Context

The product's differentiator is the investigation *behavior*, not an attachment to any one model provider. Model availability, pricing, and quality shift constantly (and often matter a lot in a hackathon-judging or cost context); business logic tightly coupled to one provider's SDK would need to be rewritten every time that changes.

## Decision

Every agent calls a single internal interface, `AIService` (in `packages/ai`), never a provider SDK directly:

```text
AIService
    │
    ├── GeminiProvider
    ├── DeepSeekProvider
    └── FutureProvider
```

`AIService` exposes (conceptually — exact method signatures are Phase 1 implementation, not frozen here):

- a structured-output call: `generate_structured(prompt, output_schema) -> ValidatedModel`, which validates the provider's response against the target Pydantic model and retries once with the validation error on failure (this is the primitive every agent in `docs/agents/*.md` is built on)
- a plain-text call for genuinely unstructured output (e.g. report prose fields)
- provider/model selection driven by configuration (`AI_PROVIDER`, `AI_PROVIDER_MODEL`, and optional per-agent overrides — see `.env.example`), never hardcoded in an agent's code

The active provider (and even the model *per agent* — e.g. a stronger reasoning model for the Performance Investigator, a lighter one for the Test Planner) is a configuration change, not a code change.

## Rationale

- **Replaceability**: swapping Gemini for DeepSeek, or adding a third provider, touches `packages/ai` only. No agent's code changes.
- **Per-agent model selection**: the Performance Investigator (see [performance-investigator.md](../agents/performance-investigator.md)) is the most reasoning-heavy agent in the system and may warrant a stronger/more expensive model than the Test Planner; the abstraction supports that without special-casing it in agent code.
- **Testability**: agents can be tested against a fake `AIService` that returns fixture responses, without any network/API-key dependency (see [testing-strategy.md](../testing/testing-strategy.md)).
- **Structured-output enforcement lives in one place**: the retry-on-validation-failure behavior (see [system-architecture.md#ai-output-reliability](../architecture/system-architecture.md)) is implemented once in `AIService`, not duplicated per agent.

## Consequences

- `packages/ai` becomes a required dependency of every agent — it's a small, stable surface, owned by Developer 1/Thatayaone, and changes to it should be rare once Phase 1 starts (see [team-workflow.md](../development/team-workflow.md)).
- Provider-specific quirks (rate limits, differing structured-output mechanisms — e.g. function calling vs. JSON mode) are absorbed inside each `*Provider` implementation, not leaked into agent code.
- We do not commit, in Phase 0, to automatic provider fallback (e.g. "if Gemini is down, silently retry on DeepSeek") — that's a real feature with real implications (different providers may produce different quality/behavior for the same prompt) and is deferred as a documented future decision, not built speculatively now.
