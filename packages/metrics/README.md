# packages/metrics

**Owner:** Developer 2/Govenor (Performance Engine)

Deterministic, non-AI calculations: parses raw k6 output into validated `Metric` records, computes p50/p90/p95/p99, throughput, error rate, threshold pass/fail, regression percentage, and capacity estimates. This is the layer the whole "AI reasons, code calculates" rule depends on — see [system-architecture.md#ai-output-reliability](../../docs/architecture/system-architecture.md).

## Comparison contract

`compare_metrics(baseline, current)` returns a validated `MetricComparison`.
It compares records with the same endpoint scope; different concurrency values
are valid for capacity-stage comparisons and are returned in the result. Every
delta uses `current - baseline`: positive latency/error deltas are worse, while
positive throughput deltas are better. Percentage deltas use the baseline as
the denominator and are rounded to six decimal places.

The result has one of three statuses:

- `available`: all supported deltas are present.
- `incompatible`: the endpoint scopes differ, so no deltas are calculated.
- `unavailable`: a required baseline denominator is zero or invalid, so the
	affected percentage must not be invented.

The typed result includes p50/p90/p95/p99 latency, throughput, error-rate,
metric/test-run identity, concurrency, and both absolute and percentage deltas.
Consumers crossing the API or agent boundary should call
`comparison.model_dump(mode="json")`.

Implemented in `metrics.py`. Consumers: `agents/load-engineer` (raw parsing),
the API runtime adapter (persisted Metric records), and
`agents/performance-investigator`/`agents/reporting` (already-computed values,
never recomputed by an agent).
