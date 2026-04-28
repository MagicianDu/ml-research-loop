#!/usr/bin/env python3
"""Run an end-to-end ml-intern research brief to autoresearch validation demo."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from lib.research_protocol import ResearchBrief, ResearchHypothesis, ResearchSource


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a fresh research-to-validation fusion demo")
    parser.add_argument("--runtime-root", type=Path, default=None)
    parser.add_argument("--max-experiments", type=int, default=1)
    parser.add_argument("--experiment-duration", type=int, default=30)
    return parser.parse_args()


def make_runtime_root(runtime_root: Path | None) -> Path:
    if runtime_root is not None:
        root = runtime_root.expanduser().resolve()
    else:
        root = PROJECT_ROOT / ".demo_runs" / f"fusion-demo-{uuid.uuid4().hex[:8]}"
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    return root


def build_research_brief() -> ResearchBrief:
    hypothesis = ResearchHypothesis(
        hypothesis_id="hyp-001",
        title="Validate shallow-depth synthetic baseline",
        rationale=(
            "A controlled first pass should validate that research context reaches "
            "autoresearch before broader architecture edits."
        ),
        expected_metric="val_bpb",
        expected_direction="minimize",
        proposed_changes=["keep DEPTH in the SEARCH REGION and test a deterministic baseline"],
        risk_notes=["synthetic demo validates plumbing, not model quality"],
    )
    return ResearchBrief(
        objective="minimize val_bpb on synthetic data",
        sources=[
            ResearchSource(
                source_type="paper",
                title="Attention Is All You Need",
                url="https://arxiv.org/abs/1706.03762",
                summary="Transformer architecture reference for attention experiments.",
            )
        ],
        hypotheses=[hypothesis],
    )


def write_task(
    runtime_root: Path,
    research_brief: ResearchBrief,
    max_experiments: int,
    experiment_duration: int,
) -> Path:
    task_id = "fusion-demo"
    task_file = runtime_root / "tasks" / f"{task_id}.json"
    task = {
        "task_id": task_id,
        "objective": research_brief.objective,
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
        "research_context": research_brief.to_dict(),
        "hypotheses": [hypothesis.to_dict() for hypothesis in research_brief.hypotheses],
    }
    task_file.write_text(json.dumps(task, indent=2, ensure_ascii=False), encoding="utf-8")
    return task_file


def subprocess_env(runtime_root: Path) -> dict[str, str]:
    site_packages = PROJECT_ROOT / ".venv" / "lib" / "python3.13" / "site-packages"
    existing_pythonpath = os.environ.get("PYTHONPATH")
    pythonpath_parts = [str(PROJECT_ROOT), str(site_packages)]
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)

    return {
        **os.environ,
        "ML_RESEARCH_LOOP_ROOT": str(runtime_root),
        "ML_RESEARCH_LOOP_PYTHON": os.environ.get("ML_RESEARCH_LOOP_PYTHON", sys.executable),
        "PYTHONPATH": os.pathsep.join(pythonpath_parts),
    }


def run_autoresearch(
    task_file: Path,
    runtime_root: Path,
    max_experiments: int,
    experiment_duration: int,
) -> subprocess.CompletedProcess[str]:
    workspace = runtime_root / "workdir" / "fusion-demo"
    return subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "autoresearch_run.py"),
            "--task-config",
            str(task_file),
            "--workspace",
            str(workspace),
            "--max-experiments",
            str(max_experiments),
            "--experiment-duration",
            str(experiment_duration),
        ],
        cwd=PROJECT_ROOT,
        env=subprocess_env(runtime_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=max(120, experiment_duration * max_experiments + 90),
    )


def main() -> int:
    args = parse_args()
    runtime_root = make_runtime_root(args.runtime_root)
    research_brief = build_research_brief()
    task_file = write_task(
        runtime_root,
        research_brief,
        max_experiments=args.max_experiments,
        experiment_duration=args.experiment_duration,
    )

    proc = run_autoresearch(
        task_file,
        runtime_root,
        max_experiments=args.max_experiments,
        experiment_duration=args.experiment_duration,
    )
    if proc.returncode != 0:
        print(proc.stdout, end="")
        return proc.returncode

    result_file = runtime_root / "results" / "fusion-demo.json"
    result = json.loads(result_file.read_text(encoding="utf-8"))
    payload = {
        "status": result.get("status"),
        "runtime_root": str(runtime_root),
        "task_file": str(task_file),
        "program_file": str(runtime_root / "workdir" / "fusion-demo" / "program.md"),
        "result_file": str(result_file),
        "research_brief": research_brief.to_dict(),
        "best_result": result.get("best_result"),
        "summary": result.get("summary"),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
