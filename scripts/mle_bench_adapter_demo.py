#!/usr/bin/env python3
"""Run the deterministic MLE-bench adapter compatibility spike."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from lib.benchmarks.mle_bench import (
    DEFAULT_RUN_GROUP,
    build_mle_bench_report,
    materialize_mle_bench_fixture,
    write_mle_bench_submission,
)
from lib.demo_templates import run_demo_template


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local MLE-bench-shaped adapter fixture."
    )
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-experiments", type=int, default=1)
    parser.add_argument("--experiment-duration", type=int, default=30)
    parser.add_argument(
        "--python",
        default=os.environ.get("ML_RESEARCH_LOOP_PYTHON", sys.executable),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_root = args.runtime_root.expanduser().resolve()
    fixture = materialize_mle_bench_fixture(runtime_root)
    demo_result = run_demo_template(
        template_name="byte-lm-smoke",
        runtime_root=runtime_root,
        project_root=PROJECT_ROOT,
        max_experiments=args.max_experiments,
        experiment_duration=args.experiment_duration,
        python_executable=args.python,
    )

    best_metric = demo_result.get("best_metric")
    submission_path = write_mle_bench_submission(
        fixture=fixture,
        best_metric=best_metric,
    )
    run_group_dir = Path(fixture["run_group_dir"])
    metadata_path = run_group_dir / "metadata.json"
    report_path = run_group_dir / "benchmark_report.json"
    metadata = {
        "status": demo_result["status"],
        "official_mle_bench": False,
        "competition_id": fixture["competition_id"],
        "run_group": DEFAULT_RUN_GROUP,
        "runtime_root": str(runtime_root),
        "workspace": demo_result["workspace"],
        "task_file": demo_result["task_file"],
        "adapter_task_file": fixture["task_file"],
        "result_file": demo_result["result_file"],
        "submission_path": str(submission_path),
        "best_metric": best_metric,
        "template": demo_result["template"],
        "returncode": demo_result["returncode"],
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report = build_mle_bench_report(
        fixture=fixture,
        run_group=DEFAULT_RUN_GROUP,
        submission_path=submission_path,
        metadata_path=metadata_path,
        task_file=Path(demo_result["task_file"]),
        result_file=Path(demo_result["result_file"]),
        best_metric=best_metric,
        status=demo_result["status"],
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    payload = {
        **report,
        "benchmark_report_path": str(report_path),
        "runtime_root": str(runtime_root),
        "workspace": demo_result["workspace"],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if demo_result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
