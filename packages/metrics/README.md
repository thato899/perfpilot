# packages/metrics

**Owner:** Developer 2/Govenor (Performance Engine)

Deterministic, non-AI calculations: parses raw k6 output into validated `Metric` records, computes p50/p90/p95/p99, throughput, error rate, threshold pass/fail, regression percentage, and capacity estimates. This is the layer the whole "AI reasons, code calculates" rule depends on — see [system-architecture.md#ai-output-reliability](../../docs/architecture/system-architecture.md).

Not implemented yet — this is Phase 1 work. Consumers: `agents/load-engineer` (raw parsing), `agents/performance-investigator` and `agents/reporting` (already-computed comparisons/estimates, never recomputed by an agent).
