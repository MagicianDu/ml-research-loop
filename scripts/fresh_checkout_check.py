#!/usr/bin/env python3
"""Validate a fresh public checkout of ml-research-loop."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


DEFAULT_REPO_URL = "https://github.com/MagicianDu/ml-research-loop.git"


@dataclass(frozen=True)
class FreshCommand:
    label: str
    argv: list[str]
    cwd: Path
    timeout_seconds: int


@dataclass(frozen=True)
class FreshResult:
    label: str
    returncode: int
    duration_seconds: float
    stdout: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a fresh public checkout")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--ref", default="main")
    parser.add_argument("--workdir", type=Path, default=None)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--keep-workdir", action="store_true")
    parser.add_argument(
        "--skip-golden-path",
        action="store_true",
        help="Skip the bounded MCP golden-path demo.",
    )
    parser.add_argument(
        "--skip-full-release-check",
        action="store_true",
        help="Reserved for launch scripts; this verifier already runs the shorter fresh-check path.",
    )
    return parser.parse_args()


def make_workdir(workdir: Path | None) -> Path:
    if workdir is not None:
        root = workdir.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root
    return Path(tempfile.gettempdir()) / f"ml-research-loop-fresh-{uuid.uuid4().hex[:8]}"


def build_commands(
    *,
    repo_url: str,
    ref: str,
    python: str,
    workdir: Path,
    skip_golden_path: bool,
) -> tuple[Path, list[FreshCommand]]:
    checkout = workdir / "ml-research-loop"
    venv_python = checkout / ".venv" / "bin" / "python"
    ml_loop = checkout / ".venv" / "bin" / "ml-loop"
    runtime_root = checkout / ".fresh-check" / "runtime"
    skill_root = checkout / ".fresh-check" / "skills"
    commands = [
        FreshCommand(
            label="git-clone",
            argv=["git", "clone", "--depth", "1", "--branch", ref, repo_url, str(checkout)],
            cwd=workdir,
            timeout_seconds=120,
        ),
        FreshCommand(
            label="create-venv",
            argv=[python, "-m", "venv", ".venv"],
            cwd=checkout,
            timeout_seconds=120,
        ),
        FreshCommand(
            label="install",
            argv=[str(venv_python), "-m", "pip", "install", "-e", ".[dev]"],
            cwd=checkout,
            timeout_seconds=900,
        ),
        FreshCommand(
            label="mcp-client-acceptance",
            argv=[
                str(venv_python),
                "scripts/mcp_client_acceptance.py",
                "--python",
                str(venv_python),
                "--project-root",
                str(checkout),
            ],
            cwd=checkout,
            timeout_seconds=60,
        ),
        FreshCommand(
            label="render-codex-config",
            argv=[
                str(ml_loop),
                "init-mcp-config",
                "--client",
                "codex",
                "--project-root",
                str(checkout),
                "--python",
                str(venv_python),
            ],
            cwd=checkout,
            timeout_seconds=30,
        ),
        FreshCommand(
            label="skills-dry-run",
            argv=[
                str(ml_loop),
                "init-skills",
                "--client",
                "codex",
                "--project-root",
                str(checkout),
                "--target-root",
                str(skill_root),
                "--dry-run",
            ],
            cwd=checkout,
            timeout_seconds=30,
        ),
    ]
    if not skip_golden_path:
        commands.append(
            FreshCommand(
                label="mcp-golden-path",
                argv=[
                    str(venv_python),
                    "scripts/mcp_golden_path.py",
                    "--runtime-root",
                    str(runtime_root),
                    "--max-experiments",
                    "1",
                    "--experiment-duration",
                    "30",
                ],
                cwd=checkout,
                timeout_seconds=180,
            )
        )
    return checkout, commands


def run_command(command: FreshCommand) -> FreshResult:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command.argv,
            cwd=command.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=command.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _timeout_stdout(command=command, exc=exc)
        return FreshResult(
            label=command.label,
            returncode=124,
            duration_seconds=round(time.monotonic() - start, 3),
            stdout=stdout,
        )
    return FreshResult(
        label=command.label,
        returncode=proc.returncode,
        duration_seconds=round(time.monotonic() - start, 3),
        stdout=proc.stdout,
    )


def _timeout_stdout(command: FreshCommand, exc: subprocess.TimeoutExpired) -> str:
    captured = exc.stdout or exc.output or ""
    if isinstance(captured, bytes):
        captured = captured.decode("utf-8", errors="replace")
    timeout = exc.timeout or command.timeout_seconds
    return "\n".join([
        f"{command.label} timed out after {timeout:g} seconds.",
        f"Command: {' '.join(command.argv)}",
        str(captured),
    ]).strip()


def render_summary(
    *,
    repo_url: str,
    ref: str,
    checkout: Path,
    results: list[FreshResult],
) -> str:
    payload = {
        "status": "passed" if all(result.returncode == 0 for result in results) else "failed",
        "repo_url": repo_url,
        "ref": ref,
        "checkout": str(checkout),
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


def main() -> int:
    args = parse_args()
    workdir = make_workdir(args.workdir)
    workdir.mkdir(parents=True)
    checkout, commands = build_commands(
        repo_url=args.repo_url,
        ref=args.ref,
        python=args.python,
        workdir=workdir,
        skip_golden_path=args.skip_golden_path,
    )
    if checkout.exists():
        shutil.rmtree(checkout)
    results: list[FreshResult] = []
    try:
        for command in commands:
            result = run_command(command)
            results.append(result)
            if result.returncode != 0:
                break
        print(render_summary(repo_url=args.repo_url, ref=args.ref, checkout=checkout, results=results))
        return 0 if all(result.returncode == 0 for result in results) else 1
    finally:
        if args.workdir is None and not args.keep_workdir and workdir.exists():
            shutil.rmtree(workdir)


if __name__ == "__main__":
    raise SystemExit(main())
