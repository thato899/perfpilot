# Agent Contract — Performance Investigator Agent

**Owner:** Developer 1/Thatayaone (AI / Orchestration) · **Code location:** `agents/performance-investigator/`

This is the most important AI component of the system, and the one where hallucination risk is highest. Its entire output is structured specifically to make speculation visually and mechanically distinguishable from fact.

## Purpose

Analyze validated performance evidence and investigate *why* performance changes under load: detect anomalies, form hypotheses about their cause, attach evidence, assign confidence, and recommend a follow-up experiment that could confirm or reject each hypothesis.

## Responsibilities

- Compare the current `TestRun`'s metrics against the relevant baseline (the deterministic diff itself — e.g. "p95 went from 420ms to 2.8s" — is computed by `packages/metrics`; this agent's job is to decide whether that diff constitutes a `Finding` worth surfacing and at what severity).
- Distinguish **observations** (what the numbers show) from **hypotheses** (a candidate explanation) from **evidence** (a specific data point that supports a hypothesis) from **confidence** (a numeric estimate of how well the evidence supports the hypothesis) — these are separate fields in the output schema, never merged into one prose blob.
- Recommend a specific follow-up experiment for any hypothesis below the confidence threshold (e.g. "repeat at the same concurrency with the DB connection pool doubled").
- When re-invoked after an experiment runs, update the relevant hypothesis's confidence based on the deterministic comparison `packages/metrics` produced — the agent explains the update, it does not recompute the improvement percentage itself.
- Rank findings by severity (`CRITICAL | HIGH | MEDIUM | LOW | INFO`) using the plan's stated thresholds as the objective bar (a threshold breach is at least `HIGH` by definition; severity above that is judgment).

## Non-responsibilities

- Does **not** perform any numeric calculation that `packages/metrics` should own (percentage change, regression %, raw threshold pass/fail). It receives these as already-computed fields and reasons over them.
- Does **not** execute tests or design test *plans* — it can request an experiment, but the Test Planner turns that request into an executable plan and the Orchestrator decides whether to actually run it.
- Does **not** write the human-facing report — that's the Reporting Agent's job, working from this agent's structured `Finding`/`Hypothesis` output.
- Does **not** present a hypothesis as a conclusion. A hypothesis without an attached evidence reference, or with confidence above what the evidence supports, is a contract violation (see Failure states).

## Input schema

`InvestigationAnalysisRequest`:

```json
{
  "test_run": { "id": "run_01H...", "metrics": ["...validated Metric records..."] },
  "baseline_test_run": { "id": "run_00H...", "metrics": ["...validated Metric records..."] },
  "comparison": { "...": "deterministic diff produced by packages/metrics — p95_delta_ms, p95_delta_pct, error_rate_delta, etc." },
  "thresholds": { "p95_ms": 1000, "max_error_rate": 0.01 },
  "prior_hypotheses": ["optional — set when re-analyzing after an experiment"],
  "infrastructure_metrics": { "db_connection_pool_utilization": 0.98, "cpu_pct": 0.71, "memory_pct": 0.55 }
}
```

## Output schema

`Finding` (see `packages/schemas/python/agent_io.py` for the authoritative type):

```json
{
  "finding": { "id": "find_1", "severity": "HIGH", "summary": "Latency degradation beginning around 750 concurrent users" },
  "observations": [
    { "id": "obs_1", "statement": "p95 increased from 420ms to 2.8 seconds between the 500 and 750 VU stages", "metric_ref": "metric_id(s) this cites" }
  ],
  "hypotheses": [
    {
      "id": "hyp_1",
      "statement": "Database connection pool contention",
      "evidence": [
        { "statement": "DB connection pool utilization reached 98%", "source_ref": "infrastructure_metrics.db_connection_pool_utilization" }
      ],
      "confidence": 0.6,
      "recommended_experiment": { "variable_to_isolate": "db_pool_size", "change": "increase from 50 to 100", "expected_signal": "p95 improves if contention was the cause" }
    }
  ]
}
```

## Guardrails against hallucination (enforced, not just prompted)

- **Every `observations[].statement` must carry a `metric_ref`** pointing to an actual field in the input. Output missing this fails schema validation.
- **Every `hypotheses[].evidence[]` entry must carry a `source_ref`** into the input payload (a metric, an infrastructure metric, or a prior observation id). A hypothesis with an empty `evidence` array is rejected outright — an unsupported hypothesis is not emitted, not even at low confidence.
- **Confidence is a number the agent commits to, not decoration.** The Orchestrator's continuation policy acts on it mechanically (see [orchestrator.md](orchestrator.md)), so confidence must be comparable run over run, not restated in fresh prose each time.
- **No hypothesis states a cause the input data cannot speak to.** If `infrastructure_metrics` wasn't supplied, the agent cannot hypothesize about CPU/memory/DB pool causes — it can only hypothesize about causes evidenced by the `Metric` records it was actually given (e.g. endpoint-level latency skew), and must say explicitly that infrastructure-level causes are untested when it lacks that data.

## Tools

- `packages/ai` (`AIService`) for the analysis/hypothesis-generation reasoning.
- Read access to the current and baseline `Metric` records and any supplied infrastructure metrics, via the Orchestrator-provided input only.
- No execution capability, no direct DB access, no access to other investigations' data.

## Failure states

| Failure | Handling |
|---|---|
| Output hypothesis has no `evidence` entries | Fails schema validation; Orchestrator retries once with the error, then marks the step failed rather than accepting an unsupported claim. |
| Output references a `metric_ref`/`source_ref` not present in the input | Same as above — treated as a hallucinated citation, not accepted. |
| Metrics show no threshold breach and no notable deviation | Valid output is an empty/`INFO`-only finding set — "nothing to report" is a legitimate result, not a failure. |
| Infrastructure metrics are unavailable | Agent may still analyze endpoint-level `Metric` data but must not hypothesize about causes outside that data (see Guardrails); confidence on any resulting hypothesis is capped accordingly. |
