# Security Model

PerfPilot's core function — generating real load against a real application — is the single most dangerous thing this system does. Every safeguard in this document exists to make sure that capability is never pointed somewhere it shouldn't be, or scaled beyond what was intended.

## Target authorization

**Rule: PerfPilot never sends load to a target that hasn't been explicitly confirmed as owned/authorized by the user, and never to a target outside a configured allow-list.**

- Creating a `Target` (`POST /api/projects/{id}/targets`) requires `authorization_confirmed: true` plus `authorization_confirmed_by`. The API rejects target creation without this — there is no "confirm later" state that still permits testing.
- Beyond the confirmation flag, `base_url`'s host must appear in `ALLOWED_TARGET_HOSTS` (see `.env.example`). This is a second, independent gate: a user cannot self-confirm their way into testing an arbitrary public domain the operator hasn't allow-listed.
- The Load Engineer re-checks the target against the allow-list immediately before invoking k6 (defense in depth — see [load-engineer.md](../agents/load-engineer.md#failure-states)), not just at `Target`-creation time, so a target that was allow-listed and later removed can't still be hit by an in-flight plan.
- The product's messaging (dashboard copy, docs, demo) never encourages testing a public site the user doesn't control. The reference [demo scenario](../demo-scenario.md) uses a target the team owns.

## Rate limiting / safety ceiling

**Rule: the system's own configuration bounds how much load it can ever generate, independent of what any test plan or agent requests.**

- `MAX_VIRTUAL_USERS` and `MAX_TEST_DURATION_SECONDS` (`.env.example`) are enforced by the Load Engineer at execution time. A `TestPlan` requesting more is clamped, not silently honored and not silently rejected — the run proceeds at the ceiling and is flagged `clamped` in its result (see [load-engineer.md](../agents/load-engineer.md#output-schema)).
- `MAX_EXPERIMENTS_PER_INVESTIGATION` bounds how many follow-up load tests a single investigation can trigger on its own initiative, so a mis-calibrated confidence loop can't keep generating load indefinitely (see [orchestrator.md](../agents/orchestrator.md#continuation-policy)).
- `POST /api/investigations/{id}/experiments` is a human-in-the-loop confirmation point: the Orchestrator/Investigator can *recommend* an experiment, but nothing generates additional load until that recommendation is explicitly approved (a human today; potentially a configurable auto-approve policy later, documented as a future decision, not a default).

## Sandboxing

- The hackathon demo runs against a target the team deploys and owns (see [demo scenario](../demo-scenario.md)) — never a shared or public target.
- `infrastructure/docker` documents k6 running in its own container with network access scoped to the target(s) actually needed for the demo, not open egress.

## Secrets

- Never log: API keys, database credentials, AI provider keys, the API auth token, or any target application credential.
- All secrets are supplied via environment variables (`.env`, git-ignored — see `.env.example` for the documented set) and are never embedded in a k6 script, a stored `TestPlan`, or a prompt sent to an AI provider. A target's auth is referenced by a stored credential ID in `LoadExecutionRequest` (see [load-engineer.md](../agents/load-engineer.md#input-schema)), never inlined as plaintext in agent input/output that gets persisted or logged.
- `AIExecution` records (the audit trail, see [database design](../database/database-design.md#aiexecution)) store references to request/response payloads, not raw secrets — anything redacted before being sent to a provider must also be redacted in what gets persisted for audit.

## Redaction

- Before any data is sent to an AI provider, it passes through the same structured schemas documented in `docs/agents/*.md` — this is itself a redaction boundary, since agents only ever receive the specific typed fields their contract lists, not a raw dump of request/response bodies, headers, or logs that might carry incidental secrets or PII.
- Target application response bodies, headers, and error messages are treated as **untrusted data** if they ever flow into an agent's input (e.g. an error message quoted in an `Observation`) — never as instructions. This matters because the Performance Investigator's input can include text that originated from the target application under test; that text is data to reason about, not something the agent should treat as directives about how to behave. This guards against prompt-injection via a target's own error pages/response content.

## Auth (documented as a scoped-down decision, not an oversight)

The MVP uses one static bearer token for the whole API (see [api-contract.md](../api/api-contract.md#authentication-mvp)) rather than per-user accounts, OAuth, or RBAC. This is intentional for a single-team hackathon build — full multi-tenant auth, unnecessary for a project one team runs against targets it owns, is explicitly out of scope for Phase 0/1 (see [roadmap.md](../roadmap.md)) and [ADR-001](../decisions/ADR-001-tech-stack.md). If PerfPilot is ever exposed beyond the team, this is the first thing that must change before that happens.

## What's explicitly deferred

- Per-user authentication/authorization and multi-tenant data isolation.
- Signed/verifiable authorization records (today: a confirmation flag + name, trusted at face value within the team).
- Automated abuse detection beyond the static ceilings above.
