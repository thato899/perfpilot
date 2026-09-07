# ADR-003: k6 as the Performance Testing Engine

**Status:** Accepted

## Context

PerfPilot needs to generate and execute real load against a target application. This is explicitly not meant to be a novel contribution of the product — the product's value is the AI-driven investigation *around* load testing, not the load generation itself (see [README.md](../../README.md#what-perfpilot-is)).

## Decision

Use **k6** as the sole execution engine. PerfPilot does not build a custom load generator.

## Rationale

- **k6 scripts are JavaScript**, which is straightforward for an LLM to generate reliably from a structured `TestPlan` (see [load-engineer.md](../agents/load-engineer.md)) — far more reliable than generating, say, a JMeter XML plan or hand-rolled concurrency code.
- **k6 produces structured, machine-readable output** (JSON summaries), which is exactly what `packages/metrics` needs to parse deterministically into `Metric` records — no scraping human-oriented text reports.
- **k6 has built-in staged ramp-up, thresholds, and scenario support**, which map almost one-to-one onto `TestPlan.stages` / `TestPlan.thresholds` — the Load Engineer's job is closer to "translate," not "invent."
- **k6 is a mature, widely-adopted, single-binary tool** — trivial to containerize (`infrastructure/docker`), no server infrastructure of its own required, well-documented enough that any of the four developers can read/debug a generated script.
- Building a custom engine would mean re-solving connection pooling, ramp scheduling, and metric aggregation under load — problems k6 has already solved well, and time better spent on the actual differentiator (the investigation loop).

## Consequences

- The Load Engineer's "generate k6 script" step is bounded by what k6 can express — if a future test type needs something k6 genuinely can't do, that's a real constraint to hit, not a hypothetical one, but nothing in the current [test-planner.md](../agents/test-planner.md) test-type list (load/stress/spike/endurance/capacity/baseline/regression) requires more than k6 already supports.
- k6 becomes a required piece of infrastructure (`infrastructure/docker`) that every developer's local setup needs, documented in [local-development.md](../development/local-development.md).
