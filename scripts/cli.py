"""Command-line interface for ml-research-loop."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from lib.demo_templates import (
    list_demo_templates,
    materialize_demo_template,
    run_demo_template,
)
from lib.benchmarks import build_benchmark_readiness, build_official_harness_probe
from lib.feedback_bundle import build_feedback_bundle, write_feedback_bundle
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

    init_skills = subcommands.add_parser(
        "init-skills",
        help="Install the repository ML Research Loop skills for Codex or Claude",
    )
    init_skills.add_argument("--client", choices=["codex", "claude"], required=True)
    init_skills.add_argument("--project-root", default=str(WORKSPACE_ROOT))
    init_skills.add_argument(
        "--target-root",
        help="Skill root. Defaults to ~/.codex/skills for Codex and ~/.claude/skills for Claude.",
    )
    init_skills.add_argument("--force", action="store_true", help="Overwrite existing skills.")
    init_skills.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the install plan without copying files.",
    )

    feedback = subcommands.add_parser(
        "feedback-bundle",
        help="Write a redacted preview feedback diagnostics bundle",
    )
    feedback.add_argument("--runtime-root", type=Path)
    feedback.add_argument("--task-id")
    feedback.add_argument("--output-dir", type=Path, default=Path("feedback-bundle"))
    feedback.add_argument("--log-lines", type=int, default=80)
    feedback.add_argument("--python", default=sys.executable)

    benchmark = subcommands.add_parser(
        "benchmark",
        help="Inspect or run benchmark adapter compatibility flows",
    )
    benchmark_commands = benchmark.add_subparsers(dest="benchmark_command", required=True)
    benchmark_readiness = benchmark_commands.add_parser(
        "readiness",
        help="Print benchmark adapter readiness metadata",
    )
    benchmark_readiness.add_argument("--json", action="store_true")
    benchmark_smoke = benchmark_commands.add_parser(
        "smoke",
        help="Run all benchmark adapter compatibility demos",
    )
    benchmark_smoke.add_argument("--runtime-root", type=Path, required=True)
    benchmark_smoke.add_argument("--python", default=sys.executable)
    benchmark_smoke.add_argument("--json", action="store_true")
    benchmark_probe = benchmark_commands.add_parser(
        "probe",
        help="Probe official benchmark harness prerequisites without running evaluations",
    )
    benchmark_probe.add_argument("--mle-bench-repo", type=Path)
    benchmark_probe.add_argument("--paperbench-repo", type=Path)
    benchmark_probe.add_argument("--paperbench-data-dir", type=Path)
    benchmark_probe.add_argument("--json", action="store_true")

    demo = subcommands.add_parser("demo", help="List, initialize, or run stable demos")
    demo_commands = demo.add_subparsers(dest="demo_command", required=True)
    demo_commands.add_parser("list", help="List available demo templates")
    demo_init = demo_commands.add_parser("init", help="Write a demo task and dataset")
    _add_demo_template_args(demo_init)
    demo_run = demo_commands.add_parser("run", help="Write and run a demo template")
    _add_demo_template_args(demo_run)
    demo_run.add_argument("--python", default=sys.executable)
    demo_run.add_argument("--json", action="store_true")

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


def _run_init_skills(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    target_root = (
        Path(args.target_root).expanduser().resolve()
        if args.target_root
        else _default_skill_root(args.client)
    )
    try:
        payload = install_skill_package(
            client=args.client,
            project_root=project_root,
            target_root=target_root,
            force=args.force,
            dry_run=args.dry_run,
        )
    except FileExistsError as exc:
        print(
            f"Refusing to overwrite existing skill: {exc.filename or exc}",
            file=sys.stderr,
        )
        return 1
    except FileNotFoundError as exc:
        print(f"Missing repository skill package: {exc.filename or exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _run_feedback_bundle(args: argparse.Namespace) -> int:
    bundle = build_feedback_bundle(
        project_root=WORKSPACE_ROOT,
        runtime_root=args.runtime_root,
        task_id=args.task_id,
        log_lines=args.log_lines,
        python_executable=args.python,
    )
    payload = write_feedback_bundle(bundle, args.output_dir)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _run_benchmark(args: argparse.Namespace) -> int:
    if args.benchmark_command == "readiness":
        payload = build_benchmark_readiness()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.benchmark_command == "smoke":
        cmd = [
            args.python,
            str(WORKSPACE_ROOT / "scripts" / "benchmark_adapter_smoke.py"),
            "--runtime-root",
            str(args.runtime_root),
        ]
        if args.json:
            cmd.append("--json")
        return subprocess.call(cmd, cwd=str(WORKSPACE_ROOT))
    if args.benchmark_command == "probe":
        payload = build_official_harness_probe(
            mle_bench_repo=args.mle_bench_repo,
            paperbench_repo=args.paperbench_repo,
            paperbench_data_dir=args.paperbench_data_dir,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    return 2


def _run_demo(args: argparse.Namespace) -> int:
    if args.demo_command == "list":
        print(json.dumps({"templates": list_demo_templates()}, indent=2, ensure_ascii=False))
        return 0
    if args.demo_command == "init":
        try:
            payload = materialize_demo_template(
                template_name=args.template,
                runtime_root=args.runtime_root,
                project_root=WORKSPACE_ROOT,
                max_experiments=args.max_experiments,
                experiment_duration=args.experiment_duration,
                force=args.force,
            )
        except (FileExistsError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.demo_command == "run":
        try:
            payload = run_demo_template(
                template_name=args.template,
                runtime_root=args.runtime_root,
                project_root=WORKSPACE_ROOT,
                max_experiments=args.max_experiments,
                experiment_duration=args.experiment_duration,
                force=args.force,
                python_executable=args.python,
            )
        except (FileExistsError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "completed" else 1
    return 2


def _add_demo_template_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--template", required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--max-experiments", type=int)
    parser.add_argument("--experiment-duration", type=int)
    parser.add_argument("--force", action="store_true")


def install_skill_package(
    client: str,
    project_root: Path,
    target_root: Path,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    """Copy repository-local skills into the selected client skill root."""
    source_root = project_root / "skills"
    skill_items = []
    for name in mcp_service.RECOMMENDED_SKILLS:
        source = source_root / name
        if not (source / "SKILL.md").exists():
            raise FileNotFoundError(str(source / "SKILL.md"))
        target = target_root / name
        if target.exists() and not force and not dry_run:
            raise FileExistsError(str(target))
        skill_items.append({
            "name": name,
            "source_path": str(source),
            "target_path": str(target),
        })

    if not dry_run:
        target_root.mkdir(parents=True, exist_ok=True)
        for item in skill_items:
            source = Path(str(item["source_path"]))
            target = Path(str(item["target_path"]))
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)

    return {
        "status": "dry_run" if dry_run else "installed",
        "client": client,
        "source_root": str(source_root),
        "target_root": str(target_root),
        "skills": skill_items,
    }


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


def _default_skill_root(client: str) -> Path:
    if client == "codex":
        return Path.home() / ".codex" / "skills"
    return Path.home() / ".claude" / "skills"


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
    if args.command == "init-skills":
        return _run_init_skills(args)
    if args.command == "feedback-bundle":
        return _run_feedback_bundle(args)
    if args.command == "benchmark":
        return _run_benchmark(args)
    if args.command == "demo":
        return _run_demo(args)
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
