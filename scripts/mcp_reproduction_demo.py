#!/usr/bin/env python3
"""Run a deterministic MCP reproduction-readiness and rubric grading demo."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from lib.reproduction_protocol import RubricTask, build_grade_report
from scripts import mcp_real_data_demo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "mcp-reproduction"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MCP reproduction demo")
    parser.add_argument("--runtime-root", type=Path, default=None)
    parser.add_argument("--max-experiments", type=int, default=1)
    parser.add_argument("--experiment-duration", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def make_runtime_root(runtime_root: Path | None) -> Path:
    root = runtime_root or PROJECT_ROOT / ".demo_runs" / f"mcp-reproduction-{uuid.uuid4().hex[:8]}"
    root = root.expanduser().resolve()
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    return root


def write_reproduction_task(
    runtime_root: Path,
    dataset_file: Path,
    max_experiments: int,
    experiment_duration: int,
) -> Path:
    task_file = mcp_real_data_demo.write_task(
        runtime_root=runtime_root,
        dataset_file=dataset_file,
        max_experiments=max_experiments,
        experiment_duration=experiment_duration,
    )
    task = json.loads(task_file.read_text(encoding="utf-8"))
    task["task_id"] = TASK_ID
    task["objective"] = "reproduce a bounded local val_bpb experiment"
    task["reproduction_spec"] = {
        "mode": "local_command",
        "command": [os.environ.get("ML_RESEARCH_LOOP_PYTHON", sys.executable), "train.py"],
        "timeout_seconds": experiment_duration,
        "required_files": ["train.py", "program.md"],
    }
    reproduction_task_file = runtime_root / "tasks" / f"{TASK_ID}.json"
    reproduction_task_file.write_text(
        json.dumps(task, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    task_file.unlink(missing_ok=True)
    return reproduction_task_file


def main() -> int:
    args = parse_args()
    runtime_root = make_runtime_root(args.runtime_root)
    dataset_file = mcp_real_data_demo.write_dataset(runtime_root)
    task_file = write_reproduction_task(
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
    review = mcp_real_data_demo.call_tool(
        "review_research_results",
        {
            "task_id": TASK_ID,
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
        },
    )
    state = review.get("experiment_state") if isinstance(review.get("experiment_state"), dict) else {}
    reproduction = (
        state.get("reproduction")
        if isinstance(state.get("reproduction"), dict)
        else {"readiness": {"status": "not_configured"}}
    )
    grade_report = build_demo_grade_report(
        workspace=workspace,
        run_payload=run_payload,
        reproduction=reproduction,
    )
    status = (
        "passed"
        if review.get("status") == "completed"
        and reproduction.get("readiness", {}).get("status") == "ready"
        and grade_report["score"] > 0
        else "failed"
    )
    payload = {
        "status": status,
        "runtime_root": str(runtime_root),
        "task_id": TASK_ID,
        "task_file": str(task_file),
        "workspace": str(workspace),
        "run": {
            "status": run_payload.get("status"),
            "returncode": run_payload.get("returncode"),
            "experiments": run_payload.get("experiments"),
        },
        "reproduction": reproduction,
        "grade_report": grade_report,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if status == "passed" else 1


def build_demo_grade_report(
    workspace: Path,
    run_payload: dict[str, Any],
    reproduction: dict[str, Any],
) -> dict[str, Any]:
    rubric = RubricTask(
        id="root",
        requirements="Local reproduction demo should produce executable code and a completed run.",
        weight=1,
        sub_tasks=[
            RubricTask(
                id="code",
                requirements="train.py and program.md exist in the workspace.",
                weight=1,
                task_category="Code Development",
            ),
            RubricTask(
                id="run",
                requirements="The bounded experiment run completes and reproduction readiness is ready.",
                weight=1,
                task_category="Code Execution",
            ),
        ],
    )
    readiness = reproduction.get("readiness") if isinstance(reproduction.get("readiness"), dict) else {}
    leaf_scores = {
        "code": 1.0 if (workspace / "train.py").exists() and (workspace / "program.md").exists() else 0.0,
        "run": (
            1.0
            if run_payload.get("status") == "completed"
            and readiness.get("status") == "ready"
            else 0.0
        ),
    }
    return build_grade_report(
        rubric=rubric,
        leaf_scores=leaf_scores,
        grader_log="Deterministic local grade based on workspace files and MCP run status.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
