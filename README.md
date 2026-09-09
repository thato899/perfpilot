# PerfPilot

> An AI Performance Engineer that designs performance experiments, generates realistic workloads, investigates bottlenecks, and determines what an application can actually handle.

**Status:** Phase 0 — architecture and documentation foundation. No application code has been implemented yet. See [Definition of Done](#phase-0-definition-of-done) below.

---

## What PerfPilot is

PerfPilot is not a chatbot wrapped around k6. It is an AI-driven performance **investigation** system. Given a target application, it reasons about what should be tested, generates and runs real load tests with k6, watches for degradation, forms hypotheses about *why* performance degrades, designs follow-up experiments to test those hypotheses, and produces a report a human engineer would actually trust.

It should eventually be able to answer questions like:

- "Can this application handle 5,000 concurrent users?"
- "At what concurrency level does this application begin to degrade?"
- "Why did performance deteriorate?"
- "Did our optimization actually improve performance?"

## Core lifecycle

```text
UNDERSTAND → PLAN → GENERATE → EXECUTE → OBSERVE → INVESTIGATE → EXPERIMENT → COMPARE → REPORT
```

The system doesn't blindly run one predefined test. It reasons about what to test, how much load to generate, when more testing is warranted, what anomalies appear, and what experiment would validate or reject a hypothesis about their cause. See [docs/architecture/data-flow.md](docs/architecture/data-flow.md) for the full loop.

## Multi-agent architecture

One **Performance Orchestrator** coordinates four specialized agents. This is a deterministic, orchestrated pipeline — not an autonomous agent swarm. See [ADR-002](docs/decisions/ADR-002-multi-agent-architecture.md) for why.

```text
                    ┌───────────────────────┐
                    │ Performance           │
                    │ Orchestrator          │
                    └──────────┬────────────┘
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
       Test Planner      Load Engineer     Performance
          Agent             Agent           Investigator
                                               Agent
             │                 │                 │
             └─────────────────┼─────────────────┘
                               │
                               ▼
                      Reporting Agent
```

| Agent | Role | Contract |
|---|---|---|
| Performance Orchestrator | Owns investigation state, sequences the other agents, decides when the investigation is done | [docs/agents/orchestrator.md](docs/agents/orchestrator.md) |
| Test Planner Agent | Turns app info + expected traffic into a structured test plan | [docs/agents/test-planner.md](docs/agents/test-planner.md) |
| Load Engineer Agent | Turns an approved test plan into an executable k6 script, runs it, collects metrics | [docs/agents/load-engineer.md](docs/agents/load-engineer.md) |
| Performance Investigator Agent | Turns metrics into observations, hypotheses, evidence and confidence — never speculation presented as fact | [docs/agents/performance-investigator.md](docs/agents/performance-investigator.md) |
| Reporting & Recommendation Agent | Turns the full investigation into an executive report with actionable recommendations | [docs/agents/reporting-agent.md](docs/agents/reporting-agent.md) |

Full architecture: [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md) and [docs/architecture/agent-architecture.md](docs/architecture/agent-architecture.md).

## Why this is hard to fake

Two rules run through the whole design:

1. **AI reasons, code calculates.** Percentages, thresholds, pass/fail, regressions — all computed in Python from k6's raw output. The AI interprets already-validated numbers; it never becomes the source of truth for them. See [docs/architecture/system-architecture.md#ai-output-reliability](docs/architecture/system-architecture.md).
2. **Structured contracts, not prose.** Agents pass typed objects to each other (defined in `packages/schemas`), not free-text summaries. This is what lets four developers build the agents in parallel without waiting on each other's prompt output format.

## Technology stack

| Layer | Choice |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui, Recharts |
| Backend | Python, FastAPI, Pydantic |
| Load generation | k6 (execution engine — PerfPilot does not build its own) |
| AI | Provider-abstracted (`AIService` → Gemini / DeepSeek / future providers) |
| Database | PostgreSQL |
| Background jobs | Celery + Redis |
| Containerization | Docker |

Rationale for each choice is in [ADR-001](docs/decisions/ADR-001-tech-stack.md).

## Repository structure

```text
perfpilot/
├── apps/
│   ├── web/          # Next.js dashboard (Developer 4/Thato)
│   └── api/           # FastAPI backend (Developer 3/Kamogelo)
├── agents/
│   ├── orchestrator/               # Developer 1/Thatayaone
│   ├── test-planner/               # Developer 1/Thatayaone
│   ├── load-engineer/              # Developer 2/Govenor
│   ├── performance-investigator/   # Developer 1/Thatayaone
│   └── reporting/                  # Developer 4/Thato
├── packages/
│   ├── schemas/       # Shared contracts — Pydantic + TS types (Developer 3/Kamogelo, jointly used by all)
│   ├── ai/            # AI provider abstraction (Developer 1/Thatayaone)
│   ├── metrics/       # Deterministic metrics/threshold calculations (Developer 2/Govenor)
│   └── common/        # Cross-cutting utilities (jointly owned, PR review required)
├── tests/
├── docs/               # Architecture, agent contracts, API, DB, security, workflow, ADRs
├── infrastructure/
│   ├── docker/         # Container definitions (frontend, backend, db, redis, k6 runner)
│   └── deployment/
├── .env.example
├── README.md
└── CONTRIBUTING.md
```

Full rationale for this layout — in particular why it's optimized for four people working without stepping on each other — is in [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md).

## Documentation index

| Area | Document |
|---|---|
| System architecture | [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md) |
| Multi-agent architecture | [docs/architecture/agent-architecture.md](docs/architecture/agent-architecture.md) |
| Investigation data flow | [docs/architecture/data-flow.md](docs/architecture/data-flow.md) |
| Agent contracts | [docs/agents/](docs/agents/) |
| API contract | [docs/api/api-contract.md](docs/api/api-contract.md) |
| Database design | [docs/database/database-design.md](docs/database/database-design.md) |
| Security model | [docs/security/security-model.md](docs/security/security-model.md) |
| Local development | [docs/development/local-development.md](docs/development/local-development.md) |
| Team workflow & ownership | [docs/development/team-workflow.md](docs/development/team-workflow.md) |
| Team roles (Team Lead, PM, Reviewer, Reporter) | [docs/development/team-roles.md](docs/development/team-roles.md) |
| Phase 1 next steps (per developer) | [docs/development/next-steps.md](docs/development/next-steps.md) |
| Coding standards & AI-assisted workflow rules | [docs/development/coding-standards.md](docs/development/coding-standards.md) |
| Task board (status per task) | [GitHub Issues](https://github.com/thato899/perfpilot/issues) |
| Testing strategy | [docs/testing/testing-strategy.md](docs/testing/testing-strategy.md) |
| Architecture Decision Records | [docs/decisions/](docs/decisions/) |
| Demo scenario | [docs/demo-scenario.md](docs/demo-scenario.md) |
| Implementation roadmap | [docs/roadmap.md](docs/roadmap.md) |

## The team

Four developers, four independent surfaces, one set of shared contracts in `packages/schemas` and `docs/`. See [docs/development/team-workflow.md](docs/development/team-workflow.md) for the full ownership map, branching model, and how to propose a contract change without blocking everyone else.

## MVP scope

The hackathon demo proves the full loop once, end-to-end, against a controlled target the team owns — it does not try to cover every test type or every possible bottleneck class. See [docs/roadmap.md](docs/roadmap.md) for what's in Phase 1 and what's explicitly deferred, and [docs/demo-scenario.md](docs/demo-scenario.md) for the reference scenario the whole system is designed around.

## Phase 0 definition of done

- [x] README explains the product
- [x] Architecture is documented
- [x] Multi-agent architecture is documented
- [x] Each agent has a clear responsibility
- [x] Agent contracts are documented
- [x] Technology stack is documented
- [x] Repository structure is defined
- [x] API contracts are documented
- [x] Database entities are documented
- [x] Security model is documented
- [x] Testing strategy is documented
- [x] Git workflow is documented
- [x] Four-person team ownership is documented
- [x] ADRs explain major architectural decisions
- [x] MVP scope is defined
- [x] Demo scenario is defined
- [x] No unnecessary application implementation has been started

No implementation begins until this documentation is reviewed and the team agrees the contracts in `packages/schemas` are stable enough to build against.
