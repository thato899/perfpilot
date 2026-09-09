# packages/schemas

**Owner:** Developer 3/Kamogelo (canonical), consumed by everyone.

This package is the single source of truth for every structured object that crosses a boundary in PerfPilot: database entities, agent inputs/outputs, and API request/response bodies. It exists so that four people can build four different parts of the system against an agreed shape instead of a shared understanding that quietly drifts.

## Layout

```text
packages/schemas/
├── python/
│   ├── entities.py   # Database-backed entities — mirrors docs/database/database-design.md
│   └── agent_io.py   # Agent input/output contracts + InvestigationState — mirrors docs/agents/*.md
└── typescript/
    └── types.ts       # Frontend-facing mirror of the entities/state the dashboard renders
```

These files are **type/contract definitions only** — field names, types, enums, and doc-comments pointing back to the authoritative prose contract in `docs/`. They intentionally contain no business logic (no validators beyond basic shape, no calculations); that belongs in `apps/api`, the individual `agents/*`, and `packages/metrics` once implementation starts.

## Rules

1. **`docs/agents/*.md` and `docs/database/database-design.md` are the prose source of truth.** These files are the typed mirror. If they disagree, the docs win until someone deliberately updates both together.
2. **Python and TypeScript must not drift.** A field added to `agent_io.py` needs the matching field added to `types.ts` in the same change (see [CONTRIBUTING.md](../../CONTRIBUTING.md#changing-a-shared-contract)).
3. **Changing a shape here is a cross-team event, not a local edit.** See [CONTRIBUTING.md](../../CONTRIBUTING.md#changing-a-shared-contract) for the process.
4. **No provider-specific or framework-specific types leak in here.** These are plain Pydantic models / plain TS interfaces — no FastAPI-specific types, no ORM base classes, no React types. That's what keeps this package importable from `apps/api`, every `agents/*`, and `apps/web` alike without pulling in each other's dependencies.
