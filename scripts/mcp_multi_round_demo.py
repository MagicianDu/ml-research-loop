#!/usr/bin/env python3
"""Run a deterministic two-round MCP planner/executor loop."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from lib import mcp_service


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TASK_PREFIX = "mcp-multi-round"
OBJECTIVE = "minimize val_bpb on synthetic data"
FIXTURE_SOURCE = {
    "source_type": "paper",
    "title": "Attention Is All You Need",
    "url": "https://arxiv.org/abs/1706.03762",
    "summary": "Transformer architecture reference for attention experiments.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a multi-round MCP optimization demo")
    parser.add_argument("--runtime-root", type=Path, default=None)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--max-experiments", type=int, default=1)
    parser.add_argument("--experiment-duration", type=int, default=30)
    return parser.parse_args()


def make_runtime_root(runtime_root: Path | None) -> Path:
    root = runtime_root or PROJECT_ROOT / ".demo_runs" / f"mcp-multi-round-{uuid.uuid4().hex[:8]}"
    root = root.expanduser().resolve()
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    return root


def write_round_task(
    runtime_root: Path,
    task_id: str,
    max_experiments: int,
    experiment_duration: int,
) -> Path:
    task_file = runtime_root / "tasks" / f"{task_id}.json"
    task = {
        "task_id": task_id,
        "objective": OBJECTIVE,
        "dataset": {"name": "synthetic", "path": "missing.bin"},
        "metric": {"name": "val_bpb", "direction": "minimize", "threshold": 0.0},
        "hyperparameter_space": {
            "batch_size": {"type": "choice", "values": [1]},
            "depth": {"type": "choice", "values": [1]},
            "dim": {"type": "choice", "values": [32]},
            "window_size": {"type": "choice", "values": [256]},
        },
        "budget": {
            "max_experiments": max_experiments,
            "max_duration_minutes": 5,
            "experiment_duration_seconds": experiment_duration,
        },
        "base_code": {
            "train_py_url": f"file://{PROJECT_ROOT / 'base' / 'train_base.py'}",
            "prepare_py_url": f"file://{PROJECT_ROOT / 'base' / 'prepare.py'}",
        },
    }
    task_file.write_text(json.dumps(task, indent=2, ensure_ascii=False), encoding="utf-8")
    return task_file


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = mcp_service.handle_request({
        "jsonrpc": "2.0",
        "id": name,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    if response is None:
        raise RuntimeError(f"No MCP response for tool: {name}")
    if "error" in response:
        raise RuntimeError(response["error"]["message"])

    result = response["result"]
    payload = json.loads(result["content"][0]["text"])
    if result.get("isError"):
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    return payload


def build_research_context() -> dict[str, Any]:
    call_tool(
        "research_task",
        {
            "objective": OBJECTIVE,
            "query": "tiny stories transformer",
            "paper_limit": 1,
            "dataset_limit": 1,
            "include_papers": False,
            "include_hf_datasets": False,
            "include_github_code": False,
        },
    )
    return call_tool(
        "propose_hypotheses",
        {
            "objective": OBJECTIVE,
            "sources": [FIXTURE_SOURCE],
        },
    )


def run_round(
    runtime_root: Path,
    task_id: str,
    task_file: Path,
    research_context: dict[str, Any],
    max_experiments: int,
    experiment_duration: int,
    task_patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    workspace = runtime_root / "workdir" / task_id
    arguments = {
        "task_config": str(task_file),
        "workspace": str(workspace),
        "runtime_root": str(runtime_root),
        "research_context": research_context,
        "hypotheses": research_context.get("hypotheses", []),
        "max_experiments": max_experiments,
        "experiment_duration": experiment_duration,
        "python": os.environ.get("ML_RESEARCH_LOOP_PYTHON", sys.executable),
    }
    if task_patch:
        arguments["task_patch"] = task_patch

    run_payload = call_tool("run_hypothesis_experiment", arguments)
    review = call_tool(
        "review_research_results",
        {
            "task_id": task_id,
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
        },
    )
    patched_task_file = runtime_root / "tasks" / f"{task_id}-hypothesis.json"
    patched_task = json.loads(patched_task_file.read_text(encoding="utf-8"))

    return {
        "task_id": task_id,
        "task_file": str(task_file),
        "patched_task_file": str(patched_task_file),
        "result_file": review.get("result_file"),
        "program_file": str(workspace / "program.md"),
        "input_task_patch": task_patch,
        "patched_task": patched_task,
        "run": {
            "status": run_payload.get("status"),
            "returncode": run_payload.get("returncode"),
            "experiments": run_payload.get("experiments"),
        },
        "review": review,
    }


def main() -> int:
    args = parse_args()
    if args.rounds < 1:
        raise SystemExit("--rounds must be >= 1")

    runtime_root = make_runtime_root(args.runtime_root)
    research_context = build_research_context()
    rounds: list[dict[str, Any]] = []
    task_patch = None

    for index in range(1, args.rounds + 1):
        task_id = f"{TASK_PREFIX}-r{index}"
        task_file = write_round_task(
            runtime_root=runtime_root,
            task_id=task_id,
            max_experiments=args.max_experiments,
            experiment_duration=args.experiment_duration,
        )
        round_payload = run_round(
            runtime_root=runtime_root,
            task_id=task_id,
            task_file=task_file,
            research_context=research_context,
            max_experiments=args.max_experiments,
            experiment_duration=args.experiment_duration,
            task_patch=task_patch,
        )
        rounds.append(round_payload)
        task_patch = (
            round_payload
            .get("review", {})
            .get("experiment_state", {})
            .get("next_round", {})
            .get("task_patch")
        )

    payload = {
        "status": "completed" if all(item["review"].get("status") == "completed" for item in rounds) else "failed",
        "runtime_root": str(runtime_root),
        "round_count": len(rounds),
        "tool_chain": _tool_chain(len(rounds)),
        "research_context": research_context,
        "rounds": rounds,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "completed" else 1


def _tool_chain(round_count: int) -> list[str]:
    chain = ["research_task", "propose_hypotheses"]
    for _ in range(round_count):
        chain.extend(["run_hypothesis_experiment", "review_research_results"])
    return chain


if __name__ == "__main__":
    raise SystemExit(main())
