# P2-UI-3: Baseline and experiment comparison

The investigation view reads the explicitly selected baseline from the
investigation state, finds that baseline by its test-run identity, and requests
the comparison for the current run. It never chooses a different baseline.
The API comparison response supplies canonical conclusions, threshold values
and outcomes, signed and percentage deltas; the view formats these values and
joins the referenced metric IDs to the baseline/current metric records to show
the two measured values.

## States

- **Loading** — the baseline list and comparison are being fetched.
- **Missing** — no baseline was selected, the selected run is not represented
  in the baseline list, or there is no distinct experiment run. The message
  names the situation and the UI does not select a replacement.
- **Incompatible** — the comparison API refused the pair (HTTP 409), such as
  for different targets or test scenarios. The API message is shown as the
  reason.
- **Unavailable** — fetching failed for another API reason.
- **Available** — baseline and experiment values are paired using metric IDs;
  deltas, per-scope conclusion, thresholds, and threshold outcomes are displayed
  as returned by `packages/metrics` through the API. A null percentage is
  rendered as unavailable, never as 0%.
- **Inconclusive** — displayed when the canonical result has both favorable
  and unfavorable metric directions.
- **Per-metric unavailable/incompatible** — the canonical result status and
  reason are displayed. Unmatched endpoint scopes are listed separately.

Run links use the authenticated same-origin API proxy. Experiment, finding,
and report links target their corresponding records in the current
investigation view. The comparison table includes p50, p95, p99, throughput,
error rate, and concurrency with units and signed absolute/percentage deltas.
The aggregate conclusion is shown first, alongside both runs' p95/error-rate
thresholds and pass/fail outcomes.

## Calculation boundary

The canonical `MetricComparison` response owns the outcome, threshold
evaluation, and deltas. Improvement/regression use the directions of p50/p90/
p95/p99 latency, throughput, and error rate; mixed signals are inconclusive.
The frontend formats and displays those results and does not calculate
comparisons, percentages, threshold results, or conclusions.

## Browser verification

On 2026-09-28, the completed-investigation page was checked in Edge against a
local comparison fixture. The rendered page showed baseline and experiment
values side by side, signed latency/throughput/error-rate/concurrency deltas,
the aggregate improvement conclusion, both runs' thresholds and pass results,
and working run, experiment, finding, report, and metric links.
