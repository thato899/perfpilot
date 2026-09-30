# P3-METRICS-1: Run-to-run noise in k6 comparisons

Issue: [#71](https://github.com/thato899/perfpilot/issues/71)

This harness measures how much canonical k6 metrics move when the same bounded
plan is repeated. It does not change `compare_metrics`, the API, the database,
or the dashboard. It does not run inside an investigation, and it does not
approve or execute follow-up experiments.

## What a reviewer can inspect

`packages/metrics/repeatability.py` builds `perfpilot.repeatability.v1`. Every
trial is kept. Invalid trials carry a reason and are left out of the ranges.
Valid trials contribute minimum, maximum, and span for p50, p95, p99,
throughput, and error rate. Pairwise conclusions are the existing
`compare_metrics` result of the first valid trial against each later valid
trial.

The report also compares two illustrations, which are not collected trials:

- a p95 increase equal to the observed same-plan span, or 0.001 ms when that span is zero;
- a larger p95 increase outside that span.

Other metrics stay equal in both illustrations. Today both are
`status=available` and `conclusion=regression`. The contract has no noise or
materiality state, so a fluctuation inside the measured span can receive the
same conclusion as a much larger change. A later reviewed policy could treat
absolute deltas inside the measured same-plan span as inconclusive. This
ticket does not apply that policy.

Scenario identity is the existing v1 fingerprint from
`apps/api/scenario_identity.py`. The harness adapts a `TestPlanOutput` into
the JSON field shape that fingerprint already hashes. It does not add a second
identity rule.

## Safety

- The operator must pass `--authorization-confirmed` for a team-owned local target.
- The host must be on `--allowed-hosts`. The default is `localhost,demo.perfpilot.local`.
- The plan must already sit inside `MAX_VIRTUAL_USERS` and `MAX_TEST_DURATION_SECONDS`. The harness does not clamp and does not raise either ceiling.
- Each trial reuses one script and one scenario fingerprint. The process timeout is the plan duration plus 30 seconds, capped by the duration ceiling.
- k6 thresholds in the harness plan are loose so a slow-but-complete run is still measured. That does not relax the VU or duration ceilings.
- A failed version probe, k6 error, timeout, or unreadable summary is an invalid trial with a reason. The rest of the batch still runs. Inconvenient results are not deleted.
- Raw summaries and the report stay under `infrastructure/docker/k6/results/`, which is gitignored. Do not commit them unless the team approves a non-sensitive aggregate.

## Setup

From the repository root, start a team-owned static target that answers
`/health` with HTTP 200:

```bash
mkdir -p /tmp/perfpilot-noise-target
echo ok > /tmp/perfpilot-noise-target/health
python3 -m http.server 8765 --bind 127.0.0.1 --directory /tmp/perfpilot-noise-target
```

`http://localhost:8765` resolves to that process, and `localhost` is on the
default allow-list. Leave the server running in that terminal.

## Command

In a second terminal:

```bash
python3 scripts/k6_repeatability.py \
  --target-url http://localhost:8765 \
  --authorization-confirmed \
  --target-build local-static \
  --journey /health \
  --vus 2 \
  --duration-seconds 5 \
  --trials 5
```

`--target-build` should name the target you actually ran, such as a git
revision of a demo app. `local-static` means the Python static server above.
The pinned engine for the product remains k6 v0.57.0; the report records
whatever `k6 version` prints on the machine that ran the batch.

Exit `0` means at least one valid trial. Exit `1` means the harness refused
to send load. Exit `2` means the report was written and every trial was
invalid.

## Cleanup

Stop the static server with Ctrl-C. The harness replaces
`trial-*.k6-summary.json` inside the output directory at the start of a new
batch so an older longer run is not mixed into the new sample. The default
directory is `infrastructure/docker/k6/results/repeatability/`.

## Files

| Path | Role |
|---|---|
| `packages/metrics/repeatability.py` | Report, ranges, and comparison illustrations |
| `agents/load-engineer/repeatability.py` | Bounded batch runner, outside the investigation loop |
| `scripts/k6_repeatability.py` | Operator command |
| `infrastructure/docker/k6/results/repeatability/` | Local raw summaries and `repeatability-report.json` |

## Tests

Fixture tests cover identical scenario identity, ceilings, retained invalid
trials, ranges, and the unchanged comparison conclusions. They do not invoke
k6. Re-run `packages/metrics/test_metrics.py` with them to confirm
`compare_metrics` behavior is untouched.

## Limitations

- Five short trials describe one local plan. They are not a statistical guarantee and not a soak test.
- The harness uses the first user journey only, the same way script generation does.
- A static file server does not exercise the DB-pool demo. It is only a controlled, authorized target for timing noise.
- Live aggregates, when collected, belong in the sample note below. Raw files stay local.

## Collected sample

One authorized batch was run on 2026-09-30 against `http://localhost:8765`
(`/health` on the local static target, build label `local-static`). k6 was
`v0.57.0` (`commit/50afd82c18`). The plan was 2 VUs for 5 seconds, inside the
5000 VU and 1800 second ceilings. All 5 trials were valid. Raw summaries stay
in the gitignored results directory.

| Metric | Minimum | Maximum | Span |
|---|---:|---:|---:|
| p50 | 0.812 ms | 1.444 ms | 0.632 ms |
| p95 | 1.783 ms | 2.406 ms | 0.623 ms |
| p99 | 2.338 ms | 3.015 ms | 0.677 ms |
| throughput | 443.492 rps | 722.361 rps | 278.869 rps |
| error rate | 0 | 0 | 0 |

`compare_metrics` read the first valid trial against the other four and
returned `improvement`, `inconclusive`, `regression`, and `improvement`, all
with `status=available`. The within-span illustration (p95 +0.623 ms) and the
outside-span illustration (p95 +100.623 ms) were both `regression`. This
sample does not distinguish run noise from a material change.

These five short trials are one local observation, not a confidence interval.
A future policy could treat deltas inside this measured span as inconclusive;
that change is out of scope here.
