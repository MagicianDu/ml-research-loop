"""Deterministic PaperBench-shaped adapter for local reproduction spikes."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lib.reproduction_protocol import (
    ReproductionSpec,
    RubricTask,
    build_grade_report,
)


DEFAULT_PAPER_ID = "mlrl-debug-paper"
REQUIRED_FILES = ["train.py", "program.md"]


@dataclass(frozen=True)
class PaperBenchFixture:
    """Local PaperBench-shaped fixture materialized for one debug paper."""

    paper_id: str
    paper_metadata: dict[str, Any]
    paper_summary: str
    rubric: RubricTask
    required_files: list[str]
    runtime_root: Path
    submission_dir: Path
    official_paperbench: bool = False


def materialize_paperbench_fixture(
    runtime_root: Path,
    paper_id: str = DEFAULT_PAPER_ID,
) -> PaperBenchFixture:
    """Create a deterministic submission scaffold for a debug PaperBench paper."""
    root = runtime_root.expanduser().resolve()
    submission_dir = root / "paperbench" / paper_id / "submission"
    submission_dir.mkdir(parents=True, exist_ok=True)
    (submission_dir / "train.py").write_text(_train_py_source(), encoding="utf-8")
    (submission_dir / "program.md").write_text(_program_md_source(), encoding="utf-8")

    metadata = {
        "title": "ML Research Loop Debug Reproduction",
        "venue": "PaperBench compatibility fixture",
        "year": 2026,
        "split": "debug",
    }
    summary = (
        "A dependency-free local fixture that mimics PaperBench reproduction "
        "handoff data without claiming an official PaperBench score."
    )
    return PaperBenchFixture(
        paper_id=paper_id,
        paper_metadata=metadata,
        paper_summary=summary,
        rubric=_build_debug_rubric(),
        required_files=list(REQUIRED_FILES),
        runtime_root=root,
        submission_dir=submission_dir,
        official_paperbench=False,
    )


def build_reproduction_spec(
    fixture: PaperBenchFixture,
    submission_dir: Path,
    timeout_seconds: int = 30,
) -> ReproductionSpec:
    """Map the PaperBench fixture onto the existing reproduction spec schema."""
    python = os.environ.get("ML_RESEARCH_LOOP_PYTHON", sys.executable)
    return ReproductionSpec(
        mode="local_command",
        command=[python, "train.py"],
        timeout_seconds=timeout_seconds,
        required_files=list(fixture.required_files),
    )


def grade_paperbench_fixture(
    fixture: PaperBenchFixture,
    submission_dir: Path,
    reproduction_status: str,
) -> dict[str, Any]:
    """Grade the deterministic fixture from local file and run status evidence."""
    leaf_scores = {
        "code.train": 1.0 if (submission_dir / "train.py").is_file() else 0.0,
        "code.program": 1.0 if (submission_dir / "program.md").is_file() else 0.0,
        "run.completed": 1.0 if reproduction_status == "completed" else 0.0,
    }
    return build_grade_report(
        rubric=fixture.rubric,
        leaf_scores=leaf_scores,
        grader_log=(
            "Deterministic PaperBench compatibility grade; "
            "official_paperbench=false."
        ),
    )


def build_paperbench_report(
    *,
    fixture: PaperBenchFixture,
    submission_dir: Path,
    reproduction_report_path: Path,
    grade_report_path: Path,
    benchmark_report_path: Path,
    grade_report: dict[str, Any],
    task_file: Path,
    result_file: Path,
    reproduction_status: str,
    reproduction_log_path: Path | None = None,
) -> dict[str, Any]:
    """Build a stage-aware benchmark report for research handoff."""
    required_file_results = _required_file_results(fixture.required_files, submission_dir)
    valid_required_files = [
        item["path"] for item in required_file_results if item["exists"]
    ]
    missing_required_files = [
        item["path"] for item in required_file_results if not item["exists"]
    ]
    grade_status = "completed" if "score" in grade_report else "failed"
    status = (
        "passed"
        if reproduction_status == "completed"
        and grade_status == "completed"
        and float(grade_report.get("score", 0.0)) > 0
        else "failed"
    )
    rubric_leaf_results = (
        grade_report.get("graded_task_tree", {}).get("graded_leaf_nodes", [])
        if isinstance(grade_report.get("graded_task_tree"), dict)
        else []
    )

    return {
        "status": status,
        "official_paperbench": fixture.official_paperbench,
        "paper_id": fixture.paper_id,
        "paper_metadata": fixture.paper_metadata,
        "paper_summary": fixture.paper_summary,
        "submission_dir": str(submission_dir),
        "reproduction_report_path": str(reproduction_report_path),
        "grade_report_path": str(grade_report_path),
        "benchmark_report_path": str(benchmark_report_path),
        "task_file": str(task_file),
        "result_file": str(result_file),
        "agent_rollout": {
            "status": "completed",
            "required_files": required_file_results,
            "valid_required_files": valid_required_files,
            "missing_required_files": missing_required_files,
        },
        "reproduction": {
            "status": reproduction_status,
            "log_path": str(reproduction_log_path) if reproduction_log_path else None,
        },
        "grading": {
            "status": grade_status,
            "score": grade_report.get("score"),
            "rubric_leaf_results": rubric_leaf_results,
        },
        "next_actions": _next_actions(missing_required_files, reproduction_status),
    }


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write a deterministic JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _build_debug_rubric() -> RubricTask:
    return RubricTask(
        id="root",
        requirements="PaperBench-shaped debug reproduction should be runnable.",
        weight=1,
        sub_tasks=[
            RubricTask(
                id="code.train",
                requirements="Submission includes an executable train.py.",
                weight=1,
                task_category="Code Development",
            ),
            RubricTask(
                id="code.program",
                requirements="Submission includes a program.md handoff.",
                weight=1,
                task_category="Code Development",
            ),
            RubricTask(
                id="run.completed",
                requirements="Local reproduction command completes successfully.",
                weight=1,
                task_category="Code Execution",
            ),
        ],
    )


def _required_file_results(
    required_files: list[str],
    submission_dir: Path,
) -> list[dict[str, Any]]:
    return [
        {
            "path": required_file,
            "exists": (submission_dir / required_file).is_file(),
        }
        for required_file in required_files
    ]


def _next_actions(
    missing_required_files: list[str],
    reproduction_status: str,
) -> list[str]:
    actions: list[str] = []
    if missing_required_files:
        actions.append("Add missing required files before grading.")
    if reproduction_status != "completed":
        actions.append("Inspect reproduction logs and rerun the local command.")
    if not actions:
        actions.append("Use this report as a Codex or Claude reproduction handoff.")
    return actions


def _train_py_source() -> str:
    return """\
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    output = {
        "metric": "debug_accuracy",
        "value": 0.91,
        "status": "completed",
    }
    Path("result.json").write_text(json.dumps(output, sort_keys=True), encoding="utf-8")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
"""


def _program_md_source() -> str:
    return """\
# ML Research Loop Debug Reproduction

This is a deterministic local submission for the PaperBench adapter spike.
It is not an official PaperBench submission and must be reported with
`official_paperbench=false`.
"""
