# Team Roles (Non-Coding)

[team-workflow.md](team-workflow.md) defines who owns which *code*. This document defines who owns which *process* — the coordination work that happens around the code, not in it. These are two independent axes: every person below still owns their coding area exactly as defined in team-workflow.md; a process role is layered on top of that, not a replacement for it.

## At a glance

| Person | Coding ownership | Process role |
|---|---|---|
| Thatayaone | AI / Orchestration | **Reviewer** |
| Govenor | Performance Engine | **Team Lead** |
| Kamogelo | Backend / Data | **Project Manager** |
| Thato | Frontend / Reporting | **Reporter** |

## Team Lead — Govenor

**Mandate:** final decision-maker when the team can't resolve something peer-to-peer.

In scope:
- Breaks ties when two developers (or two AI assistants acting on their behalf) disagree on scope, architecture, or a shared-contract shape — the escalation path when the sign-off process in [CONTRIBUTING.md](../../CONTRIBUTING.md#changing-a-shared-contract) stalls because the affected owners can't agree.
- Owns each phase's Definition of Done — decides when Phase 0/1/2 (per [roadmap.md](../roadmap.md)) is actually complete enough to move on, not just individually checked off by each owner.
- Repository governance: branch protection on `main`, who has merge rights, and when a `develop` → `main` promotion happens (demo-ready checkpoints, per [team-workflow.md's git workflow](team-workflow.md#git-workflow)).
- Final call on pulling scope into Phase 1 vs. deferring it, per [roadmap.md's Phase 3+ deferred-by-design list](../roadmap.md#phase-3-deferred-by-design-not-oversights).
- Owns that the daily sync ([team-workflow.md](team-workflow.md#communication)) happens — doesn't have to run it personally every day, but is accountable if it stops happening.

Out of scope:
- Does not override another developer's ownership of their own code — team-workflow.md's ownership map stands; Team Lead breaks ties, doesn't dictate implementation.
- Does not replace the Reviewer's review-quality mandate or the PM's day-to-day board tracking.

> **Open item:** GitHub admin rights on this repo currently sit with the `thato899` account (repo owner). If Team Lead is expected to exercise repo governance directly (branch protection, merge rights) rather than through Thato, that needs an explicit access grant — flag it in the next sync rather than assuming it's already in place.

## Project Manager — Kamogelo

**Mandate:** the issue board and the timeline are accurate, and stay accurate.

In scope:
- Keeps the [issue board](https://github.com/thato899/perfpilot/issues) (Phase 1 milestone) honest — labels match reality, issues close when their PR merges, and `status:todo`/`status:in-progress` issues that have gone stale get chased rather than left to self-report.
- Tracks the Phase 1 timeline against [roadmap.md](../roadmap.md) and flags slippage before it's a demo-day surprise, not after.
- Owns the **Depends on / Blocks** bookkeeping across issues — when someone flags a `status:blocked` issue per [coding-standards.md §5](coding-standards.md#5-note-it-when-something-is-waiting-on-your-code), PM makes sure it's visible and actually gets unblocked, not just labeled and forgotten.
- Watches the shared/jointly-owned paths (`packages/schemas/`, `packages/common/`, `docs/`, root config — see [team-workflow.md](team-workflow.md#shared--jointly-owned-paths)) for changes that slipped through without the required second opinion.

Out of scope:
- Does not decide technical architecture — that's each area's owner, or Team Lead on an unresolved dispute.
- Does not review code for correctness — that's the per-PR reviewer requirement in CONTRIBUTING.md, backstopped by the Reviewer role below.

## Reviewer — Thatayaone

**Mandate:** the bar for what "reviewed" means, not a queue of every PR.

In scope:
- Defines what a good review looks like (consistent with [coding-standards.md §2](coding-standards.md#2-rules-for-good-coding)) and calls it out when a PR approval reads as a rubber stamp rather than an actual review.
- Spot-checks that merged PRs actually did the doc updates [coding-standards.md §1](coding-standards.md#1-code-and-docs-move-together) requires, not just the code change.
- Owns escalation when a shared-contract PR doesn't have the sign-off [CONTRIBUTING.md's "Changing a shared contract"](../../CONTRIBUTING.md#changing-a-shared-contract) process requires, and blocks merge until it does.
- First point of contact when the developer assigned to review a given PR is unsure whether it's good enough to merge.

Out of scope:
- Does not have to personally review every PR — the per-PR "at least one other developer approves" rule in CONTRIBUTING.md is unchanged; any developer can be that reviewer. This role owns the *standard*, not a bottleneck.
- Does not decide product or roadmap scope — that's Team Lead / PM territory.

## Reporter — Thato

**Mandate:** the team's status is legible to people who aren't in the daily sync.

In scope:
- Produces stakeholder-facing status: what shipped, what's blocked, demo-readiness — narrated from the issue board (PM keeps the board accurate; Reporter turns it into a readable update).
- Owns the demo-day narrative and any external summary of project state (e.g. a judge-facing readout).
- Writes the periodic status update referenced in [team-workflow.md's Communication section](team-workflow.md#communication), if the team wants a written artifact rather than only a verbal daily sync.

Out of scope:
- Does not decide what counts as "done" — Team Lead owns Definition of Done; Reporter reports state, doesn't adjudicate it.
- Does not chase people to update the board — that's PM; Reporter consumes board state rather than enforcing it.

> **Naming note:** "Reporter" (this role — the human status/communications role) is unrelated to the **Reporting Agent** (`agents/reporting`, a coding deliverable also owned by Thato per [team-workflow.md](team-workflow.md#ownership-map)). Same person, two different things — one is a process role, the other is a piece of the product.
