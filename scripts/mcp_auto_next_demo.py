#!/usr/bin/env python3
"""Run a deterministic MCP review-to-auto-next demo."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from scripts.mcp_multi_round_demo import (
    build_research_context,
    call_tool,
    run_round,
    write_round_task,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "mcp-auto-next"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MCP review-to-auto-next demo")
    parser.add_argument("--runtime-root", type=Path, default=None)
    parser.add_argument("--max-experiments", type=int, default=1)
    parser.add_argument("--experiment-duration", type=int, default=30)
    return parser.parse_args()


def make_runtime_root(runtime_root: Path | None) -> Path:
    root = runtime_root or PROJECT_ROOT / ".demo_runs" / f"{TASK_ID}-{uuid.uuid4().hex[:8]}"
    root = root.expanduser().resolve()
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    return root


def main() -> int:
    args = parse_args()
    runtime_root = make_runtime_root(args.runtime_root)
    research_context = build_research_context()
    task_file = write_round_task(
        runtime_root=runtime_root,
        task_id=TASK_ID,
        max_experiments=args.max_experiments,
        experiment_duration=args.experiment_duration,
    )
    initial_round = run_round(
        runtime_root=runtime_root,
        task_id=TASK_ID,
        task_file=task_file,
        research_context=research_context,
        max_experiments=args.max_experiments,
        experiment_duration=args.experiment_duration,
    )
    workspace = runtime_root / "workdir" / TASK_ID
    auto_next = call_tool(
        "run_next_experiment_from_review",
        {
            "task_id": TASK_ID,
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "max_experiments": args.max_experiments,
            "experiment_duration": args.experiment_duration,
            "python": os.environ.get("ML_RESEARCH_LOOP_PYTHON", sys.executable),
            "include_final_review": True,
        },
    )
    final_review = call_tool(
        "review_research_results",
        {
            "task_id": TASK_ID,
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
        },
    )

    payload: dict[str, Any] = {
        "status": (
            "completed"
            if initial_round["review"].get("status") == "completed"
            and auto_next.get("status") == "completed"
            and final_review.get("status") == "completed"
            else "failed"
        ),
        "runtime_root": str(runtime_root),
        "task_id": TASK_ID,
        "task_file": str(task_file),
        "result_file": final_review.get("result_file"),
        "program_file": str(workspace / "program.md"),
        "tool_chain": [
            "research_task",
            "propose_hypotheses",
            "run_hypothesis_experiment",
            "review_research_results",
            "run_next_experiment_from_review",
            "review_research_results",
        ],
        "research_context": research_context,
        "initial_review": initial_round["review"],
        "auto_next": auto_next,
        "final_review": final_review,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
