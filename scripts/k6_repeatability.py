#!/usr/bin/env python3
"""Run the local k6 repeatability harness outside the investigation loop.

Evidence is written under the gitignored k6 results directory. The command
refuses to start unless the operator confirms the target is team-owned and
allow-listed. See docs/phase3/p3-metrics-1-run-noise.md.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT = ROOT / "infrastructure" / "docker" / "k6" / "results" / "repeatability"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-url", required=True, help="Authorized local target base URL")
    parser.add_argument(
        "--authorization-confirmed",
        action="store_true",
        help="Confirm this target is team-owned and approved for these trials",
    )
    parser.add_argument("--allowed-hosts", default="localhost,demo.perfpilot.local")
    parser.add_argument("--journey", default="/health")
    parser.add_argument("--vus", type=int, default=2)
    parser.add_argument("--duration-seconds", type=int, default=5)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--max-virtual-users", type=int, default=5000)
    parser.add_argument("--max-duration-seconds", type=int, default=1800)
    parser.add_argument("--k6-binary", default="k6")
    parser.add_argument("--target-build", default="local-unspecified")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    harness = _load_harness()
    try:
        plan = harness.controlled_plan(
            virtual_users=args.vus,
            duration_seconds=args.duration_seconds,
            journey=args.journey,
        )
        report = harness.execute_repeatability(
            harness.HarnessConfig(
                plan=plan,
                target=harness_target(args.target_url),
                allowed_hosts=_hosts(args.allowed_hosts),
                max_virtual_users=args.max_virtual_users,
                max_test_duration_seconds=args.max_duration_seconds,
                trial_count=args.trials,
                target_build=args.target_build,
                output_dir=args.output_dir,
                k6_binary=args.k6_binary,
                authorization_confirmed=args.authorization_confirmed,
            )
        )
    except harness.RepeatabilityConfigError as error:
        print(f"repeatability harness refused to run: {error}", file=sys.stderr)
        return 1

    print(f"scenario: {report.scenario_fingerprint}")
    print(f"valid trials: {report.valid_count}; invalid trials: {report.invalid_count}")
    for span in report.ranges:
        print(f"{span.name}: min {span.minimum} max {span.maximum} span {span.span}")
    print(report.recommendation)
    print(f"report: {(args.output_dir / 'repeatability-report.json').as_posix()}")
    return 0 if report.valid_count else 2


def harness_target(base_url: str):
    from packages.schemas.python.agent_io import TargetRef

    return TargetRef(base_url=base_url)


def _hosts(raw: str) -> frozenset[str]:
    return frozenset(host.strip().lower() for host in raw.split(",") if host.strip())


def _load_harness():
    path = ROOT / "agents" / "load-engineer" / "repeatability.py"
    spec = importlib.util.spec_from_file_location("perfpilot_k6_repeatability_cli", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("repeatability harness is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    raise SystemExit(main())
