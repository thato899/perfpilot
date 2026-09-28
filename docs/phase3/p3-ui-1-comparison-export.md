# P3-UI-1: Canonical comparison export

Issue: [#67](https://github.com/thato899/perfpilot/issues/67)

## Source and guarantees

Export only the comparison already selected and loaded by the investigation
page. The source is the typed #39 response plus its baseline/current metric
records. The browser formats fields into a file; it never derives metric
values, deltas, thresholds, status, or conclusions.

Both formats use the version marker `perfpilot.comparison.v1`. JSON includes
an ISO-8601 `generated_at` timestamp, target and run identities, the selected
baseline reference, optional experiment identity, unmatched endpoint lists,
and one row per canonical comparison. Each comparison carries its scope,
status, conclusion, reason, metric record IDs, baseline and experiment values,
canonical deltas, threshold values, and threshold pass states.

JSON uses snake-case field names: top-level `schema_version`, `generated_at`,
`target_id`, `baseline`, `experiment`, `units`, `baseline_only_endpoints`,
`experiment_only_endpoints`, and `comparisons`. The baseline reference records
`id`, `target_id`, `test_run_id`, `label`, `selected_by`, `test_type`,
`target_concurrency_users`, and `scenario_fingerprint`. Each comparison row
records `scope`, `status`, `conclusion`, `reason`, metric IDs, `baseline`,
`experiment`, `deltas`, and `thresholds`; metric values and delta names use
the same unit-suffixed names as the CSV headers below.

CSV is one row per comparison scope. Headers carry the units:

- Latency values and deltas use milliseconds (`*_ms`).
- Throughput uses requests per second (`*_rps`).
- Error-rate values, deltas, and threshold limits remain raw fractions (`*_fraction`); for example, `0.01` means 1%.
- Concurrency uses users (`*_users`).
- Percent-change fields (`*_pct`) remain percent values as returned by the API; error-rate absolute deltas remain fractions.

Missing values are JSON `null` and blank CSV cells. They are never converted to
zero. Incompatible/unavailable states and server-provided reasons are retained.
The CSV writer applies RFC 4180 quoting and prefixes formula-like untrusted
text cells before quoting; numeric values stay numeric.

## User interaction and failure behavior

CSV and JSON buttons stay disabled until the selected comparison response has
loaded. Download failures are announced through an accessible alert. The files
contain only target/run/comparison information already available to this
authorized view; credentials, auth headers, raw target responses, and secrets
are excluded.

## Verification

The serializer/component tests cover canonical values, all conclusion and
availability states, null handling, formula neutralization, quoting, disabled
controls, successful download initiation, and download errors. On 2026-09-28,
browser QA in Edge against a local fixture downloaded both
`comparison-run-experiment.csv` and `.json`. The CSV rows retained canonical
run IDs, metric values/deltas, thresholds, outcome/reason, explicit blanks for
missing deltas, and an apostrophe-prefixed formula-like reason. The JSON file
contained the version marker, generated timestamp, target and run identities,
unit definitions, unmatched endpoints, and comparison records.
The page also hydrated without console errors after using a stable `en-US`
number formatter so server and browser decimal separators match.
