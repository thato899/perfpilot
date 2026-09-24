# Phase 2 next steps

Phase 1 implementation and real E2E are complete, and Govenor/Team Lead
granted sign-off in PR #48. The exact DB-pool reference demo remains **not
reproduced**. Phase 2 planning is complete and implementation is underway
through the existing owner-specific issues.

## Ownership

| Owner | GitHub | Tickets |
|---|---|---|
| Thato | `thato899` | #35, #38, #39 |
| Kamogelo | `Kamogelo-Skhosana` | #34, #37 |
| Govenor | `malumzz` | #32, #36 |
| Thatayaone | `Thatayaone910` | #33 |

The last verified board state recorded #32, #35, and #38 as merged/completed;
#33's implementation was merged in PR #55; #34 and #37 remained open and
unmerged; and #39 remained blocked on #34. Reconcile live issue labels and
closure state whenever GitHub connectivity is available. Assignment alone does
not mean implementation began.

## Dependency waves

### Wave 1

- Govenor: #32, deterministic comparison metrics — complete.
- Thatayaone: #33, bounded offline agent evaluation — implementation merged; board state to reconcile.
- Thato: #35 architecture/state groundwork — complete.
- Kamogelo: #34 persistence/API groundwork — active and not complete.

### Wave 2

- Govenor: #36 after #32 and #35 contracts stabilize.
- Kamogelo: #37 after the #35 timeline/state API stabilizes; implementation is not merged.
- Thato: #38 after the #35 contract and relevant #33 grounding semantics stabilize — complete.

### Wave 3

- Thato: #39 after #32/#34 comparison contracts stabilize, plus experiment/run identity if supplied by #35; currently blocked on #34.

Preparatory work may proceed in parallel, but each owner must keep the final
integration boundary explicit and avoid cycles or mega-PRs.

## Handoff contracts

- #32 → #34/#39: comparison schema, units, sign semantics, metric coverage, and unavailable/incompatible behavior.
- #35 → #36/#37/#38: event/state schema, hypothesis and experiment identity, approval, budget, ordering, idempotency, and terminal states.
- #34 → #39: baseline identity, retrieval, comparison response, and error envelopes.
- #33 → #35/#38: grounded versus unsupported interpretation, evidence references, confidence constraints, and hostile target-data cases.

## Ready and done

A ticket is ready when its owner/assignee, dependencies, blocks, preconditions,
scope, exclusions, contracts, security, failure behavior, tests, acceptance
criteria, Definition of Done, and PR boundary are explicit. A ticket is done
only after applicable implementation/tests, documentation, CI, human review,
merge to `main`, and post-merge verification.

See the issue bodies for the detailed contract. Do not create replacement
tickets or start work outside the assigned owner-specific branch and PR.
