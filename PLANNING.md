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
| Phase 3 implementation | CLAIMED; #67 then #68 |

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

Thato's UI work is first and can start independently of #68. Kamogelo's API
and data work follows as the next priority and fixes the documented risk that
editing a plan can change compatibility for an already executed run. Neither
ticket blocks the other. Both owners are assigned and the issue automation
marks claimed tickets `status:in-progress`; each issue contains its scope,
security and failure behavior, tests, acceptance criteria, and Definition of
Done.

### Phase 3 shared-contract handoff

- #68 must preserve the #34/#39 comparison response behavior and specify any
  additive identity or availability field before implementation.
- Thato reviews and signs off any API value consumed by the dashboard/export;
  comparison arithmetic stays in the canonical metrics package.
- Do not claim scenario identity for historical runs unless it can be proven
  from immutable execution data.

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
