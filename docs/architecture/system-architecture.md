# System Architecture

## Goals

PerfPilot is a modular monolith for the hackathon phase: one deployable backend, one frontend, one database, one job queue, one AI abstraction layer — deliberately not a microservice mesh. Module boundaries are enforced by folder ownership and typed contracts (`packages/schemas`), not by network calls. This keeps deployment simple while still letting the pieces be split into services later if the product outgrows the monolith. See [ADR-001](../decisions/ADR-001-tech-stack.md).

## High-level components

```text
┌─────────────────────────────────────────────────────────────────────┐
│                              apps/web                                │
│                 Next.js dashboard — investigation UI                 │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │ REST (docs/api/api-contract.md)
┌───────────────────────────────▼───────────────────────────────────────┐
│                              apps/api                                 │
│                FastAPI — HTTP layer, auth, persistence,               │
│                background job dispatch                                │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────┐      │
│   │                    agents/orchestrator                     │      │
│   │        Performance Orchestrator — owns investigation state  │      │
│   └───┬───────────────┬───────────────────┬─────────────────────┘      │
│       │               │                   │                            │
│  ┌────▼─────┐   ┌─────▼──────┐   ┌────────▼──────────┐   ┌──────────┐  │
│  │  Test    │   │   Load     │   │   Performance      │   │Reporting │  │
│  │ Planner  │   │  Engineer  │   │   Investigator     │   │  Agent   │  │
│  └────┬─────┘   └─────┬──────┘   └────────┬───────────┘   └────┬─────┘  │
│       │               │                   │                    │       │
│       │          ┌────▼─────┐              │                    │       │
│       │          │   k6     │              │                    │       │
│       │          │ (external│              │                    │       │
│       │          │  process)│              │                    │       │
│       │          └────┬─────┘              │                    │       │
│       │               │                    │                    │       │
│       └───────────────┴──────┬─────────────┴────────────────────┘       │
│                               │                                         │
│                     packages/schemas (shared contracts)                │
│                     packages/ai (provider abstraction)                 │
│                     packages/metrics (deterministic calculations)      │
└───────────────┬───────────────────────────────────┬───────────────────┘
                │                                    │
        ┌───────▼────────┐                  ┌────────▼────────┐
        │  PostgreSQL     │                  │  Redis + Celery │
        │  (system of      │                  │  (async test    │
        │   record)        │                  │   execution)    │
        └─────────────────┘                  └─────────────────┘
```

## Layering rules

1. **`apps/web` never talks to agents or k6 directly.** It only calls `apps/api` over the documented REST contract. This is the boundary that lets frontend work proceed against a mocked API before the backend is finished.
2. **`apps/api` never contains agent reasoning.** It receives HTTP requests, validates them against `packages/schemas`, persists state, enqueues background jobs, and invokes the Orchestrator. It does not itself decide test strategy or interpret metrics.
3. **Agents never call each other directly.** Every hand-off goes through the Orchestrator, which is the only component that reads and writes investigation state. This is what keeps the pipeline deterministic instead of becoming a swarm (see [ADR-002](../decisions/ADR-002-multi-agent-architecture.md)).
4. **k6 is invoked, not reimplemented.** The Load Engineer agent generates a k6 script and hands it to a thin execution wrapper in `packages/metrics` / `infrastructure/docker` that runs the real `k6` binary and parses its output. No custom load-generation engine.
5. **AI providers are swappable.** Every agent calls `AIService` from `packages/ai`, never a provider SDK directly. Swapping Gemini for DeepSeek (or adding a third provider) is a configuration change, not a code change in any agent. See [ADR-004](../decisions/ADR-004-ai-provider-abstraction.md).
6. **Long-running work is async.** Executing a k6 test can take minutes. The API enqueues it via Celery and returns immediately with a run ID the frontend polls (or later, subscribes to). No test execution blocks a normal HTTP request/response cycle.

## AI output reliability

This is a hard architectural rule, not a style preference: **the AI is used for reasoning, never for arithmetic or as the source of truth for a number.**

```text
k6 raw output
    │
    ▼
packages/metrics  (Python — parses, aggregates, computes p50/p95/p99,
                    error rate, throughput, threshold pass/fail,
                    regression %, capacity estimate)
    │
    ▼
validated, structured Metric / Finding objects  (packages/schemas)
    │
    ▼
AI (Performance Investigator, Reporting Agent)
    — interprets the numbers, proposes hypotheses, writes prose —
    — never recomputes or overrides a number produced above —
```

Concretely:

- Percentage improvement, regression %, threshold pass/fail, and capacity estimates are computed once, in `packages/metrics`, in plain Python. Agents receive the result as a typed object.
- Every number an agent's output references must trace back to a field in that typed object. An agent output that contains a number not present in its input is a contract violation and is rejected (see each agent's "Failure states" in `docs/agents/`).
- Structured agent outputs are validated against the Pydantic schemas in `packages/schemas/python` before being persisted or shown to the Orchestrator. Invalid output triggers one retry with the validation error fed back to the model; a second failure surfaces as a failed step, not a guess.
- The Performance Investigator must attach an evidence reference (a `Metric`/`Observation` ID) to every hypothesis. A hypothesis with no evidence reference is rejected by validation, not just discouraged by prompt wording.

## Structured communication between components

Wherever two components exchange information and the shape of that information can be defined ahead of time, it is defined in `packages/schemas` and both sides are validated against it. Free-text is reserved for genuinely unstructured content (report prose, human-facing explanations) — never for values another component needs to branch on.

## Observability

Every agent invocation is recorded as an `AIExecution` (see [database design](../database/database-design.md)) carrying `investigation_id`, `test_run_id`, `agent`, `input_reference`, `output_reference`, `decision`, and a timestamp. This is what makes a multi-agent pipeline debuggable after the fact — given a report, you can walk backwards through exactly which agent produced which claim from which evidence.

## What is deliberately not in Phase 0 / MVP

See [docs/roadmap.md](../roadmap.md) for the full breakdown. In short: no Kubernetes, no distributed load-generation cluster, no autonomous agent swarm, no custom LLM, no multi-tenant auth, no billing. A single-tenant modular monolith is the whole target for the hackathon.
