# Multi-Agent Architecture

## Shape: one orchestrator, four specialists

PerfPilot uses **1 Orchestrator + 4 specialized agents**. This is a fixed, deterministic pipeline shape — not a pool of agents that decide amongst themselves who does what. See [ADR-002](../decisions/ADR-002-multi-agent-architecture.md) for the reasoning against a single mega-agent and against an uncontrolled swarm.

```text
                    ┌───────────────────────┐
                    │  Performance          │
                    │  Orchestrator         │
                    └──────────┬────────────┘
                               │  owns investigation state
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
       Test Planner      Load Engineer     Performance
          Agent             Agent           Investigator
                                               Agent
             │                 │                 │
             └─────────────────┼─────────────────┘
                               │
                               ▼
                     Reporting Agent
```

Every arrow above is mediated by the Orchestrator: no agent calls another agent's code or prompt directly. An agent receives a request from the Orchestrator, returns a structured result to the Orchestrator, and has no visibility into any other agent's internal reasoning.

## Why this shape and not alternatives

| Alternative considered | Why rejected |
|---|---|
| One giant "performance AI" agent | Impossible to keep prompts focused; a single prompt trying to plan tests, write k6, interpret metrics, and write reports produces vague, unreliable output at every step, and it's undebuggable — you can't tell which "part" of the agent went wrong. |
| Uncontrolled agent swarm (agents autonomously decide to spawn / message each other) | Non-deterministic, hard to test, hard to bound cost and load-generation side effects, and directly contradicts the requirement that test execution be safe and controlled. |
| 1 orchestrator + 4 specialists (**chosen**) | Each agent has one job and a narrow, testable input/output contract. The Orchestrator is the single place that decides "what happens next," which keeps the overall system's behavior predictable and traceable. |

## Agent responsibility boundaries

The four specialists are deliberately split along a **plan → execute → interpret → communicate** axis, which also happens to map cleanly onto how deterministic vs. AI-driven each step is:

| Agent | Decides | Does NOT decide |
|---|---|---|
| Test Planner | What kind of test to run, target concurrency, ramp strategy, thresholds | How the test is technically implemented in k6; whether a metric result indicates a bottleneck |
| Load Engineer | How to implement the plan as a k6 script, how to execute it safely, how raw metrics are collected | Whether the plan is the right one; what a metric result *means* |
| Performance Investigator | What the metrics indicate, what hypotheses explain an anomaly, how confident to be, what follow-up experiment would test a hypothesis | Whether to actually run that follow-up experiment (that's an Orchestrator decision); the report's framing for a human audience |
| Reporting Agent | How to present the investigation's findings, capacity estimate, and recommendations to a human | New findings, new hypotheses, or new numbers — it only synthesizes what Investigator + metrics already produced |

This table is the fastest way to resolve "which agent should do X" during implementation: find the row, and if it's not that agent's column, it belongs to the Orchestrator or to deterministic code in `packages/metrics`.

## The Orchestrator is not a fifth specialist

The Orchestrator does not itself plan tests, write k6, or interpret metrics. Its job is coordination and state:

- create/resume an `Investigation`
- decide which specialist runs next given the current state
- assemble the narrow, structured input each specialist needs (never "the whole conversation so far")
- validate each specialist's output against its schema before accepting it
- decide whether the investigation loop continues (another experiment) or is complete
- persist investigation history so the process is resumable and auditable

Full contract: [docs/agents/orchestrator.md](../agents/orchestrator.md).

## Agent state and memory

No agent has open-ended access to full conversation history. The Orchestrator holds one explicit `InvestigationState` object and hands each agent only the slice it needs for its current task (see `packages/schemas/python/agent_io.py` for the exact shape). This is what keeps prompts small, keeps cost bounded, and prevents one agent's hallucination from silently becoming another agent's "fact." See [docs/architecture/data-flow.md](data-flow.md#investigation-state) for the state shape and how it evolves through a run.

## Contracts live in one place

Every agent's input schema, output schema, responsibilities, non-responsibilities, tools, and failure states are documented in `docs/agents/<agent>.md` and implemented as Pydantic models in `packages/schemas/python/agent_io.py`. Anyone implementing an agent builds against that file, not against another developer's in-progress code — this is what lets four people build four agents in parallel.
