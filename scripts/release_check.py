#!/usr/bin/env python3
"""Run release verification without relying on make."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ReleaseCommand:
    label: str
    argv: list[str]
    timeout_seconds: int


@dataclass(frozen=True)
class CheckResult:
    label: str
    returncode: int
    duration_seconds: float
    stdout: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ml-research-loop release checks")
    parser.add_argument("--python", default=sys.executable, help="Python executable to use")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--skip-golden-path", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print only final JSON summary")
    return parser.parse_args()


def build_release_commands(
    python: str,
    project_root: Path,
    skip_golden_path: bool = False,
) -> list[ReleaseCommand]:
    ruff = project_root / ".venv" / "bin" / "ruff"
    ruff_executable = str(ruff) if ruff.exists() else "ruff"
    commands = [
        ReleaseCommand(
            label="ruff",
            argv=[
                ruff_executable,
                "check",
                "lib/",
                "scripts/",
                "ml_intern/",
                "codex_plugin/",
                "tests/",
            ],
            timeout_seconds=120,
        ),
        ReleaseCommand(
            label="pytest",
            argv=[python, "-m", "pytest", "tests/", "-q"],
            timeout_seconds=240,
        ),
        ReleaseCommand(
            label="mcp-stdio-smoke",
            argv=[python, str(project_root / "scripts" / "mcp_server.py")],
            timeout_seconds=15,
        ),
    ]
    if not skip_golden_path:
        runtime_root = project_root / ".demo_runs" / f"release-check-{uuid.uuid4().hex[:8]}"
        multi_round_runtime_root = (
            project_root / ".demo_runs" / f"release-check-multi-{uuid.uuid4().hex[:8]}"
        )
        commands.append(
            ReleaseCommand(
                label="mcp-golden-path",
                argv=[
                    python,
                    str(project_root / "scripts" / "mcp_golden_path.py"),
                    "--runtime-root",
                    str(runtime_root),
                    "--max-experiments",
                    "1",
                    "--experiment-duration",
                    "30",
                ],
                timeout_seconds=120,
            )
        )
        commands.append(
            ReleaseCommand(
                label="mcp-multi-round",
                argv=[
                    python,
                    str(project_root / "scripts" / "mcp_multi_round_demo.py"),
                    "--runtime-root",
                    str(multi_round_runtime_root),
                    "--rounds",
                    "2",
                    "--max-experiments",
                    "1",
                    "--experiment-duration",
                    "30",
                ],
                timeout_seconds=180,
            )
        )
    return commands


def run_command(command: ReleaseCommand, project_root: Path, env: dict[str, str]) -> CheckResult:
    start = time.monotonic()
    if command.label == "mcp-stdio-smoke":
        proc = subprocess.run(
            command.argv,
            input=_mcp_smoke_input(),
            cwd=project_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=command.timeout_seconds,
        )
    else:
        proc = subprocess.run(
            command.argv,
            cwd=project_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=command.timeout_seconds,
        )
    return CheckResult(
        label=command.label,
        returncode=proc.returncode,
        duration_seconds=round(time.monotonic() - start, 3),
        stdout=proc.stdout,
    )


def render_summary(results: list[CheckResult]) -> str:
    payload = {
        "status": "passed" if all(result.returncode == 0 for result in results) else "failed",
        "checks": [
            {
                "label": result.label,
                "returncode": result.returncode,
                "duration_seconds": result.duration_seconds,
                "stdout_tail": "\n".join(result.stdout.splitlines()[-20:]),
            }
            for result in results
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def release_env(project_root: Path, python: str) -> dict[str, str]:
    env = dict(os.environ)
    pythonpath_parts = [str(project_root)]
    pythonpath_parts.extend(str(path) for path in _site_packages_paths(project_root))
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    env["ML_RESEARCH_LOOP_PYTHON"] = env.get("ML_RESEARCH_LOOP_PYTHON", python)
    return env


def _site_packages_paths(project_root: Path) -> list[Path]:
    site_packages_root = project_root / ".venv" / "lib"
    if not site_packages_root.exists():
        return []
    return sorted(site_packages_root.glob("python*/site-packages"))


def _mcp_smoke_input() -> str:
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    return "\n".join(json.dumps(request) for request in requests) + "\n"


def main() -> int:
    args = parse_args()
    project_root = args.project_root.expanduser().resolve()
    env = release_env(project_root, args.python)
    results: list[CheckResult] = []

    for command in build_release_commands(args.python, project_root, args.skip_golden_path):
        if not args.json:
            print(f"[release-check] {command.label}: {' '.join(command.argv)}", flush=True)
        result = run_command(command, project_root, env)
        results.append(result)
        if not args.json:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.returncode != 0:
            break

    print(render_summary(results))
    return 0 if all(result.returncode == 0 for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
