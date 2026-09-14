# Image for both the `api` and `worker` services — same codebase, different
# command, per docs/development/local-development.md's planned layout.
#
# The build context is the REPOSITORY ROOT, not this directory, because
# apps/api imports packages/schemas as `packages.schemas.python.entities`
# (repo-root-relative, the same convention pyproject.toml's
# `pythonpath = ["."]` sets for pytest). The container mirrors the repo
# layout so those imports resolve identically in Docker, in CI, and on a
# developer's machine.

FROM python:3.11-slim

# PYTHONDONTWRITEBYTECODE: the source tree is bind-mounted from the host in
# development, and .pyc files written into it would be owned by root.
# PYTHONUNBUFFERED: without it, uvicorn/celery logs sit in a buffer and
# `docker compose logs` looks hung.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Dependencies first, in their own layer: application code changes far more
# often than the dependency list, so this keeps rebuilds cheap.
COPY apps/api/requirements.txt apps/api/requirements.txt
RUN pip install --no-cache-dir -r apps/api/requirements.txt

COPY pyproject.toml ./
COPY packages ./packages
COPY agents ./agents
COPY apps/api ./apps/api

# Created here, before the chown below, on purpose: docker-compose.yml
# bind-mounts the k6 results directory to this path, and Docker creates a
# missing mount point as root — which the non-root user below then can't
# write into. Creating it first means the worker can actually write results
# when issue #13 wires execution up.
RUN mkdir -p /app/infrastructure/docker/k6/results

# Non-root by default. The bind mounts in docker-compose.yml are read-write
# for this user on Docker Desktop; on Linux, a developer whose UID isn't 1000
# may need to adjust, which is why this is a single line to comment out
# rather than a baked-in assumption.
RUN useradd --create-home --uid 1000 perfpilot && chown -R perfpilot:perfpilot /app
USER perfpilot

EXPOSE 8000

# Overridden per service in docker-compose.yml (uvicorn for `api`, celery for
# `worker`). This default is the API, so `docker run` on the image alone does
# something sensible.
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
