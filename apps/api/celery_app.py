"""Celery application.

BOOT SCAFFOLDING ONLY. This module exists so the `worker` service in
infrastructure/docker/docker-compose.yml has a real Celery app to start
(issue #10), and so the broker/result-backend wiring is provably correct
before any real task depends on it.

Actual async test execution is issue #13, and the task it dispatches is
Govenor's k6 execution wrapper (agents/load-engineer). Neither is
implemented here.

Module path note: this is `apps.api.celery_app`, not `app.celery_app` as
render.yaml's TODO currently guesses. The repo is imported root-relative
(pyproject.toml's `pythonpath = ["."]`) because apps/api imports
packages.schemas — so render.yaml's `rootDir: apps/api` would break those
imports. Flagged for whoever activates render.yaml; not changed here, since
that file is a shared root path and activating it is separate work.
"""

import os

from celery import Celery

celery_app = Celery(
    "perfpilot",
    # Defaults match .env.example's host-side values, so this is importable
    # outside a container (e.g. `celery ... inspect` from a developer's
    # shell) without every variable already exported.
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
)

celery_app.conf.update(
    task_track_started=True,
    # Load tests run for minutes, not seconds — Celery's default prefetch of
    # 4 would let one worker claim several long jobs and sit on them. One at
    # a time is the right shape for this workload.
    worker_prefetch_multiplier=1,
    # Accept only JSON: a broker message is untrusted input, and pickle
    # deserialization is remote code execution.
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
)


@celery_app.task(name="perfpilot.ping")
def ping() -> str:
    """Smoke-test task — proves broker and result backend round-trip.

    Verify the wiring end to end with:

        docker compose --profile backend exec api \\
            python -c "from apps.api.celery_app import ping; \\
                       print(ping.delay().get(timeout=10))"

    Expected output: pong. Replace this with real work in issue #13; it is
    safe to delete once a genuine task exercises the same path.
    """
    return "pong"
