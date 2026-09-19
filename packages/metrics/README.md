# packages/metrics

**Owner:** Developer 2/Govenor (Performance Engine)

Deterministic, non-AI calculations: parses raw k6 output into validated `Metric` records, computes p50/p90/p95/p99, throughput, error rate, threshold pass/fail, regression percentage, and capacity estimates. This is the layer the whole "AI reasons, code calculates" rule depends on — see [system-architecture.md#ai-output-reliability](../../docs/architecture/system-architecture.md).

Implemented in `metrics.py`. Consumers: `agents/load-engineer` (raw parsing),
the API runtime adapter (persisted Metric records), and
`agents/performance-investigator`/`agents/reporting` (already-computed values,
never recomputed by an agent).
