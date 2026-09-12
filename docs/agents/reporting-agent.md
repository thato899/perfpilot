# Agent Contract — Performance Reporting Agent

**Owner:** Developer 4/Thato (Frontend / Reporting) · **Code location:** `agents/reporting/`

## Purpose

Convert a complete investigation (test runs, metrics, findings, hypotheses, experiments, decisions) into a clear, human-readable engineering report with an executive summary, capacity estimate, ranked findings, bottleneck analysis, actionable recommendations, and a regression comparison against prior runs.

## Responsibilities

- Executive summary in plain language (e.g. "The application remained healthy up to ~500 concurrent users; degradation began around 750").
- Capacity section: estimated sustainable capacity and a recommended operating capacity, both taken from `packages/metrics`' deterministic capacity estimate (see below) — the agent explains and contextualizes this number, it does not derive it.
- Key metrics table: throughput, p50/p95/p99, error rate, peak concurrency tested.
- Findings, ranked `CRITICAL → INFO`, each carrying the Investigator's observations/hypotheses/evidence/confidence verbatim (the Reporting Agent may rephrase for readability but must not alter the substance, the confidence number, or invent new evidence).
- Bottleneck analysis section per finding: observation, likely cause, evidence, confidence — a direct, readable rendering of the Investigator's `Finding`/`Hypothesis` objects.
- Actionable recommendations (e.g. "Investigate database connection pool saturation," "Inspect slow queries," "Move non-critical post-processing to asynchronous workers") grounded in the confirmed/high-confidence hypotheses — not generic performance advice unconnected to this investigation's evidence.
- Regression section comparing current run(s) against the previous baseline, using the deterministic percentage `packages/metrics` computed (e.g. "Previous p95: 420ms, Current p95: 890ms, Regression: +112%").

## Non-responsibilities

- Does **not** generate new findings, hypotheses, or evidence — it synthesizes what the Performance Investigator already produced (with its confidence carried through, not restated as if it were now certain).
- Does **not** compute the capacity estimate, regression percentage, or any other number — those are computed once in `packages/metrics` and passed in.
- Does **not** decide whether the investigation is complete or needs another experiment — that's the Orchestrator; this agent is only invoked once the Orchestrator has already decided to report.
- Does **not** own the dashboard's live/in-progress views (e.g. "test running, 340/1000 VUs") — that's `apps/web` rendering live `TestRun`/`Metric` data directly from the API. This agent produces the *final* report artifact for a completed (or budget-exhausted) investigation.

## Input schema

`ReportRequest` (`packages/schemas/python/agent_io.py` — field names below are the canonical ones; this doc previously showed a `capacity`/`estimated_sustainable_users` shape that didn't match the schema file and no `key_metrics` field at all — fixed here while implementing `agents/reporting` against it, see issue #15):

```json
{
  "investigation_id": "inv_01H...",
  "investigation_state": { "...": "full InvestigationState, see data-flow.md — this is the one agent allowed the full state, since its job is synthesis" },
  "capacity_estimate": { "sustainable_concurrency": 620, "recommended_operating_concurrency": 500, "method": "packages/metrics deterministic estimate — see database-design.md" },
  "regression_comparison": { "previous_p95_ms": 420, "current_p95_ms": 890, "regression_pct": 112.0 },
  "key_metrics": { "throughput_rps": 340, "p50_ms": 120, "p95_ms": 890, "p99_ms": 1450, "error_rate": 0.008, "peak_concurrency_tested": 1000 }
}
```

`key_metrics` is a new field (added alongside the `agents/reporting` implementation): nothing upstream of `ReportRequest` previously carried the "Key metrics table" data this agent's Responsibilities section requires — it's computed once by `packages/metrics` and passed straight through, same as `capacity_estimate`/`regression_comparison`, never recomputed here. Flagged for Govenor/Kamogelo as a schema-shape addition, not a unilaterally final one.

## Output schema

`Report`:

```json
{
  "id": "rep_01H...",
  "executive_summary": "string",
  "capacity": { "sustainable_concurrency": 620, "recommended_operating_concurrency": 500, "method": "packages/metrics deterministic estimate — see database-design.md" },
  "key_metrics": { "throughput_rps": 340, "p50_ms": 120, "p95_ms": 890, "p99_ms": 1450, "error_rate": 0.008, "peak_concurrency_tested": 1000 },
  "findings": [ { "id": "string", "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "summary": "string" } ],
  "bottleneck_analysis": [ { "observation": "string", "likely_cause": "string", "evidence": ["string"], "confidence": 0.87 } ],
  "recommendations": [ { "finding_id": "string", "statement": "Investigate database connection pool saturation.", "priority": "HIGH" } ],
  "regression": { "previous_p95_ms": 420, "current_p95_ms": 890, "regression_pct": 112.0 }
}
```

Note for whoever wires `apps/api`'s persistence/response mapping (issue #12): `packages/schemas/typescript/types.ts`'s dashboard-facing `Report`/`CapacitySummary` uses different field names again (e.g. `estimatedSustainableUsers`) for frontend convenience — that's a deliberate, separate layer (per [system-architecture.md](../architecture/system-architecture.md)'s agent-output vs. API-response distinction), not a second drift to silently reconcile. Whoever builds the `ReportOutput` → `entities.Report` → frontend `Report` mapping needs to know these three shapes name the same concepts differently on purpose.

## Tools

- `packages/ai` (`AIService`) for the prose synthesis (executive summary, recommendation phrasing).
- Read-only access to the full `InvestigationState` and the deterministic `capacity_estimate`/`regression_comparison` it's handed — no independent data access.

## Failure states

| Failure | Handling |
|---|---|
| Output recommendation is not traceable to any finding/hypothesis in the input | Rejected by validation (recommendations must reference a `finding_id`); generic advice with no grounding is not accepted output. |
| Output alters a confidence value or metric present in the input | Rejected — these are compared programmatically against the input on validation, since they must pass through unchanged. |
| Investigation has no findings at all (fully healthy run) | Valid output: a positive executive summary and capacity section with an empty findings/recommendations list — not an error. |
