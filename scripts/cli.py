"""Command-line interface for ml-research-loop."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

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

    init_config = subcommands.add_parser(
        "init-mcp-config",
        help="Render a Codex/Claude MCP config for this checkout",
    )
    init_config.add_argument(
        "--client",
        choices=["codex", "claude-code", "claude-desktop"],
        required=True,
    )
    init_config.add_argument("--project-root", default=str(WORKSPACE_ROOT))
    init_config.add_argument("--python", default=resolve_python_executable(WORKSPACE_ROOT))
    init_config.add_argument(
        "--server-name",
        help="Override MCP server name. Defaults to mlResearchLoop for Codex and ml-research-loop for Claude.",
    )
    init_config.add_argument("--output", help="Optional output file. Defaults to stdout.")
    init_config.add_argument("--force", action="store_true", help="Overwrite --output if it exists.")

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


def _run_init_mcp_config(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    python_executable = str(args.python)
    server_name = args.server_name or _default_mcp_server_name(args.client)
    payload = render_mcp_config(
        client=args.client,
        project_root=project_root,
        python_executable=python_executable,
        server_name=server_name,
    )
    if args.output:
        output = Path(args.output).expanduser().resolve()
        if output.exists() and not args.force:
            print(f"Refusing to overwrite existing file: {output}", file=sys.stderr)
            return 1
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        return 0
    print(payload)
    return 0


def render_mcp_config(
    client: str,
    project_root: Path,
    python_executable: str,
    server_name: str,
) -> str:
    """Render a concrete MCP client config for the local checkout."""
    project_root = project_root.expanduser().resolve()
    server_script = project_root / "scripts" / "mcp_server.py"
    env = {
        "PYTHONPATH": _pythonpath_for_project(project_root),
        "ML_RESEARCH_LOOP_PYTHON": python_executable,
    }
    if client == "codex":
        return _render_codex_config(
            server_name=server_name,
            python_executable=python_executable,
            server_script=server_script,
            project_root=project_root,
            env=env,
        )
    if client in {"claude-code", "claude-desktop"}:
        return json.dumps(
            {
                "mcpServers": {
                    server_name: {
                        "type": "stdio",
                        "command": python_executable,
                        "args": [str(server_script)],
                        "env": env,
                    }
                }
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n"
    raise ValueError(f"unsupported MCP client: {client}")


def _render_codex_config(
    server_name: str,
    python_executable: str,
    server_script: Path,
    project_root: Path,
    env: dict[str, str],
) -> str:
    return "\n".join([
        f"[mcp_servers.{server_name}]",
        f"command = {json.dumps(python_executable)}",
        f"args = [{json.dumps(str(server_script))}]",
        f"cwd = {json.dumps(str(project_root))}",
        "startup_timeout_sec = 20",
        "tool_timeout_sec = 3600",
        "",
        f"[mcp_servers.{server_name}.env]",
        f"PYTHONPATH = {json.dumps(env['PYTHONPATH'])}",
        f"ML_RESEARCH_LOOP_PYTHON = {json.dumps(env['ML_RESEARCH_LOOP_PYTHON'])}",
        "",
    ])


def _default_mcp_server_name(client: str) -> str:
    if client == "codex":
        return "mlResearchLoop"
    return "ml-research-loop"


def _pythonpath_for_project(project_root: Path) -> str:
    parts = [str(project_root)]
    parts.extend(str(path) for path in _site_packages_paths(project_root))
    return os.pathsep.join(parts)


def _site_packages_paths(project_root: Path) -> list[Path]:
    site_packages_root = project_root / ".venv" / "lib"
    if not site_packages_root.exists():
        return []
    return sorted(site_packages_root.glob("python*/site-packages"))


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
    if args.command == "init-mcp-config":
        return _run_init_mcp_config(args)
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
