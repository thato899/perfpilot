# PerfPilot planning

`STATUS.md` is the live state. This file records phase sequencing, ownership,
dependency waves, and cross-owner handoff contracts.

## Completion state

| Area | State |
|---|---|
| Phase 0 | COMPLETE |
| Phase 1 foundations, integrations, runtime and browser E2E | COMPLETE |
| Exact DB-pool reference scenario | NOT REPRODUCED |
| Phase 1 formal sign-off | GRANTED by Govenor/Team Lead in PR #48 |
| Phase 2 planning and implementation | COMPLETE; #32–#39 merged and closed |
| Phase 3 planning | COMPLETE |
| Phase 3 implementation | COMPLETE for #67, #68, #70, #71, #79, and #80; all closed |

The original Phase 3 sequence is complete. Provider ticket #79 is complete and
closed after its bounded DeepSeek evaluation, review, merge, and post-merge
verification. #80 is complete and closed after its bounded Gemini evaluation,
default-model update in PR #91, CI, affected-owner review, merge, and
post-merge verification. The UI polish branch was integrated by PR #77. See
[STATUS.md](STATUS.md) for current evidence.

## Phase 2 ownership and completion

| Owner | GitHub | Tickets |
|---|---|---|
| Thato | `thato899` | #35, #38, #39 |
| Kamogelo | `Kamogelo-Skhosana` | #34, #37 |
| Govenor | `malumzz` | #32, #36 |
| Thatayaone | `Thatayaone910` | #33 |

All Phase 2 issues #32–#39 are merged and closed. The implementation register
and historical dependencies remain in [roadmap.md](docs/roadmap.md).

## Phase 3 ownership and order

| Priority | Issue | Owner | Deliverable | Dependency |
|---|---|---|---|---|
| 1 | [#67](https://github.com/thato899/perfpilot/issues/67) | Thato (`thato899`) | Export selected canonical baseline comparisons as CSV and JSON | #39 complete |
| 2 | [#68](https://github.com/thato899/perfpilot/issues/68) | Kamogelo (`Kamogelo-Skhosana`) | Snapshot immutable scenario identity on TestRuns | #34 and #39 complete |
| 3 | [#70](https://github.com/thato899/perfpilot/issues/70) | Thatayaone (`Thatayaone910`) | Wire production agent calls through AIService | #1 and #33 complete |
| 4 | [#71](https://github.com/thato899/perfpilot/issues/71) | Govenor (`malumzz`) | Characterize repeat-run noise for k6 comparisons | #32, #34, and #36 complete |

This table records the original implementation sequence and ownership. All
four tickets have since been merged and closed. Their scope, security/failure
behavior, tests, acceptance criteria, and Definition of Done remain useful
historical context; their completion evidence is summarized in [STATUS.md](STATUS.md).

### Phase 3 shared-contract handoff (original implementation constraints)

- #68 preserved the #34/#39 comparison response behavior and used an additive
  identity availability field.
- Dashboard/export consumers reviewed the API values; comparison arithmetic
  remains in the canonical metrics package.
- Historical runs do not claim scenario identity without proof from immutable
  execution data.

## Shared contract changes

Shared schemas, database models, and shared TypeScript contracts require an
explicit contract-change note, consumer-impact statement, compatibility note,
and review from at least one affected owner. See
[CONTRIBUTING.md](CONTRIBUTING.md) for shared-path review expectations.

## Definition of Ready

A ticket is ready when its owner and assignee are correct, dependencies and
blocks are explicit, upstream contracts are available or explicitly mocked,
scope and exclusions are bounded, security/failure behavior is documented,
acceptance criteria are testable, a Definition of Done is present, and the
expected PR boundary is clear.

## Definition of Done

Close an issue only after applicable implementation, tests, security checks,
migration verification, documentation, CI, human review, merge to `main`, and
post-merge verification are complete. An open PR or local branch is not done.
