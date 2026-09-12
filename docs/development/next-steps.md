# Next Steps — Phase 1 Kickoff

Phase 0 (documentation and contracts) is done — see the [Phase 0 definition of done](../../README.md#phase-0-definition-of-done) in the README, all checked off. This document is the practical "what do I do Monday morning" companion to [team-workflow.md](team-workflow.md) (ownership map, git flow) and [roadmap.md](../roadmap.md) (Phase 1 scope). Read those two first if you haven't — this doc doesn't repeat their content, it turns it into a checklist.

Every checklist item below is also tracked as an issue on the [task board](https://github.com/thato899/perfpilot/issues) (`Phase 1 — thin vertical slice` milestone), labeled by owner (`dev:thatayaone`/`dev:govenor`/`dev:kamogelo`/`dev:thato`) and status (`status:todo` → `status:in-progress` → `status:done`, or `status:blocked`). **The board is the live source of truth for status** — this file is the plan, the board is what's actually done. See [coding-standards.md](coding-standards.md) for how to use it and the rules for working across four different AI assistants on one codebase.

## Everyone, before writing code

1. Read [STATUS.md](../../STATUS.md) — what's already in progress, what's blocked, what's next. Update your section before you end your session, or the next one (yours or a teammate's) starts blind.
2. Re-read [CONTRIBUTING.md](../../CONTRIBUTING.md#before-you-write-code) — in particular, don't invent a local data shape if it should live in `packages/schemas`.
3. `cp .env.example .env` and fill in the keys you need (see [local-development.md](local-development.md#environment-setup)).
4. Branch off `develop`, never off `main`: `feature/<short-description>` (see [team-workflow.md](team-workflow.md#git-workflow)).
5. **Claim your task first** — self-assign its issue before starting (see [CONTRIBUTING.md#claim-a-task-before-you-start](../../CONTRIBUTING.md#claim-a-task-before-you-start)).
6. Post in the team channel before touching a shared path (`packages/schemas/`, `packages/common/`, `docs/`, root config) — see [CONTRIBUTING.md](../../CONTRIBUTING.md#shared-paths--get-a-second-opinion-before-merging).

## Thatayaone — Developer 1 (AI / Orchestration)

Owns: `agents/orchestrator/`, `agents/test-planner/`, `agents/performance-investigator/`, `packages/ai/`

- [ ] Stand up `packages/ai` with one working provider (`GeminiProvider` or `DeepSeekProvider` — pick one, see [ADR-004](../decisions/ADR-004-ai-provider-abstraction.md)).
- [ ] Build the Orchestrator's deterministic continuation policy (state machine, not prompted) — see [orchestrator.md](../agents/orchestrator.md).
- [ ] Test Planner: produce a valid `TestPlan` for the [demo scenario](../demo-scenario.md)'s inputs.
- [ ] Performance Investigator: produce a valid `Finding` from **fixture** metrics first, then wire to real ones — see [performance-investigator.md](../agents/performance-investigator.md).
- [ ] Structured-output validation for all four specialist agents' schemas against `packages/schemas`.
- Unblocks Kamogelo: your agents can be stubbed with canned responses so Developer 3/Kamogelo doesn't wait on you — confirm the stub shape with them early.

## Govenor — Developer 2 (Performance Engine)

Owns: `agents/load-engineer/`, `packages/metrics/`, `infrastructure/docker/k6/`

- [ ] k6 script generation for one journey type (start with whatever the [demo scenario](../demo-scenario.md) needs).
- [ ] Execution wrapper with the safety ceiling enforced — see [load-engineer.md](../agents/load-engineer.md) and [security-model.md](../security/security-model.md).
- [ ] `packages/metrics`: compute p50/p95/p99, error rate, threshold pass/fail, and regression % from **real** k6 JSON output (this is deterministic code, not an LLM call — see [system-architecture.md#ai-output-reliability](../architecture/system-architecture.md)).
- [ ] Open question to settle early with Thato: does `Metric` need interval/time-bucketed rows for the dashboard's live view, or is summary-at-completion enough for the MVP? (See [roadmap.md](../roadmap.md#open-questions-to-revisit-not-blocking-phase-1).)

## Kamogelo — Developer 3 (Backend / Data)

Owns: `apps/api/`, database migrations, `packages/schemas/`

- [ ] Stand up `infrastructure/docker/docker-compose.yml` per the planned service layout in [local-development.md](local-development.md#planned-service-layout-infrastructuredocker) — you're first to need it, so you're building it.
- [ ] Migrate the Postgres schema per [database-design.md](../database/database-design.md) (Alembic or equivalent).
- [ ] Build the `apps/api` endpoints in [api-contract.md](../api/api-contract.md) that the Phase 1 slice actually needs: projects, targets, test plan/run, investigation create/get.
- [ ] Wire Celery for async test execution.
- [ ] You own `packages/schemas` canonically — when Thatayaone, Govenor, or Thato need a contract change, that's a sign-off from you, not a unilateral edit on their part (see [team-workflow.md](team-workflow.md#shared--jointly-owned-paths)).
- You can build every endpoint against `packages/schemas` with the Orchestrator stubbed — you don't need to wait on Thatayaone's agents to be finished.

## Thato — Developer 4 (Frontend / Reporting)

Owns: `apps/web/`, `agents/reporting/`

- [ ] Minimal dashboard: create a target, trigger an investigation, watch a test run's progress, view the resulting report.
- [x] Reporting Agent: produce a valid `Report` from **fixture** `InvestigationState` first, then wire to a real one — see [reporting-agent.md](../agents/reporting-agent.md). Done: `agents/reporting/report_builder.py` (issue #15) — deterministic (template, not AI-generated prose yet — `packages/ai` doesn't exist, see `# BLOCKED-ON: #1` in the code) but contract-checked (`validate_report`) and tested against the demo-scenario fixture and the "no findings" case. Wiring to a real `InvestigationState` still pending on the Orchestrator (#2) and Investigator (#4).
- [ ] You can build the dashboard against a mocked API returning fixture `InvestigationState`/`Report` payloads — don't wait on a real investigation ever having run.
- [ ] Open question to settle early with Govenor: see above (interval-bucketed metrics vs. summary-at-completion).

## Definition of done for Phase 1

The [demo scenario](../demo-scenario.md) runs for real, once, start to finish, producing a report a stakeholder could read. See [roadmap.md](../roadmap.md) for what's explicitly deferred to Phase 2+ — don't build ahead of that list.

## Daily sync

10 minutes, covering: (1) anything you changed in a shared path, (2) any contract you need changed, (3) anything blocking you on another owner's surface. See [team-workflow.md](team-workflow.md#communication).
