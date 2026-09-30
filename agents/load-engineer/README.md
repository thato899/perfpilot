# agents/load-engineer

**Owner:** Developer 2/Govenor (Performance Engine)

Turns an approved `TestPlan` into an executable k6 script, runs it safely (enforcing the configured VU/duration ceiling), and hands raw output to `packages/metrics`.

Implemented in `load_engineer.py`. The Phase 1 Load Engineer is deterministic:
it validates the authorized target, clamps VUs and duration to safety limits,
generates a k6 script, and runs k6. There is no LLM-produced structured output
in this path, so no additional AI validation boundary is required here.

`repeatability.py` is a separate operator harness for repeated identical
trials. It refuses plans over the VU or duration ceiling instead of clamping
them, and it does not enter the investigation or experiment loop. See
[docs/phase3/p3-metrics-1-run-noise.md](../../docs/phase3/p3-metrics-1-run-noise.md).
