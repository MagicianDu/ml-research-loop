from __future__ import annotations

from pathlib import Path

from lib.benchmarks.paperbench import (
    build_paperbench_report,
    build_reproduction_spec,
    grade_paperbench_fixture,
    materialize_paperbench_fixture,
)


def test_materialize_fixture_writes_paperbench_shaped_submission(tmp_path: Path) -> None:
    fixture = materialize_paperbench_fixture(tmp_path)

    assert fixture.paper_id == "mlrl-debug-paper"
    assert fixture.paper_metadata["venue"] == "PaperBench compatibility fixture"
    assert fixture.official_paperbench is False
    assert fixture.submission_dir.exists()
    assert (fixture.submission_dir / "train.py").exists()
    assert (fixture.submission_dir / "program.md").exists()
    assert sorted(fixture.required_files) == ["program.md", "train.py"]


def test_reproduction_spec_maps_fixture_to_existing_schema(tmp_path: Path) -> None:
    fixture = materialize_paperbench_fixture(tmp_path)

    spec = build_reproduction_spec(fixture, fixture.submission_dir)

    assert spec.mode == "local_command"
    assert spec.command[-1] == "train.py"
    assert spec.required_files == ["train.py", "program.md"]
    assert spec.to_dict()["timeout_seconds"] == 30


def test_grade_fixture_reports_rubric_leaf_results(tmp_path: Path) -> None:
    fixture = materialize_paperbench_fixture(tmp_path)

    grade_report = grade_paperbench_fixture(
        fixture=fixture,
        submission_dir=fixture.submission_dir,
        reproduction_status="completed",
    )

    assert grade_report["score"] > 0
    assert grade_report["num_leaf_nodes"] == 3
    leaf_ids = [
        node["id"]
        for node in grade_report["graded_task_tree"]["graded_leaf_nodes"]
    ]
    assert leaf_ids == ["code.train", "code.program", "run.completed"]


def test_benchmark_report_preserves_stage_statuses_and_paths(tmp_path: Path) -> None:
    fixture = materialize_paperbench_fixture(tmp_path)
    reproduction_report_path = tmp_path / "reproduction-report.json"
    grade_report_path = tmp_path / "grade-report.json"
    benchmark_report_path = tmp_path / "paperbench-report.json"
    grade_report = grade_paperbench_fixture(
        fixture=fixture,
        submission_dir=fixture.submission_dir,
        reproduction_status="completed",
    )

    report = build_paperbench_report(
        fixture=fixture,
        submission_dir=fixture.submission_dir,
        reproduction_report_path=reproduction_report_path,
        grade_report_path=grade_report_path,
        benchmark_report_path=benchmark_report_path,
        grade_report=grade_report,
        task_file=tmp_path / "tasks" / "mlrl-debug-paper.json",
        result_file=tmp_path / "results" / "mlrl-debug-paper.json",
        reproduction_status="completed",
    )

    assert report["status"] == "passed"
    assert report["official_paperbench"] is False
    assert report["paper_id"] == fixture.paper_id
    assert report["agent_rollout"]["status"] == "completed"
    assert report["reproduction"]["status"] == "completed"
    assert report["grading"]["status"] == "completed"
    assert report["submission_dir"] == str(fixture.submission_dir)
    assert report["reproduction_report_path"] == str(reproduction_report_path)
    assert report["grade_report_path"] == str(grade_report_path)
    assert report["benchmark_report_path"] == str(benchmark_report_path)
    assert report["grading"]["rubric_leaf_results"][0]["id"] == "code.train"
