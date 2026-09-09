# Team Workflow & Ownership

Four developers, four largely independent surfaces. The split is designed so each person can build against the contracts in `packages/schemas` and `docs/` without waiting on another developer's in-progress code.

## Ownership map

| Developer | Owns | Responsibilities |
|---|---|---|
| **Developer 1/Thatayaone — AI / Orchestration** | `agents/orchestrator/`, `agents/test-planner/`, `agents/performance-investigator/`, `packages/ai/` | Orchestrator state machine and continuation policy; agent contracts; AI provider abstraction; prompts; structured-output validation for all four specialist agents' schemas |
| **Developer 2/Govenor — Performance Engine** | `agents/load-engineer/`, `packages/metrics/`, `infrastructure/docker/k6/` | k6 script generation; execution wrapper; safety-ceiling enforcement; raw-metric parsing; all deterministic metric/threshold/regression calculations |
| **Developer 3/Kamogelo — Backend / Data** | `apps/api/`, database migrations, `packages/schemas/` | FastAPI endpoints; auth; persistence; background job wiring (Celery); owns the canonical schema definitions everyone else builds against |
| **Developer 4/Thato — Frontend / Reporting** | `apps/web/`, `agents/reporting/` | Dashboard; charts; live test/investigation progress views; the Reporting Agent (report synthesis is presentation-adjacent, and pairs naturally with the person building the report's UI) |

### A gap we found and closed during architecture review

The original four-way split (orchestrator+planner / load-engineer / backend / frontend+reporting) didn't assign an owner to `agents/performance-investigator/`. Since it's the most reasoning-heavy, prompt-and-validation-heavy agent in the system — the same skill set as the orchestrator and test planner — it's assigned to **Developer 1/Thatayaone** rather than split off on its own or bolted onto a less-related surface. This does mean Developer 1/Thatayaone owns three agent folders instead of one or two; that's an accepted trade-off given `apps/web` is already a large surface for Developer 4/Thato on its own, and the three agents Developer 1/Thatayaone owns share the same underlying skill (structured-output prompting against `packages/ai`) rather than being three unrelated problems.

### Shared / jointly-owned paths

Not everything has exactly one owner. These require lightweight coordination (see [CONTRIBUTING.md](../../CONTRIBUTING.md#shared-paths--get-a-second-opinion-before-merging)):

- **`packages/schemas/`** — formally owned by Developer 3/Kamogelo (it's the backend's canonical contract layer), but every developer proposes changes to the slice they consume. No one edits another agent's input/output schema without that agent's owner signing off.
- **`packages/common/`** — cross-cutting utilities with no single owner; changes go through PR review from at least one other developer regardless of who wrote the diff.
- **`docs/`** — each doc is closest-owned by whoever owns the corresponding code (`docs/agents/orchestrator.md` → Developer 1/Thatayaone, `docs/api/api-contract.md` → Developer 3/Kamogelo, etc.), but architecture-level docs and ADRs are a team decision, proposed by whoever identifies the need and agreed by the group before merging.
- **Root config** (`docker-compose.yml` once it exists, CI config, `.env.example`) — touches everyone's local setup; flag changes before merging, per [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Git workflow

```text
main
  │
  └── develop
        │
        ├── feature/orchestrator
        ├── feature/k6-engine
        ├── feature/backend
        └── feature/dashboard
```

- `main` — always demo-ready. Only receives merges from `develop`.
- `develop` — integration branch. All feature work merges here first.
- `feature/*`, `fix/*`, `docs/*` — branch per unit of work, never work directly on `main` or `develop`.

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for commit message conventions, PR review expectations, and the process for changing a shared contract.

## How the contracts enable parallel work

Once this Phase 0 documentation is agreed:

- Developer 3/Kamogelo can build every `apps/api` endpoint against `packages/schemas` with the Orchestrator stubbed to return canned responses matching its documented output schema.
- Developer 1/Thatayaone can build and test each agent in isolation against its own input/output schema, using fixture inputs, without a working API or frontend.
- Developer 2/Govenor can build k6 generation and the metrics pipeline against a fixture `TestPlan` and recorded k6 output, without waiting on the Test Planner or Investigator to exist.
- Developer 4/Thato can build the dashboard against a mocked API returning fixture `InvestigationState`/`Report` payloads, and build the Reporting Agent against fixture `InvestigationState` input, without waiting on a real investigation ever having run.

This is the entire point of freezing `packages/schemas` and `docs/agents/*.md` before implementation starts — see [CONTRIBUTING.md](../../CONTRIBUTING.md#before-you-write-code).

## Communication

For a hackathon-length project: a short daily sync (even 10 minutes) covering (1) anything you changed in a shared path, (2) any contract you need changed, (3) anything blocking you on another owner's surface, is enough to keep four people from drifting out of sync — no heavier process than that is needed at this scale.
