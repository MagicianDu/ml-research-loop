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
from lib.benchmarks import (
    build_benchmark_readiness,
    build_official_harness_probe,
    build_official_proof_setup_bundle,
    build_proof_archive_bundle,
    build_proof_publication_bundle,
    build_public_proof_plan,
    grade_official_mle_submission,
    materialize_official_mle_agent_workspace,
    run_official_mle_solver_round,
    write_official_mle_patch_round_proof_bundle,
    write_official_proof_setup_bundle,
    write_paperbench_codex_review_bundle,
    write_paperbench_codex_review_report,
    write_proof_archive_bundle,
    write_proof_publication_bundle,
)
from lib.feedback_bundle import build_feedback_bundle, write_feedback_bundle
from lib.memory_adapters import search_memory_adapters, sync_cards_to_adapters
from lib.research_memory import (
    ResearchMemoryStore,
    extract_fasttext_release_memory_cards,
)
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

    memory = subcommands.add_parser("memory", help="Record or retrieve local research memory")
    memory_commands = memory.add_subparsers(dest="memory_command", required=True)
    memory_record = memory_commands.add_parser(
        "record-fasttext-release",
        help="Record fastText release proof artifacts into a memory JSONL store",
    )
    memory_record.add_argument("--store", type=Path, required=True)
    memory_record.add_argument("--release-manifest", type=Path, required=True)
    memory_record.add_argument("--multi-round-report", type=Path, required=True)
    memory_record.add_argument("--review-checklist", type=Path, required=True)
    memory_record.add_argument(
        "--sync-adapters",
        action="store_true",
        help="Explicitly sync recorded cards to configured optional memory adapters",
    )
    memory_record.add_argument(
        "--adapter",
        action="append",
        choices=["graphiti", "cognee"],
        help="Optional adapter to sync/search. Can be provided multiple times.",
    )
    memory_retrieve = memory_commands.add_parser(
        "retrieve",
        help="Retrieve matching local research memory cards",
    )
    memory_retrieve.add_argument("--store", type=Path, required=True)
    memory_retrieve.add_argument("--query", required=True)
    memory_retrieve.add_argument("--paper-id")
    memory_retrieve.add_argument("--dataset")
    memory_retrieve.add_argument("--limit", type=int, default=10)
    memory_retrieve.add_argument(
        "--include-adapters",
        action="store_true",
        help="Explicitly include configured optional adapter search results",
    )
    memory_retrieve.add_argument(
        "--adapter",
        action="append",
        choices=["graphiti", "cognee"],
        help="Optional adapter to sync/search. Can be provided multiple times.",
    )

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
    benchmark_proof_plan = benchmark_commands.add_parser(
        "proof-plan",
        help="Plan a public official-debug proof run without launching evaluations",
    )
    benchmark_proof_plan.add_argument("--mle-bench-repo", type=Path)
    benchmark_proof_plan.add_argument("--paperbench-repo", type=Path)
    benchmark_proof_plan.add_argument("--paperbench-data-dir", type=Path)
    benchmark_proof_plan.add_argument("--json", action="store_true")
    benchmark_setup_bundle = benchmark_commands.add_parser(
        "setup-bundle",
        help="Write read-only setup files for an official debug proof-run environment",
    )
    benchmark_setup_bundle.add_argument("--mle-bench-repo", type=Path)
    benchmark_setup_bundle.add_argument("--paperbench-repo", type=Path)
    benchmark_setup_bundle.add_argument("--paperbench-data-dir", type=Path)
    benchmark_setup_bundle.add_argument("--output-dir", type=Path, required=True)
    benchmark_setup_bundle.add_argument("--json", action="store_true")
    benchmark_publication_bundle = benchmark_commands.add_parser(
        "publication-bundle",
        help="Write a guarded publication bundle from proof-run artifacts",
    )
    benchmark_publication_bundle.add_argument("--manifest", type=Path, required=True)
    benchmark_publication_bundle.add_argument("--artifact-root", type=Path, required=True)
    benchmark_publication_bundle.add_argument("--output-dir", type=Path, required=True)
    benchmark_publication_bundle.add_argument("--json", action="store_true")
    benchmark_archive_proof = benchmark_commands.add_parser(
        "archive-proof",
        help="Copy proof-run artifacts into a hashed archive bundle",
    )
    benchmark_archive_proof.add_argument("--manifest", type=Path, required=True)
    benchmark_archive_proof.add_argument("--artifact-root", type=Path, required=True)
    benchmark_archive_proof.add_argument("--output-dir", type=Path, required=True)
    benchmark_archive_proof.add_argument("--json", action="store_true")
    benchmark_mle_workspace = benchmark_commands.add_parser(
        "mle-workspace",
        help="Create an agent workspace from official MLE-bench prepared data",
    )
    benchmark_mle_workspace.add_argument("--competition-id", required=True)
    benchmark_mle_workspace.add_argument("--prepared-competition-dir", type=Path, required=True)
    benchmark_mle_workspace.add_argument("--runtime-root", type=Path, required=True)
    benchmark_mle_workspace.add_argument("--workspace-name")
    benchmark_mle_workspace.add_argument("--json", action="store_true")
    benchmark_mle_grade = benchmark_commands.add_parser(
        "mle-grade",
        help="Grade a submission with official mlebench grade-sample",
    )
    benchmark_mle_grade.add_argument("--competition-id", required=True)
    benchmark_mle_grade.add_argument("--submission", type=Path, required=True)
    benchmark_mle_grade.add_argument("--data-dir", type=Path, required=True)
    benchmark_mle_grade.add_argument("--mlebench", type=Path, required=True)
    benchmark_mle_grade.add_argument("--output-dir", type=Path, required=True)
    benchmark_mle_grade.add_argument("--timeout-seconds", type=int, default=300)
    benchmark_mle_grade.add_argument("--json", action="store_true")
    benchmark_mle_round = benchmark_commands.add_parser(
        "mle-round",
        help="Run workspace solve.py and grade submission.csv with official mlebench grade-sample",
    )
    benchmark_mle_round.add_argument("--competition-id", required=True)
    benchmark_mle_round.add_argument("--workspace", type=Path, required=True)
    benchmark_mle_round.add_argument("--data-dir", type=Path, required=True)
    benchmark_mle_round.add_argument("--mlebench", type=Path, required=True)
    benchmark_mle_round.add_argument("--output-dir", type=Path, required=True)
    benchmark_mle_round.add_argument("--python", default=sys.executable)
    benchmark_mle_round.add_argument("--round-id", default="round-001")
    benchmark_mle_round.add_argument("--timeout-seconds", type=int, default=300)
    benchmark_mle_round.add_argument("--json", action="store_true")
    benchmark_mle_patch_round = benchmark_commands.add_parser(
        "mle-patch-round",
        help="Apply a workspace patch, run solve.py, and grade submission.csv",
    )
    benchmark_mle_patch_round.add_argument("--competition-id", required=True)
    benchmark_mle_patch_round.add_argument("--workspace", type=Path, required=True)
    benchmark_mle_patch_round.add_argument("--data-dir", type=Path, required=True)
    benchmark_mle_patch_round.add_argument("--mlebench", type=Path, required=True)
    benchmark_mle_patch_round.add_argument("--output-dir", type=Path, required=True)
    benchmark_mle_patch_round.add_argument("--patch-file", type=Path, required=True)
    benchmark_mle_patch_round.add_argument("--python", default=sys.executable)
    benchmark_mle_patch_round.add_argument("--round-id", default="round-001")
    benchmark_mle_patch_round.add_argument("--timeout-seconds", type=int, default=300)
    benchmark_mle_patch_round.add_argument("--json", action="store_true")
    benchmark_mle_patch_proof = benchmark_commands.add_parser(
        "mle-patch-proof",
        help="Write a proof archive from an official MLE-bench patch-round report",
    )
    benchmark_mle_patch_proof.add_argument("--patch-round-report", type=Path, required=True)
    benchmark_mle_patch_proof.add_argument("--output-dir", type=Path, required=True)
    benchmark_mle_patch_proof.add_argument("--json", action="store_true")
    benchmark_paperbench_codex_bundle = benchmark_commands.add_parser(
        "paperbench-codex-review-bundle",
        help="Prepare PaperBench artifacts for Codex-assisted rubric review",
    )
    benchmark_paperbench_codex_bundle.add_argument("--run-dir", type=Path, required=True)
    benchmark_paperbench_codex_bundle.add_argument("--paper-dir", type=Path, required=True)
    benchmark_paperbench_codex_bundle.add_argument("--output-dir", type=Path, required=True)
    benchmark_paperbench_codex_bundle.add_argument("--json", action="store_true")
    benchmark_paperbench_codex_report = benchmark_commands.add_parser(
        "paperbench-codex-review-report",
        help="Write a Codex-assisted PaperBench rubric review report",
    )
    benchmark_paperbench_codex_report.add_argument("--bundle", type=Path, required=True)
    benchmark_paperbench_codex_report.add_argument("--review-file", type=Path, required=True)
    benchmark_paperbench_codex_report.add_argument("--output-dir", type=Path, required=True)
    benchmark_paperbench_codex_report.add_argument("--json", action="store_true")

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


def _run_memory(args: argparse.Namespace) -> int:
    store = ResearchMemoryStore(args.store)
    if args.memory_command == "record-fasttext-release":
        cards = extract_fasttext_release_memory_cards(
            release_manifest=args.release_manifest,
            multi_round_report=args.multi_round_report,
            review_checklist=args.review_checklist,
        )
        for card in cards:
            store.append(card)
        adapter_results = None
        if args.sync_adapters:
            adapter_results = sync_cards_to_adapters(
                cards,
                adapter_names=args.adapter,
            )
        payload = {
            "status": "recorded",
            "store": str(args.store),
            "card_count": len(cards),
            "card_ids": [card.card_id for card in cards],
            "official_scores_claimed": False,
        }
        if adapter_results is not None:
            payload["adapter_results"] = adapter_results
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.memory_command == "retrieve":
        matches = store.search(
            query=args.query,
            paper_id=args.paper_id,
            dataset=args.dataset,
            limit=args.limit,
        )
        payload = {
            "status": "retrieved",
            "store": str(args.store),
            "match_count": len(matches),
            "matches": [match.to_dict() for match in matches],
        }
        if args.include_adapters:
            payload["adapter_results"] = search_memory_adapters(
                query=args.query,
                limit=args.limit,
                adapter_names=args.adapter,
            )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    return 2


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
    if args.benchmark_command == "proof-plan":
        probe = build_official_harness_probe(
            mle_bench_repo=args.mle_bench_repo,
            paperbench_repo=args.paperbench_repo,
            paperbench_data_dir=args.paperbench_data_dir,
        )
        payload = build_public_proof_plan(probe)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.benchmark_command == "setup-bundle":
        probe = build_official_harness_probe(
            mle_bench_repo=args.mle_bench_repo,
            paperbench_repo=args.paperbench_repo,
            paperbench_data_dir=args.paperbench_data_dir,
        )
        proof_plan = build_public_proof_plan(probe)
        bundle = build_official_proof_setup_bundle(proof_plan)
        payload = write_official_proof_setup_bundle(bundle, args.output_dir)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.benchmark_command == "publication-bundle":
        artifact_manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        bundle = build_proof_publication_bundle(artifact_manifest, args.artifact_root)
        payload = write_proof_publication_bundle(bundle, args.output_dir)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.benchmark_command == "archive-proof":
        artifact_manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        bundle = build_proof_archive_bundle(artifact_manifest, args.artifact_root)
        payload = write_proof_archive_bundle(bundle, args.artifact_root, args.output_dir)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.benchmark_command == "mle-workspace":
        payload = materialize_official_mle_agent_workspace(
            competition_id=args.competition_id,
            prepared_competition_dir=args.prepared_competition_dir,
            runtime_root=args.runtime_root,
            workspace_name=args.workspace_name,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.benchmark_command == "mle-grade":
        payload = grade_official_mle_submission(
            competition_id=args.competition_id,
            submission_path=args.submission,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            mlebench_executable=args.mlebench,
            timeout_seconds=args.timeout_seconds,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "graded" else 1
    if args.benchmark_command == "mle-round":
        payload = run_official_mle_solver_round(
            competition_id=args.competition_id,
            workspace=args.workspace,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            mlebench_executable=args.mlebench,
            python_executable=args.python,
            round_id=args.round_id,
            timeout_seconds=args.timeout_seconds,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "graded" else 1
    if args.benchmark_command == "mle-patch-round":
        payload = mcp_service.run_official_mle_bench_patch_round_tool({
            "competition_id": args.competition_id,
            "workspace": str(args.workspace),
            "data_dir": str(args.data_dir),
            "mlebench": str(args.mlebench),
            "output_dir": str(args.output_dir),
            "patch": args.patch_file.read_text(encoding="utf-8"),
            "python": args.python,
            "round_id": args.round_id,
            "timeout_seconds": args.timeout_seconds,
        })
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "graded" else 1
    if args.benchmark_command == "mle-patch-proof":
        payload = write_official_mle_patch_round_proof_bundle(
            patch_round_report=args.patch_round_report,
            output_dir=args.output_dir,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    if args.benchmark_command == "paperbench-codex-review-bundle":
        payload = write_paperbench_codex_review_bundle(
            run_dir=args.run_dir,
            paper_dir=args.paper_dir,
            output_dir=args.output_dir,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    if args.benchmark_command == "paperbench-codex-review-report":
        payload = write_paperbench_codex_review_report(
            bundle_path=args.bundle,
            review_payload=json.loads(args.review_file.read_text(encoding="utf-8")),
            output_dir=args.output_dir,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
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
    if args.command == "memory":
        return _run_memory(args)
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
