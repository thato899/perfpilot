# Agent Evaluation Suite

`evaluations/` is an offline, fixture-first suite for grounding and
hallucination resistance. It consumes the existing typed contracts and public
validation seams; it does not change production prompts, schemas, orchestration,
providers, persistence, or API responses.

## Commands

Run the deterministic suite without credentials, Postgres, Redis, k6, a browser,
or local model inference:

```bash
pytest evaluations -q
```

The root `pytest` command includes this directory through `pyproject.toml`.
The normal CI Python test job therefore runs it as part of the credential-free
test suite.

## Fixture format and coverage

Each `EvaluationCase` records `agent`, `case_id`, `expected`, provider/model
metadata, an invocation double, and an optional truth assertion. Cases expect
either `accepted` or `rejected`. Rejection is split into:

- contract rejection: Pydantic or an existing agent validation boundary;
- truth assertion failure: structurally valid output that contradicts supplied
  metrics, evidence, or deterministic input.

The deterministic cases cover valid output, malformed output, missing and
fabricated metric references, missing evidence, invalid source references,
invalid confidence, unsupported hypotheses, contradictory metrics, numeric
mutation, hallucinated infrastructure signals through invalid evidence, hostile
target text, prompt-injection-like target content, and an unsupported
Orchestrator specialist boundary action.

Every result contains the agent, case, provider, model, expected result, actual
result, and failure reason. A failed assertion prints the complete per-case
record, making the violated contract and observed behavior visible.

## Redaction and safety

`redact()` recursively removes values under API-key, token, secret, password,
credential, and bearer-token fields or patterns. Hostile target text is placed
only in fixture data and is never treated as an instruction. Do not add raw
target payloads or secrets to failure messages or checked-in fixtures.

## Optional live checks

Live checks are not part of normal CI. `evaluations.live.run_live` accepts an
injected provider adapter and refuses more than five cases by default. The
default budget is 2,000 output tokens per case, `$1.00` maximum estimated cost,
and 120 seconds maximum runtime. The adapter requires usage metadata from the
injected provider and rejects responses over any of those limits; this
repository does not create a client or retry live calls.

Live execution must be an explicit command or workflow with credentials
provided by the caller, and its output must retain the same redaction and
per-case reporting rules. It is intentionally excluded from the deterministic
suite and normal CI.