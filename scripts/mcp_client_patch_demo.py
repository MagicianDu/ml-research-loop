#!/usr/bin/env python3
"""Run a deterministic MCP client-generated patch demo."""

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
TASK_ID = "mcp-client-patch"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MCP client patch proposal demo")
    parser.add_argument("--runtime-root", type=Path, default=None)
    parser.add_argument("--max-experiments", type=int, default=1)
    parser.add_argument("--experiment-duration", type=int, default=30)
    return parser.parse_args()


def make_runtime_root(runtime_root: Path | None) -> Path:
    root = runtime_root or PROJECT_ROOT / ".demo_runs" / f"{TASK_ID}-{uuid.uuid4().hex[:8]}"
    root = root.expanduser().resolve()
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    return root


def build_change_proposal(initial_review: dict[str, Any]) -> dict[str, Any]:
    state = initial_review.get("experiment_state") if isinstance(
        initial_review.get("experiment_state"), dict
    ) else {}
    plan = (
        state.get("code_change_plan", {}).get("next_experiment_plan", {})
        if isinstance(state.get("code_change_plan"), dict)
        else {}
    )
    search_region = (
        state.get("current_code", {}).get("search_region", {})
        if isinstance(state.get("current_code"), dict)
        else {}
    )
    target = str(plan.get("target_param") or next(iter(search_region), "DEPTH")).upper()
    current_value = str(search_region.get(target, plan.get("current_value", "1")))
    proposed_value = _select_proposed_value(
        current_value=current_value,
        candidate_values=plan.get("candidate_values", []),
    )
    return {
        "change_type": "hyperparam",
        "target": target,
        "current_value": current_value,
        "proposed_value": proposed_value,
        "reason": f"Client planner validates {target} using next_experiment_plan candidates.",
        "confidence": 0.72,
    }


def _select_proposed_value(current_value: str, candidate_values: Any) -> str:
    if isinstance(candidate_values, list):
        for candidate in candidate_values:
            if str(candidate) != current_value:
                return str(candidate)
    try:
        return str(int(current_value) + 1)
    except ValueError:
        return current_value


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
    initial_review = initial_round["review"]
    change_proposal = build_change_proposal(initial_review)
    client_patch = call_tool(
        "run_client_patch_experiment",
        {
            "task_config": str(task_file),
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "change_proposal": change_proposal,
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
            if initial_review.get("status") == "completed"
            and client_patch.get("status") == "completed"
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
            "run_client_patch_experiment",
            "review_research_results",
        ],
        "research_context": research_context,
        "initial_round": initial_round,
        "initial_review": initial_review,
        "change_proposal": change_proposal,
        "client_patch": client_patch,
        "final_review": final_review,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
