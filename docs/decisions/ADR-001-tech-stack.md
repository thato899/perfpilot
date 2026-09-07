# ADR-001: Technology Stack

**Status:** Accepted

## Context

We need a stack that (a) four developers with likely-different individual strengths can split cleanly, (b) has mature libraries for everything the product needs (structured LLM output, load testing, a real dashboard), and (c) can be built in hackathon time without fighting the tools.

## Decision

| Layer | Choice |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui, Recharts |
| Backend | Python, FastAPI, Pydantic |
| Load testing | k6 (see [ADR-003](ADR-003-k6-selection.md)) |
| AI | Provider-abstracted — Gemini / DeepSeek initially (see [ADR-004](ADR-004-ai-provider-abstraction.md)) |
| Database | PostgreSQL |
| Background jobs | Celery + Redis |
| Containerization | Docker |

### Why Next.js + TypeScript + Tailwind + shadcn/ui

A performance dashboard is chart- and state-heavy (live test progress, investigation timelines, report views). Next.js gives a conventional, well-documented app structure a team can split by route/feature. TypeScript is not optional here: the frontend consumes the same structured contracts (`packages/schemas/typescript`) that the backend and agents produce, and a typed contract is only as good as a typed consumer. Tailwind + shadcn/ui gets a professional-looking dashboard without a team member needing to be a dedicated designer — important for a 4-person hackathon team where no one is purely "design."

### Why Python + FastAPI + Pydantic

Every AI provider's Python SDKs are first-class, and Pydantic is the natural fit for the project's core discipline: agents exchange *validated structured objects*, not free text (see [system-architecture.md](../architecture/system-architecture.md)). FastAPI gives request/response validation from the same Pydantic models the agents use internally, so the schema is defined once and enforced at every boundary. It's also fast to stand up REST endpoints in, which matters on a hackathon clock.

### Why PostgreSQL

The data model (see [database-design.md](../database/database-design.md)) is relational at its core (Project → Target → TestPlan → TestRun → Metric, Investigation → Finding → Hypothesis → Experiment) with a few genuinely flexible/nested fields (stages, thresholds, evidence lists) that map cleanly to JSONB columns without needing a document database. Postgres does both well in one engine, and every team member already knows SQL. If time-series metric volume ever outgrows plain Postgres, the documented escalation path is a Timescale hypertable on the `Metric` table specifically — not a database swap (see [database-design.md#scalability-note](../database/database-design.md#scalability-note)).

### Why Celery + Redis

Test execution takes minutes and must never block an HTTP request (see [system-architecture.md](../architecture/system-architecture.md)). Celery + Redis is the most conventional, best-documented async task queue in the Python ecosystem — no need to justify a fancier choice for a hackathon-scoped background-job need. Redis doubles as the broker and (in the MVP) needs no separate infrastructure beyond what's already required.

### Why Docker

Four developers need "it runs the same on my machine as everyone else's" more than they need any particular orchestration platform. Docker Compose (documented, not yet implemented — see [local-development.md](../development/local-development.md)) is the right level of infrastructure for a single-team hackathon deployment; Kubernetes or anything distributed is explicitly rejected as overengineering for this phase (see [roadmap.md](../roadmap.md)).

### Why a static bearer token instead of full auth (documented scope decision)

The MVP is single-team, single-tenant, and run against targets the team itself owns. Building real multi-user authentication/authorization spends hackathon time on a problem the product doesn't have yet. A single static token (see [api-contract.md](../api/api-contract.md#authentication-mvp), [security-model.md](../security/security-model.md#auth-documented-as-a-scoped-down-decision-not-an-oversight)) is the documented, deliberate placeholder — the first thing revisited if PerfPilot is ever exposed beyond the team.

## Alternatives considered

- **Django instead of FastAPI** — more batteries-included (admin, ORM), but FastAPI's native Pydantic integration is a better fit for a codebase whose central discipline is schema-validated boundaries everywhere.
- **A JS/TS backend (e.g. NestJS) instead of Python** — would let the whole stack share one language, but every mainstream AI provider SDK and the broader agentic-AI tooling ecosystem is strongest in Python; forcing the AI layer through a less-mature JS SDK is a worse trade than the two-language split.
- **MongoDB instead of PostgreSQL** — the data is genuinely relational (investigations reference test runs reference metrics); a document database would just reimplement joins in application code.
