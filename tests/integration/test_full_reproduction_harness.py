from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from lib.full_reproduction_harness import (
    FullReproductionRunConfig,
    prepare_fasttext_mini_dataset,
    run_fasttext_baseline_alignment,
    run_fasttext_style_baseline,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TARGET_SPEC = PROJECT_ROOT / "docs" / "reproduction-pilot" / "full-reproduction-target.json"


def test_prepare_fasttext_mini_dataset_writes_provenance_and_supervised_files(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "run"

    artifacts = prepare_fasttext_mini_dataset(
        target_spec_path=TARGET_SPEC,
        output_dir=output_dir,
    )

    train_text = artifacts["train_fasttext"].read_text(encoding="utf-8")
    test_text = artifacts["test_fasttext"].read_text(encoding="utf-8")
    provenance = json.loads(artifacts["dataset_provenance"].read_text(encoding="utf-8"))

    assert "__label__world" in train_text
    assert "__label__business" in train_text
    assert "__label__sports" in test_text
    assert provenance["paper_id"] == "arxiv:1607.01759"
    assert provenance["format"] == "fasttext_supervised"
    assert provenance["train_count"] >= 8
    assert provenance["test_count"] >= 4
    assert provenance["official_scores_claimed"] is False


def test_run_fasttext_style_baseline_writes_reports_and_handoff(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    prepare_fasttext_mini_dataset(target_spec_path=TARGET_SPEC, output_dir=output_dir)

    result = run_fasttext_style_baseline(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=output_dir,
            max_train_seconds=30,
        )
    )

    baseline_report = json.loads((output_dir / "baseline-report.json").read_text())
    evaluation_report = json.loads((output_dir / "evaluation-report.json").read_text())
    handoff = json.loads((output_dir / "client-handoff.json").read_text())

    assert result["status"] == "completed"
    assert result["accuracy"] >= 0.75
    assert result["official_scores_claimed"] is False
    assert baseline_report["execution_mode"] == "python_fasttext_style_fallback"
    assert baseline_report["official_fasttext_binary"] is False
    assert baseline_report["metric_name"] == "accuracy"
    assert evaluation_report["accuracy"] == result["accuracy"]
    assert evaluation_report["test_count"] >= 4
    assert handoff["recommended_next_action"] == "run_controlled_improvement_patch"
    assert "official_benchmark_or_sota" in handoff["blocked_claims"]


def test_full_reproduction_run_cli_executes_p1_harness(tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-run"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/full_reproduction_run.py",
            "--target-spec",
            str(TARGET_SPEC),
            "--output-dir",
            str(output_dir),
            "--run-baseline",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "completed"
    assert payload["paper_id"] == "arxiv:1607.01759"
    assert payload["accuracy"] >= 0.75
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "dataset-provenance.json").exists()
    assert (output_dir / "baseline-report.json").exists()
    assert (output_dir / "evaluation-report.json").exists()
    assert (output_dir / "client-handoff.json").exists()


def test_run_fasttext_baseline_alignment_writes_p2_gap_report(tmp_path: Path) -> None:
    output_dir = tmp_path / "alignment-run"

    result = run_fasttext_baseline_alignment(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=output_dir,
            max_train_seconds=30,
        ),
        repeat_count=3,
    )

    alignment_report = json.loads((output_dir / "alignment-report.json").read_text())
    reruns_report = json.loads((output_dir / "baseline-reruns.json").read_text())
    handoff = json.loads((output_dir / "client-handoff.json").read_text())

    assert result["status"] == "completed"
    assert result["stage"] == "p2_baseline_alignment"
    assert result["official_scores_claimed"] is False
    assert alignment_report["paper_reference"]["paper_id"] == "arxiv:1607.01759"
    assert alignment_report["dataset"]["version"] == "ag_news_reference_slice_v1"
    assert alignment_report["commands"]["training"] == "fasttext supervised -input train.txt -output model"
    assert alignment_report["commands"]["evaluation"] == "fasttext test model.bin test.txt"
    assert alignment_report["local_baseline"]["repeat_count"] == 3
    assert alignment_report["local_baseline"]["mean_accuracy"] >= 0.75
    assert alignment_report["local_baseline"]["stable"] is True
    assert alignment_report["claim_gap"]["status"] == "gap_remains"
    assert alignment_report["claim_gap"]["official_scores_claimed"] is False
    assert reruns_report["repeat_count"] == 3
    assert len(reruns_report["runs"]) == 3
    assert handoff["current_stage"] == "p2_baseline_alignment"
    assert handoff["recommended_next_action"] == "replace_reference_slice_with_full_public_dataset"


def test_full_reproduction_run_cli_executes_p2_alignment(tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-alignment-run"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/full_reproduction_run.py",
            "--target-spec",
            str(TARGET_SPEC),
            "--output-dir",
            str(output_dir),
            "--align-baseline",
            "--repeat-count",
            "3",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "completed"
    assert payload["stage"] == "p2_baseline_alignment"
    assert payload["paper_id"] == "arxiv:1607.01759"
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "alignment-report.json").exists()
    assert (output_dir / "baseline-reruns.json").exists()
