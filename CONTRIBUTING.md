# Contributing to PerfPilot

This is a 4-person hackathon team project. The goal of this guide is to let everyone move fast in their own area without breaking someone else's.

Each developer uses a different AI coding assistant. See [docs/development/coding-standards.md](docs/development/coding-standards.md) for the rules that follow from that — keeping docs in sync with code, not touching another owner's files without a must-have reason, and flagging it when your work is blocked on (or blocking) someone else's. Task status lives on the [issue board](https://github.com/thato899/perfpilot/issues).

Beyond code ownership, four non-coding process roles (Team Lead, Project Manager, Reviewer, Reporter) are assigned in [docs/development/team-roles.md](docs/development/team-roles.md) — read it if you're unsure who has final say on a scope dispute, who's tracking the board, or who to escalate a stalled shared-contract sign-off to.

## Before you write code

Phase 0 (this commit) is documentation only. Before implementing anything, read:

1. [README.md](README.md) — what we're building and why
2. [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md) and [docs/architecture/agent-architecture.md](docs/architecture/agent-architecture.md)
3. [docs/development/team-workflow.md](docs/development/team-workflow.md) — your ownership area and the boundaries around it
4. The contract doc(s) for whatever you're building (`docs/agents/*.md`, `docs/api/api-contract.md`, `docs/database/database-design.md`)
5. `packages/schemas/` — the actual typed contracts your code must satisfy

If something you need isn't in `packages/schemas` yet, propose the addition there first (see "Changing a shared contract" below) rather than inventing a local shape that only your module understands.

## Claim a task before you start

The issue board only works if two people never work the same task at once. Before you start:

1. Check the issue's **Depends on** note and confirm it's actually satisfied (or fixture-able — see [team-workflow.md's dependency table](docs/development/team-workflow.md#who-depends-on-whom)).
2. **Claim it by self-assigning it** (GitHub *Assignees*, top right of the issue). That's the claim — not a comment, not a message in chat.
3. Assigning yourself automatically flips the label from `status:todo` to `status:in-progress` ([.github/workflows/issue-automation.yml](.github/workflows/issue-automation.yml)) — you don't need to move it by hand.
4. If you unassign yourself without finishing, the label flips back to `status:todo` the same way, so it's visibly free again.

When you open a PR with `Closes #<n>` in the body, [.github/workflows/claim-check.yml](.github/workflows/claim-check.yml) checks that issue is actually assigned to you and flags it (informationally — it doesn't block merge, there's no branch protection) if it isn't. If you want someone else's already-claimed task, ask them first — don't just start a competing branch.

## Branching

```text
main
 └── develop
       ├── feature/<short-description>
       ├── fix/<short-description>
       └── docs/<short-description>
```

- Never commit directly to `main`. `main` only receives merges from `develop` at demo-ready checkpoints.
- Branch from `develop`, open a PR back into `develop`.
- Branch names are kebab-case and describe the change, not the person: `feature/k6-script-generation`, not `feature/dev2-stuff`.

## Commits

Small and meaningful, in the imperative mood, prefixed by type:

```text
docs: define test planner contract
feat: implement k6 script generation
fix: correct p95 aggregation off-by-one
refactor: extract threshold evaluator
test: add investigator hallucination-guard cases
```

Don't bundle unrelated changes into one commit — a reviewer should be able to tell what a commit does from its message alone.

## Pull requests

- Open a PR into `develop` as soon as the branch is in reviewable shape — don't sit on a huge branch.
- Update [STATUS.md](STATUS.md) before you open the PR — what you did, what's next. It's the first thing an AI assistant (yours or a teammate's) reads in a fresh session; if it's stale, that session starts blind. The PR template checklist reminds you.
- Describe *what* changed and *why*, and link the doc section the change implements if applicable.
- At least one other developer approves before merge. For changes touching a **shared** path (see below), get a review from an owner of the other side of that contract, not just anyone.
- Keep PRs scoped to one concern. If you notice unrelated cleanup while working, put it in a separate PR.

## Shared paths — get a second opinion before merging

Most of the repo is owned by exactly one developer (see [docs/development/team-workflow.md](docs/development/team-workflow.md)). A few paths are shared and changing them affects everyone:

- `packages/schemas/**` — the typed contracts every agent and the API build against
- `packages/common/**` — cross-cutting utilities
- `docs/**` (architecture, ADRs) — the agreed design
- Root-level config: `docker-compose.yml` (once created), CI config, `.env.example`

Changing one of these without flagging it is the fastest way to silently break someone else's in-flight work. Post in the team channel before merging, not after.

## Changing a shared contract

1. Open an issue or a short message describing the change and why the current contract doesn't fit.
2. Propose the new shape as a diff to the relevant file in `packages/schemas` (and the matching `docs/agents/*.md` or `docs/api/api-contract.md` section).
3. Get explicit sign-off from anyone whose module consumes that contract before merging.
4. Update both the Python (`packages/schemas/python/`) and TypeScript (`packages/schemas/typescript/`) definitions together — they must not drift.

## Code style (to be enforced once implementation starts)

- **TypeScript** (`apps/web`): ESLint + Prettier, strict mode on.
- **Python** (`apps/api`, `agents/*`, `packages/*`): Black + Ruff, type hints required on public functions, Pydantic for all data crossing a module boundary.
- No commented-out code, no `console.log`/`print` debugging left in a merged PR.

## What not to do

- Don't implement a feature "temporarily" without a corresponding contract in `packages/schemas` — it will need to be redone.
- Don't let an agent perform a calculation (percentages, thresholds, regressions) that belongs in deterministic code — see [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md#ai-output-reliability).
- Don't add a load-testing target that isn't on the allow-list described in [docs/security/security-model.md](docs/security/security-model.md).
