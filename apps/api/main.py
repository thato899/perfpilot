"""FastAPI application entry point.

BOOT SCAFFOLDING ONLY. This module exists so the `api` service in
infrastructure/docker/docker-compose.yml has a real application to start
(issue #10) — a compose file whose services can't come up isn't wiring, it's
a wish list.

The Phase 1 endpoints in docs/api/api-contract.md (projects, targets, test
plan/run, investigation create/get) are issue #12 and are deliberately NOT
implemented here. Add them as routers on this `app`.

`/health` is not part of api-contract.md's resource surface — it's an
infrastructure probe: docker-compose.yml's healthcheck and render.yaml's
`healthCheckPath` both depend on it, which is why it's documented in
api-contract.md under "Operational endpoints" rather than left undeclared.
"""

from fastapi import FastAPI

app = FastAPI(
    title="PerfPilot API",
    version="0.1.0",
    description="AI-driven performance testing and investigation platform.",
)


@app.get("/health", tags=["operational"])
def health() -> dict[str, str]:
    """Liveness probe.

    Deliberately shallow: it reports that the process is up and serving, and
    checks nothing downstream. Compose already gates `api` on `db` and
    `redis` being healthy via their own healthchecks, so re-checking them
    here would report someone else's outage as this service being unhealthy
    and trigger restarts that fix nothing.
    """
    return {"status": "ok"}
