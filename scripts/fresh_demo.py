#!/usr/bin/env python3
"""Run a fresh, repeatable synthetic autoresearch demo."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a fresh synthetic demo in an isolated runtime root")
    parser.add_argument("--max-experiments", type=int, default=1)
    parser.add_argument("--experiment-duration", type=int, default=30)
    parser.add_argument("--runtime-root", type=Path, default=None)
    return parser.parse_args()


def _make_runtime_root(runtime_root: Path | None) -> Path:
    if runtime_root is not None:
        root = runtime_root.expanduser().resolve()
    else:
        root = PROJECT_ROOT / ".demo_runs" / f"fresh-demo-{uuid.uuid4().hex[:8]}"
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    return root


def _write_task(runtime_root: Path, max_experiments: int, experiment_duration: int) -> Path:
    task_id = "fresh-demo"
    task_file = runtime_root / "tasks" / f"{task_id}.json"
    task = {
        "task_id": task_id,
        "objective": "minimize val_bpb on synthetic data",
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


def main() -> int:
    args = parse_args()
    runtime_root = _make_runtime_root(args.runtime_root)
    task_file = _write_task(runtime_root, args.max_experiments, args.experiment_duration)
    workspace = runtime_root / "workdir" / "fresh-demo"

    site_packages = PROJECT_ROOT / ".venv" / "lib" / "python3.13" / "site-packages"
    existing_pythonpath = os.environ.get("PYTHONPATH")
    pythonpath_parts = [str(PROJECT_ROOT), str(site_packages)]
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)

    env = {
        **os.environ,
        "ML_RESEARCH_LOOP_ROOT": str(runtime_root),
        "ML_RESEARCH_LOOP_PYTHON": os.environ.get("ML_RESEARCH_LOOP_PYTHON", sys.executable),
        "PYTHONPATH": os.pathsep.join(pythonpath_parts),
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "autoresearch_run.py"),
            "--task-config",
            str(task_file),
            "--workspace",
            str(workspace),
            "--max-experiments",
            str(args.max_experiments),
            "--experiment-duration",
            str(args.experiment_duration),
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=max(90, args.experiment_duration + 60),
    )

    if proc.returncode != 0:
        print(proc.stdout, end="")
        return proc.returncode

    result_file = runtime_root / "results" / "fresh-demo.json"
    result = json.loads(result_file.read_text(encoding="utf-8"))
    print(json.dumps({
        "status": result.get("status"),
        "runtime_root": str(runtime_root),
        "result_file": str(result_file),
        "best_result": result.get("best_result"),
        "summary": result.get("summary"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
