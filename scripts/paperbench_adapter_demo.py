#!/usr/bin/env python3
"""Run a deterministic PaperBench-shaped adapter demo."""

from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from pathlib import Path

from lib.benchmarks.paperbench import (
    build_paperbench_report,
    build_reproduction_spec,
    grade_paperbench_fixture,
    materialize_paperbench_fixture,
    write_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PaperBench adapter demo")
    parser.add_argument("--runtime-root", type=Path, default=None)
    parser.add_argument("--paper-id", default="mlrl-debug-paper")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def make_runtime_root(runtime_root: Path | None) -> Path:
    root = runtime_root or PROJECT_ROOT / ".demo_runs" / _default_run_id()
    root = root.expanduser().resolve()
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    (root / "results").mkdir(parents=True, exist_ok=True)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    return root


def main() -> int:
    args = parse_args()
    runtime_root = make_runtime_root(args.runtime_root)
    fixture = materialize_paperbench_fixture(runtime_root, paper_id=args.paper_id)
    spec = build_reproduction_spec(fixture, fixture.submission_dir)

    task_file = runtime_root / "tasks" / f"{fixture.paper_id}.json"
    result_file = runtime_root / "results" / f"{fixture.paper_id}.json"
    reproduction_report_path = (
        runtime_root / "reports" / "reproduction-report.json"
    )
    grade_report_path = runtime_root / "reports" / "grade-report.json"
    benchmark_report_path = runtime_root / "reports" / "paperbench-report.json"
    reproduction_log_path = runtime_root / "reports" / "reproduction.log"

    write_json(task_file, _build_task_payload(fixture, spec))
    run_result = _run_reproduction(spec.command, fixture.submission_dir)
    reproduction_status = "completed" if run_result.returncode == 0 else "failed"
    reproduction_log_path.write_text(
        _format_reproduction_log(run_result),
        encoding="utf-8",
    )
    reproduction_report = {
        "status": reproduction_status,
        "official_paperbench": False,
        "paper_id": fixture.paper_id,
        "submission_dir": str(fixture.submission_dir),
        "reproduction_spec": spec.to_dict(),
        "returncode": run_result.returncode,
        "stdout": run_result.stdout,
        "stderr": run_result.stderr,
        "log_path": str(reproduction_log_path),
    }
    write_json(reproduction_report_path, reproduction_report)
    write_json(
        result_file,
        {
            "status": reproduction_status,
            "paper_id": fixture.paper_id,
            "reproduction_report_path": str(reproduction_report_path),
        },
    )

    grade_report = grade_paperbench_fixture(
        fixture=fixture,
        submission_dir=fixture.submission_dir,
        reproduction_status=reproduction_status,
    )
    write_json(grade_report_path, grade_report)

    benchmark_report = build_paperbench_report(
        fixture=fixture,
        submission_dir=fixture.submission_dir,
        reproduction_report_path=reproduction_report_path,
        grade_report_path=grade_report_path,
        benchmark_report_path=benchmark_report_path,
        grade_report=grade_report,
        task_file=task_file,
        result_file=result_file,
        reproduction_status=reproduction_status,
        reproduction_log_path=reproduction_log_path,
    )
    write_json(benchmark_report_path, benchmark_report)

    if args.json:
        print(json.dumps(benchmark_report, ensure_ascii=False))
    else:
        print(json.dumps(benchmark_report, indent=2, ensure_ascii=False))
    return 0 if benchmark_report["status"] == "passed" else 1


def _build_task_payload(fixture, spec) -> dict:
    return {
        "task_id": fixture.paper_id,
        "benchmark": "paperbench_compatibility_spike",
        "official_paperbench": False,
        "paper_metadata": fixture.paper_metadata,
        "paper_summary": fixture.paper_summary,
        "rubric": fixture.rubric.to_dict(),
        "reproduction_spec": spec.to_dict(),
    }


def _run_reproduction(
    command: list[str],
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )


def _format_reproduction_log(run_result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        [
            f"returncode={run_result.returncode}",
            "[stdout]",
            run_result.stdout,
            "[stderr]",
            run_result.stderr,
        ]
    )


def _default_run_id() -> str:
    return f"paperbench-adapter-{uuid.uuid4().hex[:8]}"


if __name__ == "__main__":
    raise SystemExit(main())
