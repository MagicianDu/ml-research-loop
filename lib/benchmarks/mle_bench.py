"""Dependency-free MLE-bench compatibility spike helpers."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_COMPETITION_ID = "mlrl-byte-lm"
DEFAULT_RUN_GROUP = "mlrl-byte-lm-local"
OFFICIAL_MLE_BENCH = False


@dataclass(frozen=True)
class MLEBenchFixture:
    """Paths and metadata for the deterministic local MLE-bench-shaped fixture."""

    competition_id: str
    runtime_root: Path
    competition_dir: Path
    train_csv: Path
    test_csv: Path
    sample_submission_csv: Path
    instructions_file: Path
    task_file: Path
    run_group_dir: Path
    metric: dict[str, str]

    def as_payload(self) -> dict[str, Any]:
        return {
            "competition_id": self.competition_id,
            "official_mle_bench": OFFICIAL_MLE_BENCH,
            "runtime_root": str(self.runtime_root),
            "competition_dir": str(self.competition_dir),
            "train_csv": str(self.train_csv),
            "test_csv": str(self.test_csv),
            "sample_submission_csv": str(self.sample_submission_csv),
            "instructions_file": str(self.instructions_file),
            "task_file": str(self.task_file),
            "run_group_dir": str(self.run_group_dir),
            "metric": self.metric,
        }


def materialize_mle_bench_fixture(
    runtime_root: Path,
    competition_id: str = DEFAULT_COMPETITION_ID,
) -> dict[str, Any]:
    """Write a deterministic local competition fixture and adapter task file."""
    runtime_root = runtime_root.expanduser().resolve()
    competition_dir = runtime_root / "mle-bench" / "competitions" / competition_id
    run_group_dir = runtime_root / "mle-bench" / "run-groups" / DEFAULT_RUN_GROUP
    task_dir = runtime_root / "tasks"
    competition_dir.mkdir(parents=True, exist_ok=True)
    run_group_dir.mkdir(parents=True, exist_ok=True)
    task_dir.mkdir(parents=True, exist_ok=True)

    train_csv = competition_dir / "train.csv"
    test_csv = competition_dir / "test.csv"
    sample_submission_csv = competition_dir / "sample_submission.csv"
    instructions_file = competition_dir / "instructions.md"
    task_file = task_dir / f"{competition_id}.json"
    metric = {"name": "val_bpb", "direction": "minimize"}

    _write_csv(
        train_csv,
        ["row_id", "bytes", "val_bpb"],
        [
            ["train-001", "11 28 45 62", "1.40"],
            ["train-002", "15 32 49 02", "1.30"],
        ],
    )
    _write_csv(
        test_csv,
        ["row_id", "bytes"],
        [["mlrl-byte-lm", "11 28 45 62"]],
    )
    _write_csv(
        sample_submission_csv,
        ["competition_id", "val_bpb"],
        [[competition_id, "0.0"]],
    )
    instructions_file.write_text(
        "\n".join([
            f"# {competition_id}",
            "",
            "This is a local deterministic fixture for the MLE-bench adapter spike.",
            "It is not an official MLE-bench competition or leaderboard submission.",
            "Produce `submission.csv` with the same columns as `sample_submission.csv`.",
            "",
        ]),
        encoding="utf-8",
    )
    task_file.write_text(
        json.dumps(
            {
                "task_id": competition_id,
                "competition_id": competition_id,
                "official_mle_bench": OFFICIAL_MLE_BENCH,
                "description": "MLE-bench-shaped local byte-LM fixture.",
                "instructions_file": str(instructions_file),
                "data": {
                    "train_csv": str(train_csv),
                    "test_csv": str(test_csv),
                    "sample_submission_csv": str(sample_submission_csv),
                },
                "metric": metric,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return MLEBenchFixture(
        competition_id=competition_id,
        runtime_root=runtime_root,
        competition_dir=competition_dir,
        train_csv=train_csv,
        test_csv=test_csv,
        sample_submission_csv=sample_submission_csv,
        instructions_file=instructions_file,
        task_file=task_file,
        run_group_dir=run_group_dir,
        metric=metric,
    ).as_payload()


def write_mle_bench_submission(
    *,
    fixture: dict[str, Any],
    best_metric: dict[str, Any] | None,
) -> Path:
    """Write `submission.csv` using the fixture sample-submission schema."""
    sample_submission = Path(fixture["sample_submission_csv"])
    submission_path = Path(fixture["run_group_dir"]) / "submission.csv"
    submission_path.parent.mkdir(parents=True, exist_ok=True)
    metric_value = _metric_value(best_metric)

    with sample_submission.open(newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))

    row = {
        "competition_id": str(fixture["competition_id"]),
        str(fixture["metric"]["name"]): _format_metric(metric_value),
    }
    with submission_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerow({column: row[column] for column in header})
    return submission_path


def build_mle_bench_report(
    *,
    fixture: dict[str, Any],
    run_group: str,
    submission_path: Path,
    metadata_path: Path,
    task_file: Path,
    result_file: Path,
    best_metric: dict[str, Any] | None,
    status: str = "completed",
) -> dict[str, Any]:
    """Build the JSON report schema for the compatibility spike."""
    run_group_name = DEFAULT_RUN_GROUP if run_group == "demo" else run_group
    return {
        "status": status,
        "official_mle_bench": OFFICIAL_MLE_BENCH,
        "competition_id": fixture["competition_id"],
        "run_group": run_group_name,
        "submission_path": str(submission_path),
        "metadata_path": str(metadata_path),
        "grade_command_hint": (
            "mlebench grade --run-group "
            f"{run_group_name} --competition {fixture['competition_id']}"
        ),
        "task_file": str(task_file),
        "result_file": str(result_file),
        "best_metric": best_metric,
    }


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _metric_value(best_metric: dict[str, Any] | None) -> float:
    if not best_metric or best_metric.get("value") is None:
        return 0.0
    return float(best_metric["value"])


def _format_metric(value: float) -> str:
    return str(value)
