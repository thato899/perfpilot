# apps/web

Next.js + TypeScript + Tailwind CSS + shadcn/ui dashboard for the PerfPilot
Phase 1 investigation API.

## Production path

The browser uses `src/lib/api.ts`, which calls same-origin
`/api/perfpilot/*` routes. The catch-all Next route handler forwards those
requests to the configured FastAPI `API_BASE_URL` and adds the server-only
`API_AUTH_SECRET` bearer token. The secret is never placed in browser code or
`NEXT_PUBLIC_*` configuration.

The dashboard creates or loads a project, registers an explicitly authorized
target, creates an investigation, polls persisted investigation/test-run
state, and renders backend Findings, Hypotheses, and Report values. It does not
recompute metrics, confidence, capacity, or regression values.

The API has no target-list endpoint, so targets returned by FastAPI are cached
locally only to let the dashboard select them after a refresh. The cached
records are not used as investigation or report data; those always come from
FastAPI.

## Current backend boundary

The merged backend currently exposes investigation creation and read/continue
routes, but does not yet expose the initial plan/run-to-investigation link or a
worker continuation trigger that can take a newly created investigation all
the way to persisted Findings and Report data. The UI therefore polls the
actual state, stops at terminal states, surfaces failures, and shows an
explicit waiting message while that backend gap remains. It never advances a
mock tick or falls back to fixture success data in production.

## Test and fixture separation

`src/lib/mock-api.ts` and `src/lib/fixtures.ts` remain for fast unit tests and
are not imported by the production pages or dashboard forms. Production API
request/response mapping is tested in `src/lib/__tests__/api.test.ts`, and
polling terminal/error boundaries are tested in
`src/lib/__tests__/polling.test.ts`.

Run the frontend checks from the repository root:

```text
pnpm --filter web test
pnpm --filter web lint
pnpm --filter web exec tsc --noEmit
pnpm run format:check
pnpm --filter web build
```

The FastAPI contract is documented in
[`docs/api/api-contract.md`](../../docs/api/api-contract.md). Configure
`API_BASE_URL` and `API_AUTH_SECRET` for the Next server. A project id may be
provided as `NEXT_PUBLIC_PERFPILOT_PROJECT_ID`; it is an identifier, not a
credential.
