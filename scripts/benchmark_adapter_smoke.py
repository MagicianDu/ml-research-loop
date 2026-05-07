#!/usr/bin/env python3
"""Run both benchmark adapter compatibility demos and summarize artifacts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from lib.benchmarks import build_benchmark_readiness


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run benchmark adapter compatibility smoke")
    parser.add_argument("--runtime-root", type=Path, default=None)
    parser.add_argument("--python", default=os.environ.get("ML_RESEARCH_LOOP_PYTHON", sys.executable))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_root = _runtime_root(args.runtime_root)
    env = {
        **os.environ,
        "ML_RESEARCH_LOOP_PYTHON": args.python,
    }

    mle_result = _run_json_script(
        name="mle_bench",
        command=[
            args.python,
            str(PROJECT_ROOT / "scripts" / "mle_bench_adapter_demo.py"),
            "--runtime-root",
            str(runtime_root / "mle-bench"),
            "--python",
            args.python,
            "--json",
        ],
        env=env,
    )
    paperbench_result = _run_json_script(
        name="paperbench",
        command=[
            args.python,
            str(PROJECT_ROOT / "scripts" / "paperbench_adapter_demo.py"),
            "--runtime-root",
            str(runtime_root / "paperbench"),
            "--json",
        ],
        env=env,
    )
    results = [
        _summarize_mle_result(mle_result),
        _summarize_paperbench_result(paperbench_result),
    ]
    status = "passed" if all(result["ok"] for result in results) else "failed"
    payload = {
        "status": status,
        "official_scores_claimed": False,
        "runtime_root": str(runtime_root),
        "readiness": build_benchmark_readiness(),
        "results": results,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status == "passed" else 1


def _runtime_root(runtime_root: Path | None) -> Path:
    root = runtime_root or PROJECT_ROOT / ".demo_runs" / f"benchmark-smoke-{uuid.uuid4().hex[:8]}"
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _run_json_script(
    *,
    name: str,
    command: list[str],
    env: dict[str, str],
) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=180,
        check=False,
    )
    payload: dict[str, Any] | None = None
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout.splitlines()[-1])
        except json.JSONDecodeError:
            payload = None
    return {
        "name": name,
        "returncode": proc.returncode,
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-20:]),
        "payload": payload,
    }


def _summarize_mle_result(result: dict[str, Any]) -> dict[str, Any]:
    payload = result["payload"] or {}
    ok = (
        result["returncode"] == 0
        and payload.get("status") == "completed"
        and payload.get("official_mle_bench") is False
    )
    return {
        "name": "mle_bench",
        "ok": ok,
        "status": payload.get("status", "failed"),
        "returncode": result["returncode"],
        "official_mle_bench": payload.get("official_mle_bench"),
        "competition_id": payload.get("competition_id"),
        "submission_path": payload.get("submission_path"),
        "metadata_path": payload.get("metadata_path"),
        "benchmark_report_path": payload.get("benchmark_report_path"),
        "best_metric": payload.get("best_metric"),
        "stdout_tail": result["stdout_tail"] if not ok else "",
    }


def _summarize_paperbench_result(result: dict[str, Any]) -> dict[str, Any]:
    payload = result["payload"] or {}
    grading = payload.get("grading") if isinstance(payload.get("grading"), dict) else {}
    ok = (
        result["returncode"] == 0
        and payload.get("status") == "passed"
        and payload.get("official_paperbench") is False
        and float(grading.get("score", 0.0)) > 0
    )
    return {
        "name": "paperbench",
        "ok": ok,
        "status": payload.get("status", "failed"),
        "returncode": result["returncode"],
        "official_paperbench": payload.get("official_paperbench"),
        "paper_id": payload.get("paper_id"),
        "submission_dir": payload.get("submission_dir"),
        "reproduction_report_path": payload.get("reproduction_report_path"),
        "grade_report_path": payload.get("grade_report_path"),
        "benchmark_report_path": payload.get("benchmark_report_path"),
        "grading_score": grading.get("score"),
        "stdout_tail": result["stdout_tail"] if not ok else "",
    }


if __name__ == "__main__":
    raise SystemExit(main())
