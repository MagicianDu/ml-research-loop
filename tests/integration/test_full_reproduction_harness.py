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
    run_fasttext_multi_proposal_loop,
    run_fasttext_patch_round,
    run_fasttext_style_baseline,
    write_fasttext_release_proof_bundle,
    write_fasttext_patch_round_proof_bundle,
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
                "    metric = '0.875' if '-wordNgrams' in sys.argv and sys.argv[sys.argv.index('-wordNgrams') + 1] == '2' else '0.750'",
                "    out.with_suffix('.bin').write_text(metric + '\\n', encoding='utf-8')",
                "    print('Read 8M words')",
                "    print('Number of words: 42')",
                "    raise SystemExit(0)",
                "if cmd == 'test':",
                "    metric = Path(sys.argv[2]).read_text(encoding='utf-8').strip() or '0.750'",
                "    print('N\\t4')",
                "    print(f'P@1\\t{metric}')",
                "    print(f'R@1\\t{metric}')",
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
    assert report["commands"]["training"][-4:] == ["-thread", "1", "-seed", "0"]
    assert report["dataset"]["source_urls"]["train"].endswith("/train.csv")
    assert report["dataset"]["source_urls"]["test"].endswith("/test.csv")
    assert set(report["dataset"]["actual_md5"]) == {"train", "test"}
    assert any(
        "selected fastText-compatible binary" in item
        for item in report["dataset"]["limitations"]
    )
    assert not any("python fallback" in item for item in report["dataset"]["limitations"])
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


def test_run_fasttext_patch_round_compares_to_baseline_and_archives_artifacts(
    tmp_path: Path,
) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_fake_fasttext_binary(tmp_path)
    baseline_dir = tmp_path / "baseline"
    patch_dir = tmp_path / "patch-round"
    baseline = run_fasttext_binary_baseline(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=baseline_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
    )

    result = run_fasttext_patch_round(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=patch_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
        baseline_report=Path(baseline["baseline_report"]),
        proposal={
            "proposal_id": "word-ngrams-2",
            "reason": "client model proposes bigram features after reviewing baseline errors",
            "train_args": {"-wordNgrams": 2},
        },
    )

    report = json.loads((patch_dir / "improvement-report.json").read_text())
    handoff = json.loads((patch_dir / "client-handoff.json").read_text())
    diff_text = (patch_dir / "patch-diff.patch").read_text(encoding="utf-8")

    assert result["status"] == "completed"
    assert result["stage"] == "p3_fasttext_patch_round"
    assert result["baseline_p_at_1"] == 0.75
    assert result["p_at_1"] == 0.875
    assert result["delta"] == 0.125
    assert result["improved"] is True
    assert result["official_scores_claimed"] is False
    assert report["proposal"]["validation_status"] == "accepted"
    assert report["proposal"]["train_args"] == {"-wordNgrams": 2}
    assert report["metric"]["improved"] is True
    assert report["loop_decision"]["decision"] == "continue_after_human_review"
    assert report["loop_decision"]["requires_human_confirmation"] is True
    assert "official_benchmark_or_sota" in report["claim_gap"]["blocked_claims"]
    assert "wordNgrams 2" in diff_text
    assert (patch_dir / "patch-proposal.json").exists()
    assert (patch_dir / "logs" / "fasttext-patch-train.log").exists()
    assert (patch_dir / "logs" / "fasttext-patch-test.log").exists()
    assert handoff["recommended_next_action"] == "review_patch_round_then_try_next_proposal"


def test_full_reproduction_run_cli_executes_fasttext_patch_round(
    tmp_path: Path,
) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_fake_fasttext_binary(tmp_path)
    baseline_dir = tmp_path / "cli-baseline"
    patch_dir = tmp_path / "cli-patch-round"
    proposal_file = tmp_path / "proposal.json"
    baseline = run_fasttext_binary_baseline(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=baseline_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
    )
    proposal_file.write_text(
        json.dumps({
            "proposal_id": "cli-word-ngrams-2",
            "reason": "exercise CLI P3 patch round",
            "train_args": {"wordNgrams": 2},
        }),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/full_reproduction_run.py",
            "--target-spec",
            str(TARGET_SPEC),
            "--output-dir",
            str(patch_dir),
            "--run-fasttext-patch-round",
            "--ag-news-train-csv",
            str(train_csv),
            "--ag-news-test-csv",
            str(test_csv),
            "--fasttext-binary",
            str(fake_binary),
            "--baseline-report",
            str(baseline["baseline_report"]),
            "--fasttext-proposal",
            str(proposal_file),
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "completed"
    assert payload["stage"] == "p3_fasttext_patch_round"
    assert payload["delta"] == 0.125
    assert payload["official_scores_claimed"] is False
    assert (patch_dir / "improvement-report.json").exists()
    assert (patch_dir / "patch-diff.patch").exists()


def test_write_fasttext_patch_round_proof_bundle_hashes_required_artifacts(
    tmp_path: Path,
) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_fake_fasttext_binary(tmp_path)
    baseline_dir = tmp_path / "baseline"
    patch_dir = tmp_path / "patch-round"
    proof_dir = tmp_path / "proof"
    baseline = run_fasttext_binary_baseline(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=baseline_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
    )
    run_fasttext_patch_round(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=patch_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
        baseline_report=Path(baseline["baseline_report"]),
        proposal={
            "proposal_id": "word-ngrams-2",
            "reason": "client model proposes bigram features after reviewing baseline errors",
            "train_args": {"-wordNgrams": 2},
        },
    )

    result = write_fasttext_patch_round_proof_bundle(
        patch_round_report=patch_dir / "improvement-report.json",
        output_dir=proof_dir,
        reviewer="p4-test-reviewer",
    )

    manifest = json.loads((proof_dir / "proof-manifest.json").read_text())
    human_review = json.loads((proof_dir / "human-review-report.json").read_text())
    artifact_index = json.loads((proof_dir / "artifact-index.json").read_text())
    sha_lines = (proof_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines()

    assert result["status"] == "completed"
    assert result["stage"] == "p4_fasttext_patch_proof_bundle"
    assert result["official_scores_claimed"] is False
    assert result["proof_manifest"] == str(proof_dir / "proof-manifest.json")
    assert manifest["review_status"] == "approved_with_limitations"
    assert manifest["metric_summary"]["delta"] == 0.125
    assert manifest["artifact_sha256"]["improvement_report"]
    assert manifest["artifact_sha256"]["patch_diff"]
    assert manifest["artifact_sha256"]["baseline_report"]
    assert artifact_index["artifact_count"] == len(artifact_index["artifacts"])
    assert human_review["reviewer"] == "p4-test-reviewer"
    assert human_review["official_scores_claimed"] is False
    assert "official_benchmark_or_sota" in human_review["blocked_public_claims"]
    assert any("artifacts/patch-diff.patch" in line for line in sha_lines)
    assert (proof_dir / "proof-summary.md").exists()


def test_write_fasttext_patch_round_proof_bundle_blocks_missing_artifact(
    tmp_path: Path,
) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_fake_fasttext_binary(tmp_path)
    baseline_dir = tmp_path / "baseline"
    patch_dir = tmp_path / "patch-round"
    proof_dir = tmp_path / "proof"
    baseline = run_fasttext_binary_baseline(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=baseline_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
    )
    run_fasttext_patch_round(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=patch_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
        baseline_report=Path(baseline["baseline_report"]),
        proposal={
            "proposal_id": "word-ngrams-2",
            "reason": "client model proposes bigram features after reviewing baseline errors",
            "train_args": {"-wordNgrams": 2},
        },
    )
    (patch_dir / "patch-diff.patch").unlink()

    result = write_fasttext_patch_round_proof_bundle(
        patch_round_report=patch_dir / "improvement-report.json",
        output_dir=proof_dir,
        reviewer="p4-test-reviewer",
    )

    assert result["status"] == "blocked"
    assert "patch_diff" in result["missing_artifacts"]
    assert result["official_scores_claimed"] is False
    assert not (proof_dir / "proof-manifest.json").exists()


def test_full_reproduction_run_cli_writes_fasttext_patch_proof_bundle(
    tmp_path: Path,
) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_fake_fasttext_binary(tmp_path)
    baseline_dir = tmp_path / "cli-baseline"
    patch_dir = tmp_path / "cli-patch-round"
    proof_dir = tmp_path / "cli-proof"
    baseline = run_fasttext_binary_baseline(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=baseline_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
    )
    run_fasttext_patch_round(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=patch_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
        baseline_report=Path(baseline["baseline_report"]),
        proposal={
            "proposal_id": "cli-proof-word-ngrams-2",
            "reason": "exercise CLI P4 proof bundle",
            "train_args": {"wordNgrams": 2},
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/full_reproduction_run.py",
            "--target-spec",
            str(TARGET_SPEC),
            "--output-dir",
            str(proof_dir),
            "--write-fasttext-patch-proof-bundle",
            "--patch-round-report",
            str(patch_dir / "improvement-report.json"),
            "--reviewer",
            "p4-cli-reviewer",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "completed"
    assert payload["stage"] == "p4_fasttext_patch_proof_bundle"
    assert payload["official_scores_claimed"] is False
    assert (proof_dir / "proof-manifest.json").exists()
    assert (proof_dir / "human-review-report.json").exists()


def test_run_fasttext_multi_proposal_loop_records_failure_and_rollback(
    tmp_path: Path,
) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_fake_fasttext_binary(tmp_path)
    baseline_dir = tmp_path / "baseline"
    multi_dir = tmp_path / "multi-round"
    baseline = run_fasttext_binary_baseline(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=baseline_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
    )

    result = run_fasttext_multi_proposal_loop(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=multi_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
        baseline_report=Path(baseline["baseline_report"]),
        proposals=[
            {
                "proposal_id": "good-bigram",
                "reason": "client model proposes bigram features",
                "train_args": {"wordNgrams": 2},
            },
            {
                "proposal_id": "bad-arg",
                "reason": "client model tried a non-allowlisted argument",
                "train_args": {"bucket": 100},
            },
        ],
    )

    report = json.loads((multi_dir / "multi-round-report.json").read_text())
    handoff = json.loads((multi_dir / "client-handoff.json").read_text())

    assert result["status"] == "completed_with_failures"
    assert result["stage"] == "p5_fasttext_multi_proposal_loop"
    assert result["best_metric"] == 0.875
    assert result["failure_count"] == 1
    assert result["rollback_summary"]["rollback_events"] == 1
    assert result["official_scores_claimed"] is False
    assert report["rounds"][0]["status"] == "completed"
    assert report["rounds"][1]["status"] == "failed"
    assert report["rounds"][1]["rollback_action"] == "keep_best_so_far"
    assert handoff["recommended_next_action"] == "package_release_proof_for_review"
    assert (multi_dir / "rounds" / "round-001-good-bigram" / "improvement-report.json").exists()


def test_write_fasttext_release_proof_bundle_creates_download_and_review_files(
    tmp_path: Path,
) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_fake_fasttext_binary(tmp_path)
    baseline_dir = tmp_path / "baseline"
    patch_dir = tmp_path / "patch-round"
    proof_dir = tmp_path / "proof"
    multi_dir = tmp_path / "multi-round"
    release_dir = tmp_path / "release-proof"
    baseline = run_fasttext_binary_baseline(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=baseline_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
    )
    run_fasttext_patch_round(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=patch_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
        baseline_report=Path(baseline["baseline_report"]),
        proposal={
            "proposal_id": "word-ngrams-2",
            "reason": "client model proposes bigram features after reviewing baseline errors",
            "train_args": {"wordNgrams": 2},
        },
    )
    write_fasttext_patch_round_proof_bundle(
        patch_round_report=patch_dir / "improvement-report.json",
        output_dir=proof_dir,
        reviewer="p5-test-reviewer",
    )
    run_fasttext_multi_proposal_loop(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=multi_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
        baseline_report=Path(baseline["baseline_report"]),
        proposals=[
            {
                "proposal_id": "good-bigram",
                "reason": "client model proposes bigram features",
                "train_args": {"wordNgrams": 2},
            },
            {
                "proposal_id": "bad-arg",
                "reason": "client model tried a non-allowlisted argument",
                "train_args": {"bucket": 100},
            },
        ],
    )

    result = write_fasttext_release_proof_bundle(
        proof_manifest=proof_dir / "proof-manifest.json",
        output_dir=release_dir,
        multi_round_report=multi_dir / "multi-round-report.json",
        reviewer="p5-test-reviewer",
    )

    manifest = json.loads((release_dir / "release-proof-manifest.json").read_text())
    checksum_text = (release_dir / "release-proof-bundle.sha256").read_text(
        encoding="utf-8"
    )

    assert result["status"] == "completed"
    assert result["stage"] == "p5_fasttext_release_proof_bundle"
    assert result["download_bundle"].endswith(".tar.gz")
    assert result["bundle_sha256"]
    assert result["official_scores_claimed"] is False
    assert manifest["multi_round_summary"]["failure_count"] == 1
    assert manifest["download_artifact"]["sha256"] == result["bundle_sha256"]
    assert "release-proof-bundle.tar.gz" in checksum_text
    assert (release_dir / "release-review-checklist.md").exists()
    assert (release_dir / "release-proof-manifest.json").exists()
    assert (release_dir / "release-proof-bundle.tar.gz").exists()


def test_full_reproduction_run_cli_executes_fasttext_multi_proposal_loop(
    tmp_path: Path,
) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_fake_fasttext_binary(tmp_path)
    baseline_dir = tmp_path / "cli-baseline"
    multi_dir = tmp_path / "cli-multi-round"
    proposals_file = tmp_path / "proposals.json"
    baseline = run_fasttext_binary_baseline(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=baseline_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
    )
    proposals_file.write_text(
        json.dumps({
            "proposals": [
                {
                    "proposal_id": "cli-good-bigram",
                    "reason": "exercise CLI P5 multi-round",
                    "train_args": {"wordNgrams": 2},
                },
                {
                    "proposal_id": "cli-bad-arg",
                    "reason": "exercise CLI P5 failure capture",
                    "train_args": {"bucket": 100},
                },
            ]
        }),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/full_reproduction_run.py",
            "--target-spec",
            str(TARGET_SPEC),
            "--output-dir",
            str(multi_dir),
            "--run-fasttext-multi-proposal-loop",
            "--ag-news-train-csv",
            str(train_csv),
            "--ag-news-test-csv",
            str(test_csv),
            "--fasttext-binary",
            str(fake_binary),
            "--baseline-report",
            str(baseline["baseline_report"]),
            "--fasttext-proposals",
            str(proposals_file),
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "completed_with_failures"
    assert payload["stage"] == "p5_fasttext_multi_proposal_loop"
    assert payload["best_metric"] == 0.875
    assert payload["failure_count"] == 1
    assert payload["official_scores_claimed"] is False
    assert (multi_dir / "multi-round-report.json").exists()


def test_full_reproduction_run_cli_writes_fasttext_release_proof_bundle(
    tmp_path: Path,
) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_fake_fasttext_binary(tmp_path)
    baseline_dir = tmp_path / "cli-baseline"
    patch_dir = tmp_path / "cli-patch-round"
    proof_dir = tmp_path / "cli-proof"
    multi_dir = tmp_path / "cli-multi-round"
    release_dir = tmp_path / "cli-release-proof"
    baseline = run_fasttext_binary_baseline(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=baseline_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
    )
    run_fasttext_patch_round(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=patch_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
        baseline_report=Path(baseline["baseline_report"]),
        proposal={
            "proposal_id": "cli-proof-word-ngrams-2",
            "reason": "exercise CLI P5 release bundle",
            "train_args": {"wordNgrams": 2},
        },
    )
    write_fasttext_patch_round_proof_bundle(
        patch_round_report=patch_dir / "improvement-report.json",
        output_dir=proof_dir,
        reviewer="p5-cli-reviewer",
    )
    run_fasttext_multi_proposal_loop(
        FullReproductionRunConfig(
            target_spec_path=TARGET_SPEC,
            output_dir=multi_dir,
            max_train_seconds=30,
        ),
        train_csv=train_csv,
        test_csv=test_csv,
        fasttext_binary=fake_binary,
        baseline_report=Path(baseline["baseline_report"]),
        proposals=[
            {
                "proposal_id": "cli-good-bigram",
                "reason": "exercise CLI P5 release bundle",
                "train_args": {"wordNgrams": 2},
            },
            {
                "proposal_id": "cli-bad-arg",
                "reason": "exercise CLI P5 release bundle failure path",
                "train_args": {"bucket": 100},
            },
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/full_reproduction_run.py",
            "--target-spec",
            str(TARGET_SPEC),
            "--output-dir",
            str(release_dir),
            "--write-fasttext-release-proof-bundle",
            "--proof-manifest",
            str(proof_dir / "proof-manifest.json"),
            "--multi-round-report",
            str(multi_dir / "multi-round-report.json"),
            "--reviewer",
            "p5-cli-reviewer",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "completed"
    assert payload["stage"] == "p5_fasttext_release_proof_bundle"
    assert payload["official_scores_claimed"] is False
    assert (release_dir / "release-proof-bundle.tar.gz").exists()
    assert (release_dir / "release-proof-bundle.sha256").exists()
