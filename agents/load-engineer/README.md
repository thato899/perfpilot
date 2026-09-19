# agents/load-engineer

**Owner:** Developer 2/Govenor (Performance Engine)

Turns an approved `TestPlan` into an executable k6 script, runs it safely (enforcing the configured VU/duration ceiling), and hands raw output to `packages/metrics`.

Implemented in `load_engineer.py`. The Phase 1 Load Engineer is deterministic:
it validates the authorized target, clamps VUs and duration to safety limits,
generates a k6 script, and runs k6. There is no LLM-produced structured output
in this path, so no additional AI validation boundary is required here.
