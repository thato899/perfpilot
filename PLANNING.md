# PerfPilot planning

`STATUS.md` is the live state. This file records stable phase sequencing,
ownership, dependency waves, and cross-owner handoff contracts.

## Completion state

| Area | State |
|---|---|
| Phase 0 | COMPLETE |
| Phase 1 foundations | COMPLETE |
| Phase 1 backend integration | COMPLETE |
| Phase 1 runtime E2E | COMPLETE |
| Phase 1 browser E2E | COMPLETE |
| Exact DB-pool reference scenario | NOT REPRODUCED |
| Phase 1 formal sign-off | GRANTED by Govenor/Team Lead in PR #48 |
| Phase 2 planning | COMPLETE |
| Phase 2 implementation | NOT STARTED |

## Phase 2 ownership

| Owner | GitHub | Tickets | Primary area |
|---|---|---|---|
| Thato | `thato899` | #35, #38, #39 | investigation state and frontend integration |
| Kamogelo | `Kamogelo-Skhosana` | #34, #37 | data/API and timeline integration |
| Govenor | `malumzz` | #32, #36 | deterministic metrics and safe k6 execution |
| Thatayaone | `Thatayaone910` | #33 | bounded agent evaluation |

All eight issues remain open with `phase-2` and `status:todo`. Assignment does not mean implementation has started.

## Dependency waves

```text
Wave 1
  #32  deterministic comparison metrics
  #33  agent evaluation suite
  #35  architecture/state groundwork
  #34  baseline persistence/API groundwork

Wave 2
  #36  approved follow-up execution, after #32 and #35 contracts
  #37  timeline UI, after #35 timeline/state API
  #38  findings UI, after #35 and relevant #33 grounding semantics

Wave 3
  #39  comparison UI, after #32 and #34, plus stable #35 run identity where needed
```

The graph is intentionally acyclic:

- #32 → #34, #36, #39.
- #33 → validation/evaluation expectations for #35 and #38.
- #35 → #36, #37, #38; it may optionally provide experiment identity to #39.
- #34 → #39.

#34 and #35 may do preparatory contract/state work in parallel with #32/#33,
but their final consumers must wait for stable upstream contracts.

## Handoff contracts

- **#32 → #34/#39:** typed comparison schema, units, precision, sign semantics, metric coverage, and unavailable/incompatible behavior. No downstream arithmetic duplication.
- **#35 → #36/#37/#38:** event/state schema, identity for hypotheses and experiments, approval state, budget state, ordering, idempotency, and terminal/error states.
- **#34 → #39:** baseline identity, compatible-run selection, comparison response, and stable error envelopes.
- **#33 → #35/#38:** grounded versus unsupported interpretation, evidence-reference expectations, confidence constraints, and hostile-target-data cases.

Shared schemas, database models, and shared TypeScript contracts require an
explicit contract-change note, consumer-impact statement, compatibility note,
and review from at least one affected owner.

## Definition of Ready

A Phase 2 ticket is ready only when its owner and assignee are correct,
dependencies and blocks are explicit, upstream contracts are available or
explicitly mocked, scope and exclusions are bounded, security/failure behavior
is documented, acceptance criteria are testable, Definition of Done is present,
and the expected PR boundary is clear.

## Definition of Done

Close a Phase 2 issue only after applicable implementation, unit/integration
tests, Postgres/API/worker/browser/E2E evidence, security checks, migration
verification, documentation, CI, human review, merge to `main`, and post-merge
verification are complete. An open PR or local branch is not done.
