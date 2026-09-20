# PerfPilot planning

`STATUS.md` is the live state. This file records the stable phase handoff and the dependency order for future work.

## Current completion state

| Area | State |
|---|---|
| Phase 0 | COMPLETE |
| Phase 1 foundations | COMPLETE |
| Phase 1 backend integration | COMPLETE |
| Phase 1 runtime E2E | COMPLETE |
| Phase 1 browser E2E | COMPLETE |
| Exact DB-pool reference scenario | NOT REPRODUCED |
| Phase 1 formal sign-off | PENDING Govenor/Team Lead approval |
| Phase 2 | GATED BY PHASE 1 SIGN-OFF |

Phase 1 implementation and real E2E are complete. The verified run used the repo-owned FastAPI, PostgreSQL, Redis, Celery, pinned k6 v0.57.0, deterministic metrics, Investigator, persisted Finding/Report, and Next.js browser path. It was a healthy run; it must not be described as the DB-pool degradation reference scenario.

## Phase 1 implementation record

Merged implementation PRs: #42, #43, #44, #45, #46, and #47, plus the earlier foundation PRs. Primary issues #1–#15 and #27 are closed. Issue #13 is `status:done`; #9 is a resolved architecture question without a lifecycle status. PR #41 was closed without merge because its Phase 1 work was superseded and its remaining policy details belong to Phase 2 investigation-loop work.

## Phase 2 register and dependency graph

Issues #32–#39 remain open, labeled `phase-2` and `status:todo`, until formal Phase 1 sign-off. They must be implementation-ready before work begins and must retain explicit scope boundaries, contracts, persistence/API/UI impacts, security and failure behavior, deterministic-vs-AI ownership, tests, documentation, compatibility, acceptance criteria, Definition of Done, and expected PR scope.

Dependency order:

```text
#32 ──→ #34 ──→ #39
 │
 ├──→ #36
 │      ↑
 └──→ #35 ──→ #37
             └→ #38
```

More explicitly:

- #32 → #34, #36, #39
- #33 → #35, #38
- #35 → #36, #37, #38
- #34 plus stable contracts → #39
- Do not create a #35 ↔ #36 cycle.

After explicit sign-off, #32 and #33 may begin in parallel. #34/#35 wait for their foundations; #36 waits for #32 and #35; UI work follows the stabilized contracts.

## Handoff rule

Do not start Phase 2 implementation, move Phase 2 tickets to `status:in-progress`, or claim formal completion on Govenor’s behalf. The next required action is human review of the Phase 1 closeout and an explicit sign-off decision.
