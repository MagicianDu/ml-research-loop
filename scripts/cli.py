"""Command-line interface for ml-research-loop."""

from __future__ import annotations

import argparse
import json
import subprocess

from lib import mcp_service
from lib.runtime import resolve_python_executable
from lib.task_protocol import WORKSPACE_ROOT
from ml_intern.autoresearch_manager import AutoResearchManager


def build_parser() -> argparse.ArgumentParser:
    """Build the ml-loop argument parser."""
    parser = argparse.ArgumentParser(prog="ml-loop")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser("run", help="Run an autoresearch task config")
    run.add_argument("--task-config", required=True)
    run.add_argument("--workspace")
    run.add_argument("--max-experiments", type=int)
    run.add_argument("--max-duration", type=int)
    run.add_argument("--experiment-duration", type=int, default=300)
    run.add_argument("--ai", action="store_true")
    run.add_argument("--mock", action="store_true")
    run.add_argument("--verbose", action="store_true")

    status = subcommands.add_parser("status", help="Read task progress")
    status.add_argument("task_id")

    result = subcommands.add_parser("result", help="Read task result")
    result.add_argument("task_id")

    check = subcommands.add_parser("check", help="Run MCP/product readiness checks")
    check.add_argument("--python", default=resolve_python_executable(WORKSPACE_ROOT))
    check.add_argument("--skip-demos", action="store_true")
    check.add_argument("--json", action="store_true")

    artifacts = subcommands.add_parser("artifacts", help="Manage runtime artifacts")
    artifact_commands = artifacts.add_subparsers(dest="artifact_command", required=True)
    artifacts_list = artifact_commands.add_parser("list", help="List runtime artifacts")
    artifacts_list.add_argument("--runtime-root", required=True)
    artifacts_archive = artifact_commands.add_parser("archive", help="Archive one task's artifacts")
    artifacts_archive.add_argument("--runtime-root", required=True)
    artifacts_archive.add_argument("--task-id", required=True)
    artifacts_clean = artifact_commands.add_parser("clean", help="Delete one task's artifacts")
    artifacts_clean.add_argument("--runtime-root", required=True)
    artifacts_clean.add_argument("--task-id", required=True)
    artifacts_clean.add_argument("--confirm", action="store_true")

    return parser


def _run_task(args: argparse.Namespace) -> int:
    script = "ai_autoresearch_run.py" if args.ai else "autoresearch_run.py"
    cmd = [
        resolve_python_executable(WORKSPACE_ROOT),
        str(WORKSPACE_ROOT / "scripts" / script),
        "--task-config",
        args.task_config,
        "--experiment-duration",
        str(args.experiment_duration),
    ]
    if args.workspace:
        cmd.extend(["--workspace", args.workspace])
    if args.max_experiments is not None:
        cmd.extend(["--max-experiments", str(args.max_experiments)])
    if args.max_duration is not None:
        cmd.extend(["--max-duration", str(args.max_duration)])
    if args.ai and args.mock:
        cmd.append("--mock")
    if args.verbose:
        cmd.append("--verbose")

    return subprocess.call(cmd, cwd=str(WORKSPACE_ROOT))


def _run_check(args: argparse.Namespace) -> int:
    cmd = [
        resolve_python_executable(WORKSPACE_ROOT),
        str(WORKSPACE_ROOT / "scripts" / "release_check.py"),
        "--python",
        args.python,
    ]
    if args.skip_demos:
        cmd.append("--skip-golden-path")
    if args.json:
        cmd.append("--json")
    return subprocess.call(cmd, cwd=str(WORKSPACE_ROOT))


def _run_artifacts(args: argparse.Namespace) -> int:
    arguments = {"runtime_root": args.runtime_root}
    if args.artifact_command == "list":
        payload = mcp_service.list_runtime_artifacts_tool(arguments)
    elif args.artifact_command == "archive":
        payload = mcp_service.archive_runtime_artifacts_tool({
            **arguments,
            "task_id": args.task_id,
        })
    elif args.artifact_command == "clean":
        payload = mcp_service.clean_runtime_artifacts_tool({
            **arguments,
            "task_id": args.task_id,
            "confirm": args.confirm,
        })
    else:
        return 2
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    args = build_parser().parse_args(argv)
    manager = AutoResearchManager()

    if args.command == "run":
        return _run_task(args)
    if args.command == "check":
        return _run_check(args)
    if args.command == "artifacts":
        return _run_artifacts(args)
    if args.command == "status":
        print(json.dumps(manager.get_status(args.task_id), indent=2, ensure_ascii=False))
        return 0
    if args.command == "result":
        result = manager.get_result(args.task_id)
        payload = result.to_dict() if result is not None else {
            "task_id": args.task_id,
            "status": "not_ready",
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
