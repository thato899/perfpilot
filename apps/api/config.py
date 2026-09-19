"""Runtime settings, read from the environment documented in .env.example.

Everything here is read once at import. The safety limits in particular are
deliberately *not* overridable per-request: security-model.md's rule is that
"the system's own configuration bounds how much load it can ever generate,
independent of what any test plan or agent requests".
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from urllib.parse import urlparse


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - misconfiguration
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _host_list(raw: str) -> frozenset[str]:
    return frozenset(h.strip().lower() for h in raw.split(",") if h.strip())


@dataclass(frozen=True)
class Settings:
    api_auth_secret: str
    allowed_target_hosts: frozenset[str] = field(default_factory=frozenset)
    max_virtual_users: int = 5000
    max_test_duration_seconds: int = 1800
    max_experiments_per_investigation: int = 3
    load_engineer_mode: str = "real"
    k6_binary_path: str = "k6"
    k6_results_dir: str = "./infrastructure/docker/k6/results"

    def host_is_allowed(self, base_url: str) -> bool:
        """Is `base_url`'s host on the allow-list?

        Compares the *host* only — port and path are irrelevant to whether
        we're permitted to point load at a machine, and including them would
        let `localhost:3000` pass while `localhost:8080` failed. A URL we
        can't parse a hostname out of is refused rather than allowed, so a
        malformed value fails closed.
        """
        host = urlparse(base_url).hostname
        if not host:
            return False
        return host.lower() in self.allowed_target_hosts


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        api_auth_secret=os.environ.get("API_AUTH_SECRET", ""),
        allowed_target_hosts=_host_list(
            os.environ.get("ALLOWED_TARGET_HOSTS", "localhost,demo.perfpilot.local")
        ),
        max_virtual_users=_int_env("MAX_VIRTUAL_USERS", 5000),
        max_test_duration_seconds=_int_env("MAX_TEST_DURATION_SECONDS", 1800),
        # Not in .env.example yet; orchestrator.md names it as the bound on
        # self-initiated follow-up experiments. Defaulted here rather than
        # added to .env.example, which is a shared root file.
        max_experiments_per_investigation=_int_env("MAX_EXPERIMENTS_PER_INVESTIGATION", 3),
        load_engineer_mode=os.environ.get("LOAD_ENGINEER_MODE", "real"),
        k6_binary_path=os.environ.get("K6_BINARY_PATH", "k6"),
        k6_results_dir=os.environ.get("K6_RESULTS_DIR", "./infrastructure/docker/k6/results"),
    )
