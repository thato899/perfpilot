# Coding Standards & AI-Assisted Workflow Rules

Each developer on this project uses a different AI coding assistant. None of those assistants share this conversation, or each other's — the only thing they all have in common is what's committed to this repo. That makes this document load-bearing in a way it wouldn't be on a single-assistant team: **if a rule isn't written down here, the next AI session (yours or a teammate's) has no way to know it.** Treat this file as the contract your assistant works against, the same way `packages/schemas` is the contract your code works against.

This extends [CONTRIBUTING.md](../../CONTRIBUTING.md) and [team-workflow.md](team-workflow.md) — read those first. This doc is the "how we actually work" layer on top of "who owns what."

## 0. Start every session with STATUS.md

Before you (or your AI assistant) touch anything: read [STATUS.md](../../STATUS.md) — it's the live "what's currently being worked on, what's blocked, what's next" for all four developers, and [PLANNING.md](../../PLANNING.md) for the dated plan behind it. Before you end a session, update your section and add a log line. A stale STATUS.md defeats the entire reason it exists — the next AI session (yours next time, or a teammate's) has no other way to know what changed since the docs were written.

## 1. Code and docs move together

A PR that changes behavior and doesn't touch the corresponding doc is incomplete, not just under-documented — the next person (human or AI) reading `docs/agents/load-engineer.md` to understand the Load Engineer will be reading something that no longer describes the code.

- Changed an agent's input/output shape? Update the matching `docs/agents/*.md` **and** `packages/schemas` in the same PR.
- Changed an API endpoint? Update `docs/api/api-contract.md` in the same PR.
- Changed the DB schema? Update `docs/database/database-design.md` in the same PR.
- Changed how a piece of infrastructure is run? Update `docs/development/local-development.md` in the same PR.
- Finished a task on the [issue board](https://github.com/thato899/perfpilot/issues)? Move it — see §3.

If your assistant proposes a code change, ask it to name which doc(s) the change touches before you merge. If none do, say so explicitly in the PR description rather than leaving it unstated.

## 2. Rules for good coding

Baseline (also in [CONTRIBUTING.md](../../CONTRIBUTING.md#code-style-to-be-enforced-once-implementation-starts)):

- **TypeScript** (`apps/web`): ESLint + Prettier, strict mode on.
- **Python** (`apps/api`, `agents/*`, `packages/*`): Black + Ruff, type hints required on public functions, Pydantic for all data crossing a module boundary.
- No commented-out code, no `console.log`/`print` debugging left in a merged PR.

Additional rules for working with an AI assistant specifically:

- **Small, reviewable diffs.** An assistant that rewrites a whole file to change one function makes review impossible for a human *or* another assistant reading the diff later. Ask for scoped changes.
- **No invented contracts.** If your assistant needs a shape that isn't in `packages/schemas` yet, that's a contract proposal (see [CONTRIBUTING.md](../../CONTRIBUTING.md#changing-a-shared-contract)), not a local type it can define quietly inside your module.
- **Tests for anything deterministic.** `packages/metrics`, the Orchestrator's continuation policy, threshold/regression calculations — anything that isn't an LLM call needs a test with a fixed input and an exact expected output. See [testing-strategy.md](../testing/testing-strategy.md).
- **Docstrings on public functions**, especially agent entry points — the next AI session reads the docstring before it reads the implementation.
- **Commit messages describe the change, not the tool.** `feat: add p95 regression calculation`, not `feat: AI-generated metrics update`. The commit history should read the same regardless of which assistant or person made it.
- **Schema changes need the owning agent's sign-off**, not just whichever AI assistant happened to touch the file — see [team-workflow.md](team-workflow.md#shared--jointly-owned-paths).

## 3. Issue board — tasks and status

Tracked as [GitHub Issues](https://github.com/thato899/perfpilot/issues) on the **Phase 1 — thin vertical slice** milestone, one issue per task from [next-steps.md](next-steps.md).

- **Status labels:** `status:todo` → `status:in-progress` → `status:done`, plus `status:blocked` for anything waiting on another owner (see §4). The `status:todo` ↔ `status:in-progress` move now happens automatically when you self-assign/unassign the issue ([.github/workflows/issue-automation.yml](../../.github/workflows/issue-automation.yml) — see [CONTRIBUTING.md#claim-a-task-before-you-start](../../CONTRIBUTING.md#claim-a-task-before-you-start)). `status:blocked` and `status:done` are still yours to set by hand — don't wait for someone else to notice.
- **Owner labels:** `dev:thatayaone`, `dev:govenor`, `dev:kamogelo`, `dev:thato`.
- Before starting a task, check its issue for a **Depends on** note and confirm that dependency is actually satisfied (or fixture-able — most are, per the [dependency table](team-workflow.md#who-depends-on-whom)).
- Close the issue in the same PR that finishes the task (`Closes #<n>` in the PR description), so the board and the code stay in sync automatically.

## 4. Respect each other's work

Ownership (per [team-workflow.md](team-workflow.md#ownership-map)) exists so four people using four different assistants aren't fighting over the same files. Default to not touching a file outside your ownership.

- **If it's a genuine must** — a bug in someone else's module is blocking you, or their code doesn't match the documented contract — fix the minimum needed to unblock yourself, say so explicitly in the PR description (what you changed and why it couldn't wait), and tag the owner for review before merging. Don't silently refactor or restyle a file you don't own while you're in there.
- **If it's not a must** — you'd just do it differently — open an issue or flag it in the daily sync instead of changing it yourself. A different assistant's style in a file you don't own is not a defect.
- **Shared paths** (`packages/schemas/`, `packages/common/`, `docs/` architecture-level content, root config) always need a second opinion before merging, regardless of how small the change looks — see [CONTRIBUTING.md](../../CONTRIBUTING.md#shared-paths--get-a-second-opinion-before-merging).

## 5. Note it when something is waiting on your code

This is the rule most likely to get skipped, because from inside your own surface a blocking dependency is invisible — you can't see who's stalled on the other side. Check both directions before you merge:

- **Is anything waiting on what you're about to ship?** Check the [dependency table](team-workflow.md#who-depends-on-whom) — if you own something listed as a producer (e.g. `packages/ai`, `packages/metrics`, the Orchestrator's `InvestigationState`), the consumers listed there need to know when it changes shape, not just when it first lands. A comment on their issue ("this landed / this changed, here's what's different") is enough.
- **Are you waiting on something that doesn't exist yet?** Don't silently stub around it forever and let it go unnoticed:
  1. Label the relevant issue (or open one) `status:blocked` and add a one-line **Blocked by:** note naming the owner and what you need from them.
  2. Leave a `# BLOCKED-ON: <issue link> — <what's missing>` (or `// BLOCKED-ON:` in TS) comment at the exact spot in code where the fixture/stub stands in for the real thing, so the next person reading the code — not just the board — sees it.
  3. Raise it in the daily sync per [team-workflow.md](team-workflow.md#communication) if it's actually holding you up, not just theoretically pending.

The goal isn't ceremony — most Phase 1 dependencies are fixture-able and non-blocking by design (see the dependency table). This rule is for the minority that aren't, so they don't turn into a silent surprise the week of the demo.
