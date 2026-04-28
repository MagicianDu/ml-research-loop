#!/usr/bin/env python3
"""Run a deterministic MCP tool-chain demo from research context to review."""

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
TASK_ID = "mcp-golden-path"
OBJECTIVE = "minimize val_bpb on synthetic data"
FIXTURE_SOURCE = {
    "source_type": "paper",
    "title": "Attention Is All You Need",
    "url": "https://arxiv.org/abs/1706.03762",
    "summary": "Transformer architecture reference for attention experiments.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MCP research-to-validation golden path")
    parser.add_argument("--runtime-root", type=Path, default=None)
    parser.add_argument("--max-experiments", type=int, default=1)
    parser.add_argument("--experiment-duration", type=int, default=30)
    parser.add_argument(
        "--live-research",
        action="store_true",
        help="Use live arXiv/Hugging Face research_task search before falling back to fixture source.",
    )
    return parser.parse_args()


def make_runtime_root(runtime_root: Path | None) -> Path:
    root = runtime_root or PROJECT_ROOT / ".demo_runs" / f"mcp-golden-path-{uuid.uuid4().hex[:8]}"
    root = root.expanduser().resolve()
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    return root


def write_base_task(runtime_root: Path, max_experiments: int, experiment_duration: int) -> Path:
    task_file = runtime_root / "tasks" / f"{TASK_ID}.json"
    task = {
        "task_id": TASK_ID,
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


def build_research_context(live_research: bool) -> dict[str, Any]:
    research_context = call_tool(
        "research_task",
        {
            "objective": OBJECTIVE,
            "query": "tiny stories transformer",
            "paper_limit": 1,
            "dataset_limit": 1,
            "include_papers": live_research,
            "include_hf_datasets": live_research,
            "include_github_code": False,
        },
    )
    if live_research and research_context.get("sources"):
        return research_context

    return call_tool(
        "propose_hypotheses",
        {
            "objective": OBJECTIVE,
            "sources": [FIXTURE_SOURCE],
        },
    )


def main() -> int:
    args = parse_args()
    runtime_root = make_runtime_root(args.runtime_root)
    task_file = write_base_task(runtime_root, args.max_experiments, args.experiment_duration)

    research_context = build_research_context(args.live_research)
    run_payload = call_tool(
        "run_hypothesis_experiment",
        {
            "task_config": str(task_file),
            "workspace": str(runtime_root / "workdir" / TASK_ID),
            "runtime_root": str(runtime_root),
            "research_context": research_context,
            "hypotheses": research_context.get("hypotheses", []),
            "max_experiments": args.max_experiments,
            "experiment_duration": args.experiment_duration,
            "python": os.environ.get("ML_RESEARCH_LOOP_PYTHON", sys.executable),
        },
    )
    review = call_tool(
        "review_research_results",
        {"task_id": TASK_ID, "runtime_root": str(runtime_root)},
    )

    payload = {
        "status": review.get("status"),
        "runtime_root": str(runtime_root),
        "task_file": str(task_file),
        "result_file": review.get("result_file"),
        "program_file": str(runtime_root / "workdir" / TASK_ID / "program.md"),
        "tool_chain": [
            "research_task",
            "propose_hypotheses",
            "run_hypothesis_experiment",
            "review_research_results",
        ],
        "research_context": research_context,
        "run": {
            "status": run_payload.get("status"),
            "returncode": run_payload.get("returncode"),
            "experiments": run_payload.get("experiments"),
        },
        "review": review,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
