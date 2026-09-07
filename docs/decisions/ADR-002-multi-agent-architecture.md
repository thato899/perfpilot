# ADR-002: One Orchestrator + Four Specialized Agents

**Status:** Accepted

## Context

The product's core differentiator is an AI-driven performance *investigation* — plan, execute, observe, hypothesize, experiment, compare, report. We need an agent architecture that can carry out that loop reliably, be debuggable when it produces a wrong answer, and be splittable across four developers.

## Decision

Use exactly **one Orchestrator agent + four specialized agents** (Test Planner, Load Engineer, Performance Investigator, Reporting Agent), coordinated as a deterministic pipeline — never a swarm where agents autonomously decide to invoke each other. Full shape: [agent-architecture.md](../architecture/agent-architecture.md).

## Alternatives considered

### One giant "performance AI" agent

A single agent/prompt responsible for planning, k6 generation, metric interpretation, and report writing.

Rejected because:
- A prompt trying to do all four jobs at once produces vague output at every step — there's no way to give it a tight, single-purpose instruction set.
- Undebuggable: if the final report is wrong, there's no way to tell whether the planning, the interpretation, or the writing step was at fault, because they're not separate steps.
- Impossible to enforce the "AI reasons, code calculates" rule (see [system-architecture.md](../architecture/system-architecture.md)) cleanly — a single agent handling both plan generation and metric interpretation blurs exactly the boundary we need to keep sharp.
- Can't be split across four developers — everyone would be editing the same prompt.

### Uncontrolled agent swarm (agents free to spawn/message each other)

Rejected because:
- Non-deterministic: the same input could take a different path through the system on different runs, which is unacceptable for something that produces real load against a real target.
- Impossible to bound cost or load-generation side effects — nothing stops a swarm from deciding to run "just one more experiment" indefinitely (see the safety ceilings in [security-model.md](../security/security-model.md)).
- Hard to test: agent evaluation (see [testing-strategy.md](../testing/testing-strategy.md#agent-evaluation)) depends on each agent having a fixed, narrow input/output contract; a swarm's agents don't have that by design.

### One orchestrator + four specialists (chosen)

- Each specialist has one job, a narrow input/output schema, and clear non-responsibilities (see `docs/agents/*.md`) — this is what makes each agent independently testable and independently ownable.
- The Orchestrator is the single place investigation-loop logic lives, and that logic is deterministic code (see [orchestrator.md#continuation-policy](../agents/orchestrator.md#continuation-policy-deterministic)), not an LLM asked "should we continue?" in free text — so the loop is guaranteed to terminate and its decisions are auditable.
- Maps directly onto the four-developer team split (see [team-workflow.md](../development/team-workflow.md)) — this was a factor in the decision, not just a coincidence.

## Consequences

- Every hand-off between specialists goes through the Orchestrator and a typed schema in `packages/schemas` — slightly more ceremony than letting two agents talk directly, in exchange for every hand-off being validated and logged (`AIExecution`, see [database-design.md](../database/database-design.md#aiexecution)).
- Adding a future fifth specialist (e.g. a dedicated "Anomaly Detector" separate from the Investigator) is possible without restructuring — it just adds one more branch to the Orchestrator's dispatch, so long as it keeps the same one-job-one-contract discipline as the other four.
