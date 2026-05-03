#!/usr/bin/env python3
"""Run a real local-data MCP task and apply a guarded client code patch."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from scripts import mcp_real_data_demo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TASK_ID = mcp_real_data_demo.TASK_ID


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MCP real task/code benchmark")
    parser.add_argument("--runtime-root", type=Path, default=None)
    parser.add_argument("--max-experiments", type=int, default=1)
    parser.add_argument("--experiment-duration", type=int, default=30)
    return parser.parse_args()


def make_runtime_root(runtime_root: Path | None) -> Path:
    root = runtime_root or PROJECT_ROOT / ".demo_runs" / f"mcp-real-task-code-{uuid.uuid4().hex[:8]}"
    root = root.expanduser().resolve()
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    return root


def main() -> int:
    args = parse_args()
    runtime_root = make_runtime_root(args.runtime_root)
    dataset_file = mcp_real_data_demo.write_dataset(runtime_root)
    task_file = mcp_real_data_demo.write_task(
        runtime_root=runtime_root,
        dataset_file=dataset_file,
        max_experiments=args.max_experiments,
        experiment_duration=args.experiment_duration,
    )
    workspace = runtime_root / "workdir" / TASK_ID
    research_context = mcp_real_data_demo.build_research_context()
    run_payload = mcp_real_data_demo.call_tool(
        "run_hypothesis_experiment",
        {
            "task_config": str(task_file),
            "workspace": str(workspace),
            "runtime_root": str(runtime_root),
            "research_context": research_context,
            "hypotheses": research_context.get("hypotheses", []),
            "max_experiments": args.max_experiments,
            "experiment_duration": args.experiment_duration,
            "python": os.environ.get("ML_RESEARCH_LOOP_PYTHON", sys.executable),
        },
    )
    initial_review = mcp_real_data_demo.call_tool(
        "review_research_results",
        {
            "task_id": TASK_ID,
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
        },
    )
    patch_planning = build_patch_planning(initial_review, workspace / "train.py")
    code_patch = mcp_real_data_demo.call_tool(
        "apply_client_code_patch",
        {
            "workspace": str(workspace),
            "runtime_root": str(runtime_root),
            "patch": patch_planning["diff"],
            "description": "Apply the first client-planned SEARCH REGION code edit.",
            "allowed_files": ["train.py", "program.md"],
            "run_syntax_check": True,
            "test_command": [
                os.environ.get("ML_RESEARCH_LOOP_PYTHON", sys.executable),
                "-m",
                "py_compile",
                "train.py",
            ],
            "test_timeout_seconds": 60,
            "task_id": TASK_ID,
            "include_post_patch_review": True,
            "initial_review": initial_review,
        },
    )
    post_patch_review = code_patch.get("post_patch_review")
    if not isinstance(post_patch_review, dict):
        post_patch_review = mcp_real_data_demo.call_tool(
            "review_research_results",
            {
                "task_id": TASK_ID,
                "runtime_root": str(runtime_root),
                "workspace": str(workspace),
            },
        )
    data_source = detect_data_source(workspace)
    payload = {
        "status": (
            "completed"
            if initial_review.get("status") == "completed"
            and post_patch_review.get("status") == "completed"
            and code_patch.get("status") == "applied"
            and data_source == "real_file"
            else "failed"
        ),
        "runtime_root": str(runtime_root),
        "task_id": TASK_ID,
        "task_file": str(task_file),
        "dataset_file": str(dataset_file),
        "data_source": data_source,
        "run_budget": {
            "max_experiments": args.max_experiments,
            "experiment_duration_seconds": args.experiment_duration,
        },
        "run": {
            "status": run_payload.get("status"),
            "returncode": run_payload.get("returncode"),
            "experiments": run_payload.get("experiments"),
        },
        "initial_review": initial_review,
        "patch_planning": {
            key: value
            for key, value in patch_planning.items()
            if key != "diff"
        },
        "code_patch": code_patch,
        "post_patch_review": post_patch_review,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "completed" else 1


def build_patch_planning(review: dict[str, Any], train_py: Path) -> dict[str, str]:
    state = review.get("experiment_state") if isinstance(review.get("experiment_state"), dict) else {}
    current_code = (
        state.get("current_code")
        if isinstance(state.get("current_code"), dict)
        else {}
    )
    search_region = (
        current_code.get("search_region")
        if isinstance(current_code.get("search_region"), dict)
        else {}
    )
    plan = (
        state.get("code_change_plan", {}).get("next_experiment_plan", {})
        if isinstance(state.get("code_change_plan"), dict)
        else {}
    )
    target = str(plan.get("target_param") or next(iter(search_region), "")).upper()
    if not target or target not in search_region:
        raise RuntimeError("review did not expose a patchable SEARCH REGION target")
    current_value = str(search_region[target])
    proposed_value = select_proposed_value(current_value, plan.get("candidate_values", []))
    diff = build_multi_file_diff(
        train_py=train_py,
        program_md=train_py.parent / "program.md",
        target=target,
        current_value=current_value,
        proposed_value=proposed_value,
    )
    return {
        "source": "code_change_plan.next_experiment_plan",
        "target": target,
        "current_value": current_value,
        "proposed_value": proposed_value,
        "diff": diff,
    }


def select_proposed_value(current_value: str, candidate_values: Any) -> str:
    if isinstance(candidate_values, list):
        for candidate in candidate_values:
            if str(candidate) != current_value:
                return str(candidate)
    try:
        return str(int(current_value) + 1)
    except ValueError:
        return current_value


def build_single_line_diff(
    train_py: Path,
    target: str,
    current_value: str,
    proposed_value: str,
) -> str:
    lines = train_py.read_text(encoding="utf-8").splitlines()
    expected = f"{target} = {current_value}"
    for index, line in enumerate(lines, start=1):
        if line.strip() != expected:
            continue
        prefix = line[: len(line) - len(line.lstrip())]
        return "\n".join([
            "--- a/train.py",
            "+++ b/train.py",
            f"@@ -{index},1 +{index},1 @@",
            f"-{line}",
            f"+{prefix}{target} = {proposed_value}",
            "",
        ])
    raise RuntimeError(f"Could not find SEARCH REGION line: {expected}")


def build_multi_file_diff(
    train_py: Path,
    program_md: Path,
    target: str,
    current_value: str,
    proposed_value: str,
) -> str:
    parts = [
        build_single_line_diff(
            train_py=train_py,
            target=target,
            current_value=current_value,
            proposed_value=proposed_value,
        ).rstrip()
    ]
    if program_md.exists():
        parts.append(
            build_program_note_diff(
                program_md=program_md,
                target=target,
                current_value=current_value,
                proposed_value=proposed_value,
            ).rstrip()
        )
    return "\n".join([*parts, ""])


def build_program_note_diff(
    program_md: Path,
    target: str,
    current_value: str,
    proposed_value: str,
) -> str:
    lines = program_md.read_text(encoding="utf-8").splitlines()
    insert_at = len(lines) + 1
    note = f"Client patch note: {target} changed from {current_value} to {proposed_value}."
    return "\n".join([
        "--- a/program.md",
        "+++ b/program.md",
        f"@@ -{insert_at},0 +{insert_at},1 @@",
        f"+{note}",
        "",
    ])


def detect_data_source(workspace: Path) -> str:
    log_file = workspace / "logs" / "exp-001.log"
    log_text = log_file.read_text(encoding="utf-8") if log_file.exists() else ""
    if "[train.py] Data loaded: 4096 bytes" in log_text and "Data not found" not in log_text:
        return "real_file"
    return "synthetic_fallback"


if __name__ == "__main__":
    raise SystemExit(main())
