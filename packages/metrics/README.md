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

The result includes an absolute and percentage concurrency delta, plus each
run's p95 and maximum error-rate thresholds and whether that run met them.
Thresholds are passed in by the caller because they belong to each test plan;
they are never inferred from the metrics. The overall `conclusion` uses the
canonical deltas: lower p50/p90/p95/p99 latency and error rate, or higher
throughput, are improvement signals. If every non-zero signal points the same
way the result is `improvement` or `regression`; opposing signals are
`inconclusive`; no changes are `unchanged`. A missing/incompatible pair returns
`unavailable`/`incompatible`. Concurrency is shown but does not influence the
performance conclusion because it is a test input.

The result has one of three statuses:

- `available`: all supported deltas are present.
- `incompatible`: the endpoint scopes differ, so no deltas are calculated.
- `unavailable`: a required baseline denominator is zero or invalid, so the
	affected percentage must not be invented.

The typed result includes p50/p90/p95/p99 latency, throughput, error rate,
metric/test-run identity, concurrency, thresholds, threshold outcomes, and
absolute and percentage deltas. Consumers crossing the API or agent boundary should call
`comparison.model_dump(mode="json")`.

Implemented in `metrics.py`. Consumers: `agents/load-engineer` (raw parsing),
the API runtime adapter (persisted Metric records), and
`agents/performance-investigator`/`agents/reporting` (already-computed values,
never recomputed by an agent).
