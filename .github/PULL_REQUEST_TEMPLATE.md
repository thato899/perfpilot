## What & why

## Linked issue

Closes #

<!-- Closes/Fixes #<n> so the issue board updates automatically on merge.
The issue should already be assigned to you (claimed) before you open this —
claim-check.yml flags it if it isn't. See CONTRIBUTING.md#claim-a-task-before-you-start. -->

## Checklist

- [ ] I claimed the linked issue (self-assigned) before starting, or this PR doesn't close a tracked issue
- [ ] Docs updated in this PR for any contract/behavior change (coding-standards.md §1) — named below, or "no docs affected"
- [ ] Tests added/updated for anything deterministic (see docs/testing/testing-strategy.md)
- [ ] Lint/format run locally and pass (`pnpm lint && pnpm run format:check` and/or `ruff check . && black --check .`)
- [ ] [STATUS.md](../STATUS.md) updated — what I did, what's next
- [ ] This touches a shared path (`packages/schemas/`, `packages/common/`, `docs/` architecture-level, root config) → flagged and got a second opinion (CONTRIBUTING.md#shared-paths--get-a-second-opinion-before-merging)

## Docs touched

## Notes for reviewer
