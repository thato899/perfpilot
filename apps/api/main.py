"""FastAPI application entry point.

Wires the routers in docs/api/api-contract.md onto one app, plus the error
handlers that give every failure the contract's documented envelope.

The HTTP layer owns request/response validation, auth and persistence. It
does not own what happens *inside* a planning or continuation call beyond
invoking the Orchestrator and storing what comes back — that reasoning is
Developer 1/Thatayaone's (api-contract.md#ownership-note). Today the
Orchestrator is a stub; see apps/api/orchestrator_stub.py.
"""

from __future__ import annotations

from fastapi import FastAPI

from .errors import install_error_handlers
from .routers import investigations, projects, tests_

app = FastAPI(
    title="PerfPilot API",
    version="0.1.0",
    description="AI-driven performance testing and investigation platform.",
)

install_error_handlers(app)

app.include_router(projects.router)
app.include_router(tests_.router)
app.include_router(investigations.router)


@app.get("/health", tags=["operational"])
def health() -> dict[str, str]:
    """Liveness probe. Unauthenticated, by design.

    Consumed by docker-compose.yml's healthcheck and render.yaml's
    healthCheckPath — a probe that needed a bearer token couldn't be used by
    an orchestrator that doesn't have one.

    Deliberately shallow: it reports that the process is serving and checks
    nothing downstream. Compose already gates `api` on `db` and `redis`
    passing their own healthchecks, so re-checking them here would report
    someone else's outage as this service being unhealthy and trigger
    restarts that fix nothing.
    """
    return {"status": "ok"}
