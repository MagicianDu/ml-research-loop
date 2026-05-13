from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from lib.full_reproduction_harness import (
    FullReproductionRunConfig,
    prepare_ag_news_csv_dataset,
    prepare_fasttext_mini_dataset,
    probe_fasttext_runtime,
    run_fasttext_baseline_alignment,
    run_fasttext_binary_baseline,
    run_fasttext_full_data_alignment,
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


def _write_ag_news_fixture_csvs(tmp_path: Path) -> tuple[Path, Path]:
    train_csv = tmp_path / "train.csv"
    test_csv = tmp_path / "test.csv"
    train_csv.write_text(
        "\n".join(
            [
                '"1","Leaders discuss treaty","Foreign ministers opened regional peace talks"',
                '"2","Team wins final","Players celebrated the championship game victory"',
                '"3","Stocks rise","Investors watched revenue growth and bank profits"',
                '"4","New processor released","Software teams tested neural chips and cloud tools"',
                '"1","Election talks continue","Diplomats reviewed the neighboring government vote"',
                '"2","Coach praises players","The league club reached the tournament playoffs"',
                '"3","Company reports profit","Shares moved higher after quarterly earnings"',
                '"4","Browser update ships","Developers patched security flaws in mobile software"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    test_csv.write_text(
        "\n".join(
            [
                '"1","Regional vote monitored","Diplomats and observers discussed election talks"',
                '"2","Club wins match","The league team won the final championship game"',
                '"3","Market watches earnings","Banks and investors reviewed company revenue"',
                '"4","Cloud platform update","Software developers improved processor tools"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return train_csv, test_csv


def test_prepare_ag_news_csv_dataset_converts_public_csv_to_fasttext(tmp_path: Path) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    output_dir = tmp_path / "ag-news-run"

    artifacts = prepare_ag_news_csv_dataset(
        target_spec_path=TARGET_SPEC,
        output_dir=output_dir,
        train_csv=train_csv,
        test_csv=test_csv,
    )

    train_text = artifacts["train_fasttext"].read_text(encoding="utf-8")
    test_text = artifacts["test_fasttext"].read_text(encoding="utf-8")
    provenance = json.loads(artifacts["dataset_provenance"].read_text(encoding="utf-8"))

    assert "__label__world" in train_text
    assert "__label__sports" in test_text
    assert "__label__business" in train_text
    assert "__label__sci_tech" in test_text
    assert provenance["source_kind"] == "ag_news_csv"
    assert provenance["version"] == "ag_news_csv_local_v1"
    assert provenance["train_count"] == 8
    assert provenance["test_count"] == 4
    assert provenance["official_scores_claimed"] is False


def test_probe_fasttext_runtime_reports_binary_and_python_package(tmp_path: Path) -> None:
    fake_binary = tmp_path / "fasttext"
    fake_binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_binary.chmod(0o755)

    probe = probe_fasttext_runtime(explicit_binary=fake_binary)

    assert probe["status"] in {"official_binary_available", "python_package_available"}
    assert probe["binary"]["available"] is True
    assert probe["binary"]["path"] == str(fake_binary)
    assert probe["official_scores_claimed"] is False


def test_run_fasttext_full_data_alignment_writes_toolchain_gap_report(tmp_path: Path) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    output_dir = tmp_path / "full-data-alignment"

    result = run_fasttext_full_data_alignment(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=output_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=tmp_path / "missing-fasttext",
        repeat_count=3,
    )

    report = json.loads((output_dir / "full-data-alignment-report.json").read_text())
    toolchain_probe = json.loads((output_dir / "fasttext-runtime-probe.json").read_text())
    handoff = json.loads((output_dir / "client-handoff.json").read_text())

    assert result["status"] == "completed"
    assert result["stage"] == "p2_plus_full_data_alignment"
    assert result["official_scores_claimed"] is False
    assert report["dataset"]["source_kind"] == "ag_news_csv"
    assert report["dataset"]["train_count"] == 8
    assert report["paper_target"]["metric_name"] == "accuracy"
    assert report["paper_target"]["target_accuracy"] == 0.924
    assert report["paper_target"]["tolerance"] == 0.02
    assert report["toolchain"]["official_fasttext_binary_available"] is False
    assert report["local_baseline"]["repeat_count"] == 3
    assert report["claim_gap"]["status"] == "gap_remains"
    assert toolchain_probe["official_scores_claimed"] is False
    assert handoff["current_stage"] == "p2_plus_full_data_alignment"
    assert handoff["recommended_next_action"] == "run_official_fasttext_or_python_package"


def test_full_reproduction_run_cli_executes_p2_plus_full_data_alignment(
    tmp_path: Path,
) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    output_dir = tmp_path / "cli-full-data-alignment"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/full_reproduction_run.py",
            "--target-spec",
            str(TARGET_SPEC),
            "--output-dir",
            str(output_dir),
            "--align-full-data",
            "--ag-news-train-csv",
            str(train_csv),
            "--ag-news-test-csv",
            str(test_csv),
            "--fasttext-binary",
            str(tmp_path / "missing-fasttext"),
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
    assert payload["stage"] == "p2_plus_full_data_alignment"
    assert payload["paper_id"] == "arxiv:1607.01759"
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "full-data-alignment-report.json").exists()
    assert (output_dir / "fasttext-runtime-probe.json").exists()


def _write_fake_fasttext_binary(tmp_path: Path) -> Path:
    binary = tmp_path / "fasttext"
    binary.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import sys",
                "cmd = sys.argv[1]",
                "if cmd == 'supervised':",
                "    out = Path(sys.argv[sys.argv.index('-output') + 1])",
                "    out.with_suffix('.bin').write_text('fake model\\n', encoding='utf-8')",
                "    print('Read 8M words')",
                "    print('Number of words: 42')",
                "    raise SystemExit(0)",
                "if cmd == 'test':",
                "    print('N\\t4')",
                "    print('P@1\\t0.750')",
                "    print('R@1\\t0.750')",
                "    raise SystemExit(0)",
                "raise SystemExit(2)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return binary


def test_run_fasttext_binary_baseline_archives_logs_and_parses_p_at_1(
    tmp_path: Path,
) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_fake_fasttext_binary(tmp_path)
    output_dir = tmp_path / "binary-baseline"

    result = run_fasttext_binary_baseline(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=output_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
    )

    report = json.loads((output_dir / "fasttext-baseline-report.json").read_text())
    handoff = json.loads((output_dir / "client-handoff.json").read_text())

    assert result["status"] == "completed"
    assert result["stage"] == "p2_plus_fasttext_binary_baseline"
    assert result["official_scores_claimed"] is False
    assert report["execution"]["training_returncode"] == 0
    assert report["execution"]["evaluation_returncode"] == 0
    assert report["metric"]["name"] == "accuracy"
    assert report["metric"]["p_at_1"] == 0.75
    assert report["paper_target"]["target_accuracy"] == 0.924
    assert report["claim_gap"]["status"] == "gap_remains"
    assert (output_dir / "logs" / "fasttext-train.log").exists()
    assert (output_dir / "logs" / "fasttext-test.log").exists()
    assert handoff["current_stage"] == "p2_plus_fasttext_binary_baseline"
    assert handoff["recommended_next_action"] == "review_fasttext_baseline_gap"


def test_full_reproduction_run_cli_executes_fasttext_binary_baseline(
    tmp_path: Path,
) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_fake_fasttext_binary(tmp_path)
    output_dir = tmp_path / "cli-binary-baseline"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/full_reproduction_run.py",
            "--target-spec",
            str(TARGET_SPEC),
            "--output-dir",
            str(output_dir),
            "--run-fasttext-baseline",
            "--ag-news-train-csv",
            str(train_csv),
            "--ag-news-test-csv",
            str(test_csv),
            "--fasttext-binary",
            str(fake_binary),
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "completed"
    assert payload["stage"] == "p2_plus_fasttext_binary_baseline"
    assert payload["paper_id"] == "arxiv:1607.01759"
    assert payload["p_at_1"] == 0.75
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "fasttext-baseline-report.json").exists()
