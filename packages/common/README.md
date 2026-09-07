# packages/common

**Owner:** jointly owned — no single developer; every change goes through PR review from at least one other developer (see [docs/development/team-workflow.md](../../docs/development/team-workflow.md#shared--jointly-owned-paths)).

Cross-cutting utilities used by more than one of `apps/api`, `agents/*`, and `packages/*` (e.g. ID generation conventions, structured logging helpers, config loading). Not implemented yet — add something here only once at least two consumers actually need it; don't pre-populate it speculatively.
