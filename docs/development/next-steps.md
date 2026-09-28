# Phase 3 next steps

Phase 1 and Phase 2 are complete. The exact DB-pool reference scenario remains
unreproduced. Phase 3 focuses on sharing canonical comparison results and
preserving run identity when plans change.

## Priority order

| Priority | Owner | Issue | Deliverable |
|---|---|---|---|
| 1 | Thato (`thato899`) | [#67](https://github.com/thato899/perfpilot/issues/67) | Export the selected comparison as CSV and JSON |
| 2 | Kamogelo (`Kamogelo-Skhosana`) | [#68](https://github.com/thato899/perfpilot/issues/68) | Persist immutable scenario identity on each TestRun |
| 3 | Thatayaone (`Thatayaone910`) | [#70](https://github.com/thato899/perfpilot/issues/70) | Route live specialist calls through AIService |
| 4 | Govenor (`malumzz`) | [#71](https://github.com/thato899/perfpilot/issues/71) | Characterize run-to-run noise in k6 comparisons |

Thato's export uses the existing #39 comparison contract and can proceed
without waiting for #68. Kamogelo's follow-up preserves the scenario that a
run actually executed and keeps later comparison compatibility stable after a
TestPlan edit. Do not infer legacy run identity from mutable plans. Thatayaone's
follow-up integrates already available AI provider seams into the real worker;
Govenor's work measures current comparison noise without altering behavior.

See the [Phase 3 roadmap](../roadmap.md#phase-3-sharing-and-reproducibility),
[issue bodies](https://github.com/thato899/perfpilot/issues?q=is%3Aissue+is%3Aopen+label%3Aphase-3),
and [PLANNING.md](../../PLANNING.md) for the full boundaries and handoffs.

The issues are assigned to their owners and marked `status:in-progress` by the
repository's claim-label automation. Close them only after their Definition of
Done, merge, and post-merge verification.
