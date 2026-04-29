#!/usr/bin/env python3
"""Run an MCP hypothesis experiment against a real local byte dataset."""

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
TASK_ID = "mcp-real-data"
OBJECTIVE = "minimize val_bpb on a local byte dataset"
FIXTURE_SOURCE = {
    "source_type": "paper",
    "title": "Attention Is All You Need",
    "url": "https://arxiv.org/abs/1706.03762",
    "summary": "Transformer architecture reference for compact sequence modeling experiments.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MCP demo using a real local dataset file")
    parser.add_argument("--runtime-root", type=Path, default=None)
    parser.add_argument("--max-experiments", type=int, default=1)
    parser.add_argument("--experiment-duration", type=int, default=30)
    return parser.parse_args()


def make_runtime_root(runtime_root: Path | None) -> Path:
    root = runtime_root or PROJECT_ROOT / ".demo_runs" / f"mcp-real-data-{uuid.uuid4().hex[:8]}"
    root = root.expanduser().resolve()
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    return root


def write_dataset(runtime_root: Path) -> Path:
    dataset_file = runtime_root / "data" / "tiny_real_64_64.bin"
    payload = bytes((index * 17 + 11) % 64 for index in range(4096))
    dataset_file.write_bytes(payload)
    return dataset_file


def write_task(
    runtime_root: Path,
    dataset_file: Path,
    max_experiments: int,
    experiment_duration: int,
) -> Path:
    task_file = runtime_root / "tasks" / f"{TASK_ID}.json"
    task = {
        "task_id": TASK_ID,
        "objective": OBJECTIVE,
        "dataset": {"name": "tiny-real-bytes", "path": str(dataset_file)},
        "metric": {"name": "val_bpb", "direction": "minimize", "threshold": 0.0},
        "hyperparameter_space": {
            "batch_size": {"type": "choice", "values": [1]},
            "depth": {"type": "choice", "values": [1]},
            "dim": {"type": "choice", "values": [16]},
            "window_size": {"type": "choice", "values": [64]},
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
    dataset_file = write_dataset(runtime_root)
    task_file = write_task(
        runtime_root=runtime_root,
        dataset_file=dataset_file,
        max_experiments=args.max_experiments,
        experiment_duration=args.experiment_duration,
    )
    workspace = runtime_root / "workdir" / TASK_ID
    research_context = build_research_context()
    run_payload = call_tool(
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
    review = call_tool(
        "review_research_results",
        {
            "task_id": TASK_ID,
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
        },
    )
    log_file = workspace / "logs" / "exp-001.log"
    log_text = log_file.read_text(encoding="utf-8") if log_file.exists() else ""
    loaded_real_dataset = "[train.py] Data loaded: 4096 bytes" in log_text
    data_source = (
        "real_file"
        if loaded_real_dataset and "Data not found" not in log_text
        else "synthetic_fallback"
    )
    payload = {
        "status": review.get("status"),
        "runtime_root": str(runtime_root),
        "task_file": str(task_file),
        "dataset_file": str(dataset_file),
        "data_source": data_source,
        "result_file": review.get("result_file"),
        "log_file": str(log_file),
        "run": {
            "status": run_payload.get("status"),
            "returncode": run_payload.get("returncode"),
            "experiments": run_payload.get("experiments"),
        },
        "review": review,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "completed" and data_source == "real_file" else 1


if __name__ == "__main__":
    raise SystemExit(main())
