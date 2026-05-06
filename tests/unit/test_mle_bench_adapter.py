from __future__ import annotations

import csv
import json
from pathlib import Path

from lib.benchmarks.mle_bench import (
    build_mle_bench_report,
    materialize_mle_bench_fixture,
    write_mle_bench_submission,
)


def test_materialize_mle_bench_fixture_writes_competition_files(tmp_path: Path) -> None:
    fixture = materialize_mle_bench_fixture(tmp_path / "runtime")

    competition_dir = Path(fixture["competition_dir"])
    task = json.loads(Path(fixture["task_file"]).read_text(encoding="utf-8"))

    assert fixture["competition_id"] == "mlrl-byte-lm"
    assert fixture["official_mle_bench"] is False
    assert fixture["metric"]["name"] == "val_bpb"
    assert fixture["metric"]["direction"] == "minimize"
    assert competition_dir.name == "mlrl-byte-lm"
    assert Path(fixture["train_csv"]).exists()
    assert Path(fixture["test_csv"]).exists()
    assert Path(fixture["sample_submission_csv"]).exists()
    assert "local deterministic fixture" in Path(fixture["instructions_file"]).read_text(
        encoding="utf-8"
    )
    assert task["competition_id"] == "mlrl-byte-lm"
    assert task["official_mle_bench"] is False
    assert task["metric"]["name"] == "val_bpb"


def test_write_mle_bench_submission_matches_sample_submission_columns(tmp_path: Path) -> None:
    fixture = materialize_mle_bench_fixture(tmp_path / "runtime")
    submission_path = write_mle_bench_submission(
        fixture=fixture,
        best_metric={"name": "val_bpb", "value": 1.25, "experiment_id": "exp-001"},
    )

    with Path(fixture["sample_submission_csv"]).open(newline="", encoding="utf-8") as handle:
        sample_header = next(csv.reader(handle))
    with Path(submission_path).open(newline="", encoding="utf-8") as handle:
        submission_rows = list(csv.reader(handle))

    assert submission_rows[0] == sample_header
    assert submission_rows[1:] == [["mlrl-byte-lm", "1.25"]]


def test_build_mle_bench_report_preserves_future_official_adapter_fields(
    tmp_path: Path,
) -> None:
    fixture = materialize_mle_bench_fixture(tmp_path / "runtime")
    submission_path = write_mle_bench_submission(
        fixture=fixture,
        best_metric={"name": "val_bpb", "value": 1.25, "experiment_id": "exp-001"},
    )
    metadata_path = tmp_path / "runtime" / "mle-bench" / "run-groups" / "demo" / "metadata.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text("{}", encoding="utf-8")

    report = build_mle_bench_report(
        fixture=fixture,
        run_group="demo",
        submission_path=submission_path,
        metadata_path=metadata_path,
        task_file=Path(fixture["task_file"]),
        result_file=tmp_path / "runtime" / "results" / "demo-byte-lm-smoke.json",
        best_metric={"name": "val_bpb", "value": 1.25, "experiment_id": "exp-001"},
    )

    assert report["status"] == "completed"
    assert report["official_mle_bench"] is False
    assert report["competition_id"] == "mlrl-byte-lm"
    assert report["run_group"] == "mlrl-byte-lm-local"
    assert report["submission_path"] == str(submission_path)
    assert report["metadata_path"] == str(metadata_path)
    assert report["task_file"] == fixture["task_file"]
    assert report["best_metric"]["value"] == 1.25
    assert "mlebench grade" in report["grade_command_hint"]
