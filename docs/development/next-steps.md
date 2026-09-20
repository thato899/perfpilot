# Phase 2 next steps

Phase 1 implementation and real E2E are complete, and Govenor/Team Lead
granted sign-off in PR #48. The exact DB-pool reference demo remains **not
reproduced**. Phase 2 planning is complete; implementation remains scoped to
the eight existing issues.

## Ownership

| Owner | GitHub | Tickets |
|---|---|---|
| Thato | `thato899` | #35, #38, #39 |
| Kamogelo | `Kamogelo-Skhosana` | #34, #37 |
| Govenor | `malumzz` | #32, #36 |
| Thatayaone | `Thatayaone910` | #33 |

All eight issues remain open with `phase-2` and `status:todo` until the owner
actually starts work. Assignment alone does not mean implementation began.

## Dependency waves

### Wave 1

- Govenor: #32, deterministic comparison metrics.
- Thatayaone: #33, bounded offline agent evaluation.
- Thato: #35 architecture/state groundwork.
- Kamogelo: #34 persistence/API groundwork.

### Wave 2

- Govenor: #36 after #32 and #35 contracts stabilize.
- Kamogelo: #37 after the #35 timeline/state API stabilizes.
- Thato: #38 after the #35 contract and relevant #33 grounding semantics stabilize.

### Wave 3

- Thato: #39 after #32/#34 comparison contracts stabilize, plus experiment/run identity if supplied by #35.

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
