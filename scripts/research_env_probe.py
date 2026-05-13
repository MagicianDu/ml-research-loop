#!/usr/bin/env python3
"""Probe research workspace readiness and print a repair plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.environment_probe import probe_research_environment  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe research workspace environment readiness")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--required-file", action="append", default=[])
    parser.add_argument("--required-command", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = probe_research_environment(
        workspace=args.workspace,
        required_files=args.required_file,
        required_commands=args.required_command,
    )

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        _print_status_lines(payload)
    return 0


def _print_status_lines(payload: dict[str, object]) -> None:
    print(f"status: {payload['status']}")
    print(f"workspace: {payload['workspace']}")
    print(f"missing_files: {len(payload['missing_files'])}")
    print(f"missing_commands: {len(payload['missing_commands'])}")
    print(f"secret_risk_files: {len(payload['secret_risk_files'])}")
    print(f"repair_plan: {len(payload['repair_plan'])} entries")


if __name__ == "__main__":
    raise SystemExit(main())
