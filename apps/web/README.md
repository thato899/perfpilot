# apps/web

**Owner:** Developer 4 (Frontend / Reporting)

Next.js + TypeScript + Tailwind CSS + shadcn/ui dashboard: project/target management, investigation progress, findings, and final reports.

Not implemented yet — this is Phase 1 work. Build against:

- [docs/api/api-contract.md](../../docs/api/api-contract.md) — every endpoint this app calls
- `packages/schemas/typescript/types.ts` — the exact shapes those endpoints return
- [docs/architecture/data-flow.md](../../docs/architecture/data-flow.md) — what an in-progress investigation looks like, for the live progress view
- [docs/demo-scenario.md](../../docs/demo-scenario.md) — the reference walkthrough the UI needs to support end to end

This app never calls an agent or k6 directly — only `apps/api`, per [system-architecture.md](../../docs/architecture/system-architecture.md#layering-rules).
