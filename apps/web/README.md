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
state, and renders backend Findings, Hypotheses, and Report values. The result
page separates deterministic measurement observations from AI interpretation,
supports multiple hypotheses per finding, and displays persisted evidence,
experiment state, and experiment budget. It does not recompute metrics,
confidence, capacity, regression values, or budget state.

The API has no target-list endpoint, so targets returned by FastAPI are cached
locally only to let the dashboard select them after a refresh. The cached
records are not used as investigation or report data; those always come from
FastAPI.

## Verified backend boundary

The merged backend creates a real investigation, queues and executes a real
TestRun through Celery/k6, persists Findings and a Report, and exposes the
state consumed by the result page. The UI polls persisted state, handles
planning/running/investigating/reporting transitions, stops at terminal states,
and surfaces bounded API failures. It never advances a mock tick or falls back
to fixture success data in production.

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
