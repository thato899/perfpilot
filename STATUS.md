# STATUS.md

The **live** state of the project. This changes every session — for the stable plan/timeline, see [PLANNING.md](PLANNING.md).

**If you are an AI assistant opening this repo for a session: read this file before doing anything else.** It tells you what's currently being worked on, what's blocked, and what's next — the things a fresh chat tab has no way to know otherwise. Before you end your session (or hand off), update your developer's section below and add a line to the log. This is the whole point of the file: it only works if it stays current.

**Last updated:** 2026-09-12 by Thato (Claude Code)

*Note: this branch (`feature/dashboard-mocked-api`) and `feature/reporting-agent-fixture` (PR #17) were both cut from `main` the same day and both touch this file — expect a small merge conflict here when the second one lands, resolved by combining both entries, not by dropping either.*

---

## Per-developer status

Each section below follows the same template. Update your own section — don't edit someone else's without flagging it with them first (same rule as touching their code, see [CONTRIBUTING.md](CONTRIBUTING.md#what-not-to-do)).

### Thatayaone — AI / Orchestration

**Last updated:** — not yet logged

- **Currently working on:**
- **Just completed:**
- **Blocked on:**
- **Next up:** claim an issue from [docs/development/next-steps.md#thatayaone--developer-1-ai--orchestration](docs/development/next-steps.md#thatayaone--developer-1-ai--orchestration) — start with `packages/ai` (#1), it's the one thing everyone else's agents import.

### Govenor — Performance Engine

**Last updated:** — not yet logged

- **Currently working on:**
- **Just completed:**
- **Blocked on:**
- **Next up:** claim an issue from [docs/development/next-steps.md#govenor--developer-2-performance-engine](docs/development/next-steps.md#govenor--developer-2-performance-engine); also owns unblocking [issue #9](https://github.com/thato899/perfpilot/issues/9) (interval vs. summary metrics) early — see Thato's proposal there, needs your read.

### Kamogelo — Backend / Data

**Last updated:** — not yet logged

- **Currently working on:**
- **Just completed:**
- **Blocked on:**
- **Next up:** claim an issue from [docs/development/next-steps.md#kamogelo--developer-3-backend--data](docs/development/next-steps.md#kamogelo--developer-3-backend--data); also the one who activates `render.yaml` once `apps/api` boots locally.

### Thato — Frontend / Reporting

**Last updated:** 2026-09-12 by Thato (Claude Code)

- **Currently working on:** nothing active right now — both currently-assigned issues (#14, #15) have PRs open awaiting review. Everything in next-steps.md's Thato backlog that doesn't depend on a teammate is done; see next-steps.md's Thato section for the exact per-item status.
- **Just completed:** Dashboard (issue #14, this PR) — `apps/web`: Next.js + TypeScript + Tailwind + shadcn/ui, all four required flows (create target / trigger investigation / watch progress / view report) working against a mocked API (`src/lib/mock-api.ts`, `localStorage`-backed). Verified end to end with a scripted headless-browser run (screenshots + console-error check), not just `next build`. Found a schema gap (`types.ts` had no `ExpectedTraffic`) and fixed it. Tightened CI: `ts-lint` now runs `apps/web`'s own Next.js-flavored eslint config instead of only the generic root one. Since then, added a real automated test suite — Vitest + React Testing Library (`apps/web/README.md#testing`), 21 tests covering `mock-api.ts`'s full behavior (target creation/rejection, tick-by-tick investigation advance to a completed report, finding/hypothesis timing) and the severity/status badge components — plus a new `ts-test` CI job (guarded the same way `ts-lint`/`ts-format` are) so it isn't just running on my machine. This closes the "automated frontend tests" gap the PR originally shipped with flagged as not-yet-done. (Separately, and in parallel: Reporting Agent, issue #15, PR #17 — see that PR/branch for details, not duplicated here.)
- **Blocked on:** nothing for this fixture/mock-first slice. Wiring the dashboard to a real API needs `apps/api` (#12) — noted as a "Not yet done" item in `apps/web/README.md`, not a current blocker since mock-first was the explicit Phase 1 scope. Merging both #17/#18 needs a teammate's second opinion first (shared-path rule, CONTRIBUTING.md) — not something I can/should do unilaterally even though there's no branch protection.
- **Next up:** proposed a recommendation on [issue #9](https://github.com/thato899/perfpilot/issues/9) (summary-at-completion over interval-bucketed metrics, for Phase 1) — waiting on Govenor's read before treating it as settled; this is the one open item that's genuinely not mine to close. Otherwise: pick up the next unclaimed `dev:thato` issue once one exists, or help review a teammate's PR.

---

## Log

Reverse-chronological. One entry per session — a couple of lines, not a full changelog (the git history and issue board are that).

### 2026-09-12 — Thato (Claude Code), second session

- Went back through next-steps.md's Thato backlog end to end to check what was actually left undone (vs. blocked on a teammate). Everything not dependent on another owner was already done from the first session (#14, #15); the two genuinely-blocked items — issue #9 (needs Govenor) and real API/agent wiring (needs #12/#2/#4) — are correctly left alone, not forced.
- Found one real gap that was mine to close: no automated frontend test suite (apps/web/README.md had flagged this as "not yet done"). Added Vitest + React Testing Library (21 tests: `mock-api.ts`'s full behavior including the tick-by-tick investigation lifecycle, plus the severity/status badge components) and a guarded `ts-test` CI job, same pattern as `ts-lint`/`ts-format`. Landed on the existing `feature/dashboard-mocked-api` branch (PR #18, still open/unmerged) since it directly closes that PR's own flagged gap.
- Hit three real toolchain snags getting the suite running locally (documented in `apps/web/README.md#testing` so the next person doesn't rediscover them): Vitest 5/`@vitejs/plugin-react` 6/jsdom 30 all assume a Node newer than this machine's local 20.11 (missing `node:util`'s `styleText`, and an ESM-only jsdom sub-dependency) — pinned to `vitest@3.2.7`, `vite@6.4.3`, `@vitejs/plugin-react@4.7.0`, `jsdom@25.0.1` instead. Also had to flip `pnpm-workspace.yaml`'s `esbuild` build-script gate from its placeholder to `true` (Vite can't run without esbuild's native binary) — unlike `sharp`/`unrs-resolver`, this one isn't optional. None of this should affect CI, which installs a newer Node 20.x via `actions/setup-node@v4`.
- Updated `docs/development/next-steps.md` (Thato's dashboard checkbox note) and `apps/web/README.md` (moved "automated frontend tests" out of "Not yet done", added a Testing section) to match.

### 2026-09-12 — Thato (Claude Code)

- Claimed and completed issue #14 (dashboard): scaffolded `apps/web` (Next.js 16, TypeScript, Tailwind v4, shadcn/ui), built the mock API layer + fixtures, and all four required views. Verified with a real headless-browser run end to end (not just a type-check) — screenshots confirm the home page, target selection, live progress ticking 0 → 1000 VUs, and the final report all render correctly with no console errors.
- Along the way: installed `pnpm` globally (was only reachable via `npx pnpm@version` before — `create-next-app`/`shadcn` both shell out to a bare `pnpm` on PATH) and Playwright's Chromium build, for local verification; neither is a repo dependency. Found a schema gap (`types.ts` had no `ExpectedTraffic`) and fixed it. Tightened `ts-lint` in CI to run `apps/web`'s own Next.js-flavored eslint config (`eslint-config-next`) instead of only the generic root one, which wasn't actually exercising React/Next-specific rules.
- Posted a proposed recommendation on issue #9 (summary-at-completion over interval-bucketed metrics) rather than deciding it unilaterally — it's a joint call with Govenor per roadmap.md.
- Also claimed and completed issue #15 (Reporting Agent) this same session — see PR #17 / the `feature/reporting-agent-fixture` branch for that entry, kept separate since it's a separate PR.

### 2026-09-09 — Thato (Claude Code)

- Set up the Phase 1 engineering process: 8-stage CI pipeline (lint/format/typecheck/test/build/audit for TS+Python, guarded so it's green today and activates automatically as code lands), issue-claim automation (self-assign flips `status:todo`→`status:in-progress`; a non-blocking `claim-check` flags PRs closing unclaimed issues), issue/PR templates, `CODEOWNERS`, root Python/JS tooling configs, real smoke tests for `packages/schemas/python`, a `render.yaml` deployment template for the full planned stack, and this file + `PLANNING.md`.
- Ran `ruff --fix`/`black`/`prettier --write` once against the pre-existing `packages/schemas/python/{entities,agent_io}.py` and `packages/schemas/typescript/types.ts` so the new lint/format CI jobs start green — import ordering, blank lines, and union-type line-wrapping only, no behavior change. Flagged here since `packages/schemas/` is Kamogelo's owned/shared path — worth a glance next session, not a blocker.
- No branch protection applied (team's explicit call — see `PLANNING.md`'s process-decisions section). Landed as a PR, not a direct push to `main`.

---

## Quick links

[PLANNING.md](PLANNING.md) · [Issue board](https://github.com/thato899/perfpilot/issues) · [CONTRIBUTING.md](CONTRIBUTING.md#claim-a-task-before-you-start)
