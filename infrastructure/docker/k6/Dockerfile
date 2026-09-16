# Local k6 runner for the PerfPilot demo stack.
#
# This file is intentionally version-pinned so the repo does not rely on the
# latest upstream `grafana/k6` tag. It is the Govenor-owned runtime for the
# `k6-runner` service defined in infrastructure/docker/docker-compose.yml.

FROM grafana/k6:0.57.0

# Expose a known results directory for the worker to read raw summary exports.
WORKDIR /results

# Keep the entrypoint simple and inspectable: print the k6 version when the
# container starts, then stay alive for worker-triggered `docker compose exec`.
ENTRYPOINT ["sh", "-c", "k6 version && tail -f /dev/null"]
