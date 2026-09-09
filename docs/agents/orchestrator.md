# Agent Contract — Performance Orchestrator

**Owner:** Developer 1/Thatayaone (AI / Orchestration) · **Code location:** `agents/orchestrator/`

## Purpose

The Orchestrator is the lead performance engineer. It owns the `InvestigationState`, decides which specialist runs next, validates every specialist's output, and decides when an investigation is complete. It is the only component that reads and writes investigation state, and the only component allowed to invoke a specialist agent.

## Responsibilities

- Create and resume an `Investigation` (a request to determine capacity / diagnose a regression / validate a fix — see [database design](../database/database-design.md)).
- Determine the current step of the lifecycle (`UNDERSTAND → PLAN → GENERATE → EXECUTE → OBSERVE → INVESTIGATE → EXPERIMENT → COMPARE → REPORT`, see [data-flow.md](../architecture/data-flow.md)) from the current `InvestigationState`.
- Invoke exactly the specialist appropriate for that step, passing only the structured slice of state that specialist's input schema requires.
- Validate each specialist's output against its Pydantic output schema (`packages/schemas/python/agent_io.py`). Reject and retry once (with the validation error appended to the retry prompt) on failure; escalate to a failed step on a second failure.
- Apply deterministic rules to decide whether the investigation loop continues (another experiment) or is complete — see "Continuation policy" below. This decision consults AI-produced signals (e.g. the Investigator's confidence and `recommended_experiments`) but the go/stop logic itself is plain code, not a free-text LLM judgment.
- Enforce the hard experiment budget and safety limits (`MAX_VIRTUAL_USERS`, `MAX_TEST_DURATION_SECONDS`, max follow-up experiments per investigation) regardless of what any agent recommends.
- Maintain investigation history (every state transition, every specialist invocation) for audit/debugging.
- Hand the final assembled evidence to the Reporting Agent once the investigation is marked complete.

## Non-responsibilities

- Does **not** design test plans, write k6 scripts, compute metrics, form hypotheses, or write report prose — each belongs to a specialist.
- Does **not** talk to the AI provider directly for domain reasoning; if the Orchestrator itself needs an LLM call (e.g. to summarize *why* it's continuing the loop for a human-facing log), that call still goes through `packages/ai`, and its output is a log annotation, never a decision input.
- Does **not** let one specialist call another directly.
- Does **not** persist to the database itself in the MVP — it operates on state handed to it by `apps/api`, and returns the updated state for `apps/api` to persist. (This keeps the Orchestrator a plain, testable function of `(state, event) -> (state, next_action)` rather than something with its own DB session lifecycle. See [system-architecture.md](../architecture/system-architecture.md).)

## Input schema

`OrchestratorStep` (see `packages/schemas/python/agent_io.py`):

```json
{
  "investigation_state": { "...": "InvestigationState, see data-flow.md" },
  "event": {
    "type": "test_run_completed | user_requested_continue | timeout",
    "payload": { "...": "e.g. test_run_id whose metrics are now available" }
  }
}
```

## Output schema

`OrchestratorDecision`:

```json
{
  "next_action": "invoke_test_planner | invoke_load_engineer | invoke_investigator | invoke_reporting_agent | wait | complete",
  "specialist_input": { "...": "the narrow structured input for next_action, if any" },
  "updated_state": { "...": "InvestigationState with this step's results merged in" },
  "reasoning_ref": "ai_execution_id — pointer to the log of any AI call this decision consulted, for audit"
}
```

## Continuation policy (deterministic)

Pseudocode — the actual logic, not an LLM prompt:

```text
if investigation.experiments_run >= MAX_EXPERIMENTS_PER_INVESTIGATION:
    -> complete (report with current confidence, flag budget exhausted)
if top_finding.severity in (CRITICAL, HIGH) and top_hypothesis.confidence < CONFIDENCE_THRESHOLD:
    if top_hypothesis.recommended_experiment is present and not yet run:
        -> invoke_test_planner with that experiment's parameters
if no unresolved HIGH/CRITICAL finding remains, or confidence threshold met:
    -> invoke_reporting_agent
```

`CONFIDENCE_THRESHOLD` defaults to 0.8 and `MAX_EXPERIMENTS_PER_INVESTIGATION` defaults to 3; both are configuration, not hardcoded.

## Tools

- `packages/ai` (`AIService`) — only for non-decision-critical summarization/logging, per Non-responsibilities above.
- Read/write access to the in-memory `InvestigationState` object it's given; no direct DB or filesystem access in the MVP.
- Calls into each specialist agent's public entry point (a plain function/class call in-process for the MVP monolith — not a network call).

## Failure states

| Failure | Handling |
|---|---|
| Specialist returns output that fails schema validation | One retry with the validation error included; second failure marks the step `failed` in state and surfaces to the API layer as a 422-equivalent with the validation detail, not a silent fallback. |
| Specialist call raises (provider error, timeout) | Marked `failed`, surfaced with the underlying error; the investigation is left in its last good state so it can be resumed rather than restarted. |
| Continuation policy would exceed a hard safety limit | The limit wins; the investigation completes early and the report says explicitly that the budget/limit was hit rather than implying the investigation was exhaustive. |
| Investigation state is missing a field a specialist's input schema requires | Programmer error — this should be caught by Pydantic validation before the specialist is ever invoked; fails loudly in development, never silently defaults a required field. |
