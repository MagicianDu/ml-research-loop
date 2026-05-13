"""Harness for full-paper reproduction baseline runs."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
import shutil
from pathlib import Path
import re
import time
from typing import Any


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
AG_NEWS_LABELS = {
    "1": "world",
    "2": "sports",
    "3": "business",
    "4": "sci_tech",
}
AG_NEWS_SOURCE_URLS = {
    "train": "https://raw.githubusercontent.com/mhjabreel/CharCnn_Keras/master/data/ag_news_csv/train.csv",
    "test": "https://raw.githubusercontent.com/mhjabreel/CharCnn_Keras/master/data/ag_news_csv/test.csv",
}
AG_NEWS_EXPECTED_MD5 = {
    "train": None,
    "test": None,
}
AG_NEWS_EXPECTED_ROWS = {
    "train": 120000,
    "test": 7600,
}
FASTTEXT_AG_NEWS_PAPER_TARGET = {
    "metric_name": "accuracy",
    "target_accuracy": 0.924,
    "tolerance": 0.02,
    "source": "fastText supervised models page for ag news regular model",
}


@dataclass(frozen=True)
class FullReproductionRunConfig:
    """Execution config for a full reproduction baseline harness."""

    target_spec_path: Path
    output_dir: Path
    max_train_seconds: int = 300


def prepare_fasttext_mini_dataset(
    *,
    target_spec_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    """Write a deterministic text-classification mini slice and fastText files."""
    spec = _read_json(target_spec_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    records = _mini_text_classification_records()
    train_records = [record for record in records if record["split"] == "train"]
    test_records = [record for record in records if record["split"] == "test"]
    raw_jsonl = data_dir / "mini-text-classification.jsonl"
    train_fasttext = data_dir / "train.txt"
    test_fasttext = data_dir / "test.txt"
    provenance_path = output_dir / "dataset-provenance.json"

    raw_jsonl.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    train_fasttext.write_text(_render_fasttext_records(train_records), encoding="utf-8")
    test_fasttext.write_text(_render_fasttext_records(test_records), encoding="utf-8")
    _write_json(
        provenance_path,
        {
            "schema_version": "2026-05-13.full-reproduction-dataset.v1",
            "paper_id": spec["paper_id"],
            "paper_title": spec["title"],
            "dataset_track": spec["dataset_track"],
            "source_kind": "curated_public_text_classification_mini_slice",
            "source_url": spec["paper_url"],
            "format": "fasttext_supervised",
            "train_count": len(train_records),
            "test_count": len(test_records),
            "labels": sorted({record["label"] for record in records}),
            "raw_jsonl": raw_jsonl.relative_to(output_dir).as_posix(),
            "train_fasttext": train_fasttext.relative_to(output_dir).as_posix(),
            "test_fasttext": test_fasttext.relative_to(output_dir).as_posix(),
            "official_scores_claimed": False,
            "limitations": [
                "curated mini-slice for harness validation; not the full paper dataset",
                "python fallback classifier; not an official fastText binary result",
            ],
        },
    )
    return {
        "raw_jsonl": raw_jsonl,
        "train_fasttext": train_fasttext,
        "test_fasttext": test_fasttext,
        "dataset_provenance": provenance_path,
    }


def prepare_fasttext_reference_dataset(
    *,
    target_spec_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    """Write a deterministic AG-News-shaped reference slice for P2 alignment."""
    spec = _read_json(target_spec_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    records = _ag_news_reference_slice_records()
    train_records = [record for record in records if record["split"] == "train"]
    test_records = [record for record in records if record["split"] == "test"]
    raw_jsonl = data_dir / "ag-news-reference-slice.jsonl"
    train_fasttext = data_dir / "train.txt"
    test_fasttext = data_dir / "test.txt"
    provenance_path = output_dir / "dataset-provenance.json"

    raw_jsonl.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    train_fasttext.write_text(_render_fasttext_records(train_records), encoding="utf-8")
    test_fasttext.write_text(_render_fasttext_records(test_records), encoding="utf-8")
    _write_json(
        provenance_path,
        {
            "schema_version": "2026-05-13.full-reproduction-dataset.v1",
            "paper_id": spec["paper_id"],
            "paper_title": spec["title"],
            "dataset_track": spec["dataset_track"],
            "source_kind": "curated_ag_news_reference_slice",
            "version": "ag_news_reference_slice_v1",
            "format": "fasttext_supervised",
            "train_count": len(train_records),
            "test_count": len(test_records),
            "labels": sorted({record["label"] for record in records}),
            "raw_jsonl": raw_jsonl.relative_to(output_dir).as_posix(),
            "train_fasttext": train_fasttext.relative_to(output_dir).as_posix(),
            "test_fasttext": test_fasttext.relative_to(output_dir).as_posix(),
            "official_scores_claimed": False,
            "limitations": [
                "reference slice for baseline alignment; not the full AG News dataset",
                "handwritten public-domain examples using the AG News label schema",
                "python fallback classifier; not an official fastText binary result",
            ],
        },
    )
    return {
        "raw_jsonl": raw_jsonl,
        "train_fasttext": train_fasttext,
        "test_fasttext": test_fasttext,
        "dataset_provenance": provenance_path,
    }


def prepare_ag_news_csv_dataset(
    *,
    target_spec_path: Path,
    output_dir: Path,
    train_csv: Path,
    test_csv: Path,
) -> dict[str, Path]:
    """Convert AG News CSV files into fastText supervised input files."""
    spec = _read_json(target_spec_path)
    output_dir = output_dir.expanduser().resolve()
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    train_records = _read_ag_news_csv_records(train_csv, split="train")
    test_records = _read_ag_news_csv_records(test_csv, split="test")
    records = train_records + test_records
    raw_jsonl = data_dir / "ag-news-csv.jsonl"
    train_fasttext = data_dir / "train.txt"
    test_fasttext = data_dir / "test.txt"
    provenance_path = output_dir / "dataset-provenance.json"

    raw_jsonl.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    train_fasttext.write_text(_render_fasttext_records(train_records), encoding="utf-8")
    test_fasttext.write_text(_render_fasttext_records(test_records), encoding="utf-8")

    train_count = len(train_records)
    test_count = len(test_records)
    is_full_expected_size = (
        train_count == AG_NEWS_EXPECTED_ROWS["train"]
        and test_count == AG_NEWS_EXPECTED_ROWS["test"]
    )
    _write_json(
        provenance_path,
        {
            "schema_version": "2026-05-13.full-reproduction-dataset.v1",
            "paper_id": spec["paper_id"],
            "paper_title": spec["title"],
            "dataset_track": spec["dataset_track"],
            "source_kind": "ag_news_csv",
            "version": "ag_news_csv_local_v1",
            "format": "fasttext_supervised",
            "source_urls": AG_NEWS_SOURCE_URLS,
            "expected_md5": AG_NEWS_EXPECTED_MD5,
            "actual_md5": {
                "train": _md5_file(train_csv),
                "test": _md5_file(test_csv),
            },
            "hash_verification_status": "actual_hash_recorded_expected_hash_not_verified",
            "expected_rows": AG_NEWS_EXPECTED_ROWS,
            "train_count": train_count,
            "test_count": test_count,
            "is_full_expected_size": is_full_expected_size,
            "labels": sorted({record["label"] for record in records}),
            "raw_jsonl": raw_jsonl.relative_to(output_dir).as_posix(),
            "train_fasttext": train_fasttext.relative_to(output_dir).as_posix(),
            "test_fasttext": test_fasttext.relative_to(output_dir).as_posix(),
            "official_scores_claimed": False,
            "limitations": _ag_news_csv_limitations(is_full_expected_size),
        },
    )
    return {
        "raw_jsonl": raw_jsonl,
        "train_fasttext": train_fasttext,
        "test_fasttext": test_fasttext,
        "dataset_provenance": provenance_path,
    }


def probe_fasttext_runtime(
    *,
    explicit_binary: Path | None = None,
) -> dict[str, Any]:
    """Probe official fastText runtime availability without running training."""
    binary_path = _resolve_fasttext_binary(explicit_binary)
    python_package_spec = importlib.util.find_spec("fasttext")
    binary_available = binary_path is not None
    python_package_available = python_package_spec is not None
    if binary_available:
        status = "official_binary_available"
    elif python_package_available:
        status = "python_package_available"
    else:
        status = "fallback_only"
    return {
        "schema_version": "2026-05-13.fasttext-runtime-probe.v1",
        "status": status,
        "binary": {
            "available": binary_available,
            "path": str(binary_path) if binary_path else None,
            "source": "explicit" if explicit_binary else "PATH",
        },
        "python_package": {
            "available": python_package_available,
            "module": "fasttext" if python_package_available else None,
        },
        "fallback": {
            "available": True,
            "execution_mode": "python_fasttext_style_fallback",
        },
        "official_scores_claimed": False,
    }


def run_fasttext_style_baseline(config: FullReproductionRunConfig) -> dict[str, Any]:
    """Train and evaluate a deterministic fastText-style fallback baseline."""
    start_time = time.monotonic()
    spec = _read_json(config.target_spec_path)
    output_dir = config.output_dir.expanduser().resolve()
    data_dir = output_dir / "data"
    train_path = data_dir / "train.txt"
    test_path = data_dir / "test.txt"
    if not train_path.exists() or not test_path.exists():
        prepare_fasttext_mini_dataset(
            target_spec_path=config.target_spec_path,
            output_dir=output_dir,
        )

    train_records = _read_fasttext_records(train_path)
    test_records = _read_fasttext_records(test_path)
    model = _train_multinomial_baseline(train_records)
    predictions = [
        {
            "label": label,
            "prediction": _predict_label(model, text),
            "text": text,
        }
        for label, text in test_records
    ]
    correct = sum(1 for item in predictions if item["label"] == item["prediction"])
    accuracy = round(correct / len(predictions), 6)
    duration_seconds = round(time.monotonic() - start_time, 6)

    model_path = output_dir / "model.json"
    baseline_report_path = output_dir / "baseline-report.json"
    evaluation_report_path = output_dir / "evaluation-report.json"
    handoff_path = output_dir / "client-handoff.json"

    _write_json(model_path, _serializable_model(model))
    baseline_report = {
        "schema_version": "2026-05-13.full-reproduction-baseline.v1",
        "status": "completed",
        "paper_id": spec["paper_id"],
        "paper_title": spec["title"],
        "track_scope": spec["track_scope"],
        "execution_mode": "python_fasttext_style_fallback",
        "official_fasttext_binary": False,
        "baseline_command": spec["baseline_command"],
        "evaluation_command": spec["evaluation_command"],
        "metric_name": spec["primary_metric"],
        "accuracy": accuracy,
        "train_count": len(train_records),
        "test_count": len(test_records),
        "duration_seconds": duration_seconds,
        "model_artifact": model_path.relative_to(output_dir).as_posix(),
        "official_scores_claimed": False,
        "claim_boundary": (
            "P1 harness baseline only; not a full paper reproduction or official fastText score"
        ),
    }
    _write_json(baseline_report_path, baseline_report)
    _write_json(
        evaluation_report_path,
        {
            "schema_version": "2026-05-13.full-reproduction-evaluation.v1",
            "status": "completed",
            "paper_id": spec["paper_id"],
            "metric_name": spec["primary_metric"],
            "accuracy": accuracy,
            "correct": correct,
            "test_count": len(test_records),
            "predictions": predictions,
            "official_scores_claimed": False,
        },
    )
    _write_json(
        handoff_path,
        {
            "schema_version": "2026-05-13.full-reproduction-client-handoff.v1",
            "paper_id": spec["paper_id"],
            "current_stage": "p1_harness_baseline",
            "metric_name": spec["primary_metric"],
            "metric_value": accuracy,
            "recommended_next_action": "run_controlled_improvement_patch",
            "allowed_patch_scope": [
                "tokenization settings",
                "ngram feature extraction",
                "classifier hyperparameters",
                "training data split within the mini-slice",
            ],
            "blocked_claims": list(spec["blocked_claims"]),
            "official_scores_claimed": False,
        },
    )
    return {
        "status": "completed",
        "paper_id": spec["paper_id"],
        "accuracy": accuracy,
        "baseline_report": str(baseline_report_path),
        "evaluation_report": str(evaluation_report_path),
        "client_handoff": str(handoff_path),
        "official_scores_claimed": False,
    }


def run_fasttext_full_data_alignment(
    config: FullReproductionRunConfig,
    *,
    train_csv: Path,
    test_csv: Path,
    fasttext_binary: Path | None = None,
    repeat_count: int = 3,
) -> dict[str, Any]:
    """Run the P2+ full-data alignment path on provided AG News CSV files."""
    if repeat_count < 2:
        raise ValueError("repeat_count must be at least 2 for full-data alignment")

    output_dir = config.output_dir.expanduser().resolve()
    spec = _read_json(config.target_spec_path)
    artifacts = prepare_ag_news_csv_dataset(
        target_spec_path=config.target_spec_path,
        output_dir=output_dir,
        train_csv=train_csv,
        test_csv=test_csv,
    )
    provenance = _read_json(artifacts["dataset_provenance"])
    runtime_probe = probe_fasttext_runtime(explicit_binary=fasttext_binary)
    runtime_probe_path = output_dir / "fasttext-runtime-probe.json"
    _write_json(runtime_probe_path, runtime_probe)

    runs: list[dict[str, Any]] = []
    for index in range(repeat_count):
        baseline_result = run_fasttext_style_baseline(config)
        runs.append(
            {
                "run_id": f"repeat-{index + 1:03d}",
                "metric_name": spec["primary_metric"],
                "accuracy": baseline_result["accuracy"],
                "execution_mode": "python_fasttext_style_fallback",
                "official_scores_claimed": False,
            }
        )

    accuracies = [float(run["accuracy"]) for run in runs]
    mean_accuracy = round(sum(accuracies) / len(accuracies), 6)
    max_delta = round(max(accuracies) - min(accuracies), 6)
    stable = max_delta == 0

    reruns_report_path = output_dir / "baseline-reruns.json"
    alignment_report_path = output_dir / "full-data-alignment-report.json"
    handoff_path = output_dir / "client-handoff.json"

    _write_json(
        reruns_report_path,
        {
            "schema_version": "2026-05-13.full-reproduction-reruns.v1",
            "stage": "p2_plus_full_data_alignment",
            "paper_id": spec["paper_id"],
            "repeat_count": repeat_count,
            "metric_name": spec["primary_metric"],
            "runs": runs,
            "mean_accuracy": mean_accuracy,
            "max_delta": max_delta,
            "stable": stable,
            "official_scores_claimed": False,
        },
    )

    official_toolchain_ready = (
        runtime_probe["binary"]["available"] or runtime_probe["python_package"]["available"]
    )
    full_dataset_ready = bool(provenance["is_full_expected_size"])
    claim_gap_status = (
        "ready_for_official_baseline_run"
        if official_toolchain_ready and full_dataset_ready
        else "gap_remains"
    )
    missing_for_full_reproduction = _full_data_alignment_missing_items(
        full_dataset_ready=full_dataset_ready,
        official_toolchain_ready=official_toolchain_ready,
    )
    _write_json(
        alignment_report_path,
        {
            "schema_version": "2026-05-13.full-reproduction-full-data-alignment.v1",
            "status": "completed",
            "stage": "p2_plus_full_data_alignment",
            "paper_reference": {
                "paper_id": spec["paper_id"],
                "title": spec["title"],
                "paper_url": spec["paper_url"],
                "code_url": spec["code_url"],
                "target_claim": spec["target_claim"],
                "full_paper_claims_verified_locally": False,
            },
            "dataset": {
                "track": spec["dataset_track"],
                "source_kind": provenance["source_kind"],
                "version": provenance["version"],
                "format": provenance["format"],
                "train_count": provenance["train_count"],
                "test_count": provenance["test_count"],
                "expected_rows": provenance["expected_rows"],
                "is_full_expected_size": full_dataset_ready,
                "labels": provenance["labels"],
                "source_urls": provenance["source_urls"],
                "expected_md5": provenance["expected_md5"],
                "actual_md5": provenance["actual_md5"],
                "hash_verification_status": provenance["hash_verification_status"],
                "limitations": provenance["limitations"],
            },
            "toolchain": {
                "status": runtime_probe["status"],
                "official_fasttext_binary_available": runtime_probe["binary"]["available"],
                "python_package_available": runtime_probe["python_package"]["available"],
                "fallback_execution_mode": "python_fasttext_style_fallback",
                "probe_report": runtime_probe_path.relative_to(output_dir).as_posix(),
            },
            "commands": {
                "training": spec["baseline_command"],
                "evaluation": spec["evaluation_command"],
                "fallback_training": "python multinomial baseline over fastText-format train.txt",
                "fallback_evaluation": "python accuracy over fastText-format test.txt",
            },
            "paper_target": FASTTEXT_AG_NEWS_PAPER_TARGET,
            "local_baseline": {
                "metric_name": spec["primary_metric"],
                "repeat_count": repeat_count,
                "mean_accuracy": mean_accuracy,
                "max_delta": max_delta,
                "stable": stable,
                "reruns_report": reruns_report_path.relative_to(output_dir).as_posix(),
            },
            "claim_gap": {
                "status": claim_gap_status,
                "summary": _full_data_alignment_gap_summary(
                    full_dataset_ready=full_dataset_ready,
                    official_toolchain_ready=official_toolchain_ready,
                ),
                "missing_for_full_reproduction": missing_for_full_reproduction,
                "blocked_claims": list(spec["blocked_claims"]),
                "official_scores_claimed": False,
            },
            "official_scores_claimed": False,
        },
    )
    _write_json(
        handoff_path,
        {
            "schema_version": "2026-05-13.full-reproduction-client-handoff.v1",
            "paper_id": spec["paper_id"],
            "current_stage": "p2_plus_full_data_alignment",
            "metric_name": spec["primary_metric"],
            "metric_value": mean_accuracy,
            "stable": stable,
            "recommended_next_action": "run_official_fasttext_or_python_package",
            "allowed_patch_scope": [
                "install or select official fastText binary",
                "install or select equivalent Python fastText package",
                "download full AG News CSV files from recorded source URLs",
                "run official baseline and compare with target tolerance",
            ],
            "blocked_claims": list(spec["blocked_claims"]),
            "official_scores_claimed": False,
        },
    )
    return {
        "status": "completed",
        "stage": "p2_plus_full_data_alignment",
        "paper_id": spec["paper_id"],
        "accuracy": mean_accuracy,
        "stable": stable,
        "full_dataset_ready": full_dataset_ready,
        "official_toolchain_ready": official_toolchain_ready,
        "alignment_report": str(alignment_report_path),
        "runtime_probe": str(runtime_probe_path),
        "client_handoff": str(handoff_path),
        "official_scores_claimed": False,
    }


def run_fasttext_baseline_alignment(
    config: FullReproductionRunConfig,
    *,
    repeat_count: int = 3,
) -> dict[str, Any]:
    """Run the P2 repeatable baseline-alignment check and write gap artifacts."""
    if repeat_count < 2:
        raise ValueError("repeat_count must be at least 2 for baseline alignment")

    output_dir = config.output_dir.expanduser().resolve()
    spec = _read_json(config.target_spec_path)
    artifacts = prepare_fasttext_reference_dataset(
        target_spec_path=config.target_spec_path,
        output_dir=output_dir,
    )
    provenance = _read_json(artifacts["dataset_provenance"])

    runs: list[dict[str, Any]] = []
    for index in range(repeat_count):
        baseline_result = run_fasttext_style_baseline(config)
        runs.append(
            {
                "run_id": f"repeat-{index + 1:03d}",
                "metric_name": spec["primary_metric"],
                "accuracy": baseline_result["accuracy"],
                "official_scores_claimed": False,
            }
        )

    accuracies = [float(run["accuracy"]) for run in runs]
    mean_accuracy = round(sum(accuracies) / len(accuracies), 6)
    max_delta = round(max(accuracies) - min(accuracies), 6)
    stable = max_delta == 0

    reruns_report_path = output_dir / "baseline-reruns.json"
    alignment_report_path = output_dir / "alignment-report.json"
    handoff_path = output_dir / "client-handoff.json"

    _write_json(
        reruns_report_path,
        {
            "schema_version": "2026-05-13.full-reproduction-reruns.v1",
            "stage": "p2_baseline_alignment",
            "paper_id": spec["paper_id"],
            "repeat_count": repeat_count,
            "metric_name": spec["primary_metric"],
            "runs": runs,
            "mean_accuracy": mean_accuracy,
            "max_delta": max_delta,
            "stable": stable,
            "official_scores_claimed": False,
        },
    )
    alignment_report = {
        "schema_version": "2026-05-13.full-reproduction-alignment.v1",
        "status": "completed",
        "stage": "p2_baseline_alignment",
        "paper_reference": {
            "paper_id": spec["paper_id"],
            "title": spec["title"],
            "paper_url": spec["paper_url"],
            "code_url": spec["code_url"],
            "target_claim": spec["target_claim"],
            "core_track": "supervised text classification",
            "full_paper_claims_verified_locally": False,
        },
        "dataset": {
            "track": spec["dataset_track"],
            "version": provenance["version"],
            "source_kind": provenance["source_kind"],
            "format": provenance["format"],
            "train_count": provenance["train_count"],
            "test_count": provenance["test_count"],
            "labels": provenance["labels"],
            "limitations": provenance["limitations"],
        },
        "commands": {
            "training": spec["baseline_command"],
            "evaluation": spec["evaluation_command"],
            "local_execution_mode": "python_fasttext_style_fallback",
        },
        "local_baseline": {
            "metric_name": spec["primary_metric"],
            "repeat_count": repeat_count,
            "mean_accuracy": mean_accuracy,
            "max_delta": max_delta,
            "stable": stable,
            "reruns_report": reruns_report_path.relative_to(output_dir).as_posix(),
        },
        "claim_gap": {
            "status": "gap_remains",
            "summary": (
                "Local repeatability is established on a deterministic reference slice, "
                "but the official fastText binary, full AG News data, and paper table "
                "comparison are still pending."
            ),
            "missing_for_full_reproduction": [
                "full public AG News dataset or a documented equivalent dataset",
                "official fastText binary or Python package training path",
                "paper-table target value and tolerance",
                "archived training and evaluation logs from the full dataset run",
            ],
            "blocked_claims": list(spec["blocked_claims"]),
            "official_scores_claimed": False,
        },
        "official_scores_claimed": False,
    }
    _write_json(alignment_report_path, alignment_report)
    _write_json(
        handoff_path,
        {
            "schema_version": "2026-05-13.full-reproduction-client-handoff.v1",
            "paper_id": spec["paper_id"],
            "current_stage": "p2_baseline_alignment",
            "metric_name": spec["primary_metric"],
            "metric_value": mean_accuracy,
            "stable": stable,
            "recommended_next_action": "replace_reference_slice_with_full_public_dataset",
            "allowed_patch_scope": [
                "dataset loader for full public AG News data",
                "official fastText binary invocation",
                "equivalent Python fastText package invocation",
                "paper-result tolerance configuration",
            ],
            "blocked_claims": list(spec["blocked_claims"]),
            "official_scores_claimed": False,
        },
    )
    return {
        "status": "completed",
        "stage": "p2_baseline_alignment",
        "paper_id": spec["paper_id"],
        "accuracy": mean_accuracy,
        "stable": stable,
        "alignment_report": str(alignment_report_path),
        "reruns_report": str(reruns_report_path),
        "client_handoff": str(handoff_path),
        "official_scores_claimed": False,
    }


def _mini_text_classification_records() -> list[dict[str, str]]:
    return [
        {
            "id": "train-world-1",
            "split": "train",
            "label": "world",
            "text": "diplomats met to discuss the peace agreement and regional elections",
        },
        {
            "id": "train-world-2",
            "split": "train",
            "label": "world",
            "text": "the foreign ministry announced talks with neighboring countries",
        },
        {
            "id": "train-business-1",
            "split": "train",
            "label": "business",
            "text": "shares rose after the company reported revenue growth and profit",
        },
        {
            "id": "train-business-2",
            "split": "train",
            "label": "business",
            "text": "investors watched the market as banks adjusted interest rates",
        },
        {
            "id": "train-sports-1",
            "split": "train",
            "label": "sports",
            "text": "the team won the match after a late goal in the final",
        },
        {
            "id": "train-sports-2",
            "split": "train",
            "label": "sports",
            "text": "players trained before the championship tournament and league game",
        },
        {
            "id": "train-tech-1",
            "split": "train",
            "label": "tech",
            "text": "software engineers released a faster mobile processor and new platform",
        },
        {
            "id": "train-tech-2",
            "split": "train",
            "label": "tech",
            "text": "researchers improved neural network hardware and cloud computing tools",
        },
        {
            "id": "test-world-1",
            "split": "test",
            "label": "world",
            "text": "election officials and diplomats discussed the regional peace talks",
        },
        {
            "id": "test-business-1",
            "split": "test",
            "label": "business",
            "text": "the bank reported profit as investors returned to the market",
        },
        {
            "id": "test-sports-1",
            "split": "test",
            "label": "sports",
            "text": "the league team won the final game of the tournament",
        },
        {
            "id": "test-tech-1",
            "split": "test",
            "label": "tech",
            "text": "the new processor improved mobile software and computing performance",
        },
    ]


def _ag_news_reference_slice_records() -> list[dict[str, str]]:
    labels = {
        "world": [
            "diplomats met after regional elections to discuss a peace framework",
            "the foreign ministry confirmed talks with neighboring governments",
            "observers reported calm voting across several provinces",
            "leaders opened negotiations after the border agreement was signed",
            "diplomats and foreign leaders reviewed the regional peace agreement",
            "election observers said neighboring governments opened talks",
        ],
        "business": [
            "shares rose as the company reported stronger revenue and profit",
            "banks adjusted interest rates while investors watched the market",
            "the airline announced quarterly earnings above analyst forecasts",
            "retail sales improved after consumers returned to city stores",
            "the company reported quarterly revenue as investors bought shares",
            "banks and market analysts watched profit and interest rates",
        ],
        "sports": [
            "the team won the championship after a late goal in the final",
            "players trained before the league match and weekend tournament",
            "the coach praised defense after the club reached the playoffs",
            "a record crowd watched the runner win the national title",
            "the league team won the final match after a late goal",
            "players and fans celebrated the championship tournament victory",
        ],
        "tech": [
            "software engineers released a faster mobile processor platform",
            "researchers improved neural network hardware and cloud tools",
            "the company patched a security flaw in its browser update",
            "a satellite startup tested new chips for low power devices",
            "software developers released cloud tools for mobile analytics",
            "researchers tested neural network chips and processor hardware",
        ],
    }
    records: list[dict[str, str]] = []
    for label, texts in labels.items():
        for index, text in enumerate(texts, start=1):
            split = "test" if index in {5, 6} else "train"
            records.append(
                {
                    "id": f"{split}-{label}-{index}",
                    "split": split,
                    "label": label,
                    "text": text,
                }
            )
    return records


def _read_ag_news_csv_records(path: Path, *, split: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    with path.expanduser().open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for index, row in enumerate(reader, start=1):
            if not row:
                continue
            if len(row) < 3:
                raise ValueError(f"AG News row {index} in {path} must have label,title,text")
            label_id = row[0].strip()
            if label_id not in AG_NEWS_LABELS:
                raise ValueError(f"unsupported AG News label {label_id!r} in {path}:{index}")
            title = row[1].strip()
            description = row[2].strip()
            records.append(
                {
                    "id": f"{split}-{index:06d}",
                    "split": split,
                    "label": AG_NEWS_LABELS[label_id],
                    "label_id": label_id,
                    "title": title,
                    "description": description,
                    "text": f"{title} {description}".strip(),
                }
            )
    return records


def _render_fasttext_records(records: list[dict[str, str]]) -> str:
    return "".join(
        f"__label__{record['label']} {record['text']}\n"
        for record in records
    )


def _read_fasttext_records(path: Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        label_token, text = line.split(" ", maxsplit=1)
        records.append((label_token.removeprefix("__label__"), text))
    return records


def _train_multinomial_baseline(
    records: list[tuple[str, str]],
) -> dict[str, Any]:
    labels = sorted({label for label, _ in records})
    label_counts = Counter(label for label, _ in records)
    token_counts: dict[str, Counter[str]] = defaultdict(Counter)
    total_tokens: Counter[str] = Counter()
    vocabulary: set[str] = set()
    for label, text in records:
        tokens = _tokens(text)
        token_counts[label].update(tokens)
        total_tokens[label] += len(tokens)
        vocabulary.update(tokens)
    return {
        "labels": labels,
        "label_counts": label_counts,
        "token_counts": token_counts,
        "total_tokens": total_tokens,
        "vocabulary": vocabulary,
        "record_count": len(records),
    }


def _predict_label(model: dict[str, Any], text: str) -> str:
    tokens = _tokens(text)
    vocabulary_size = max(1, len(model["vocabulary"]))
    best_label = ""
    best_score = -math.inf
    for label in model["labels"]:
        prior = (model["label_counts"][label] + 1) / (
            model["record_count"] + len(model["labels"])
        )
        score = math.log(prior)
        denominator = model["total_tokens"][label] + vocabulary_size
        for token in tokens:
            score += math.log((model["token_counts"][label][token] + 1) / denominator)
        if score > best_score:
            best_score = score
            best_label = label
    return best_label


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _serializable_model(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "labels": list(model["labels"]),
        "label_counts": dict(model["label_counts"]),
        "token_counts": {
            label: dict(counter)
            for label, counter in model["token_counts"].items()
        },
        "total_tokens": dict(model["total_tokens"]),
        "vocabulary": sorted(model["vocabulary"]),
        "record_count": model["record_count"],
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_fasttext_binary(explicit_binary: Path | None) -> Path | None:
    if explicit_binary is not None:
        candidate = explicit_binary.expanduser()
        if candidate.exists() and candidate.is_file() and candidate.stat().st_mode & 0o111:
            return candidate.resolve()
        return None
    discovered = shutil.which("fasttext")
    return Path(discovered).resolve() if discovered else None


def _md5_file(path: Path) -> str:
    digest = hashlib.md5()  # noqa: S324 - file identity only, not security.
    with path.expanduser().open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ag_news_csv_limitations(is_full_expected_size: bool) -> list[str]:
    limitations = [
        "converted from local AG News CSV files into fastText supervised format",
        "local baseline may use python fallback unless official fastText runtime is available",
    ]
    if not is_full_expected_size:
        limitations.append("row counts do not match the full AG News train/test split")
    return limitations


def _full_data_alignment_missing_items(
    *,
    full_dataset_ready: bool,
    official_toolchain_ready: bool,
) -> list[str]:
    missing: list[str] = []
    if not full_dataset_ready:
        missing.append("full AG News CSV row counts and expected hashes")
    if not official_toolchain_ready:
        missing.append("official fastText binary or equivalent Python fastText package")
    missing.extend(
        [
            "official baseline training log",
            "paper target comparison reviewed by a human",
            "proof archive with hash-indexed official/equivalent run artifacts",
        ]
    )
    return missing


def _full_data_alignment_gap_summary(
    *,
    full_dataset_ready: bool,
    official_toolchain_ready: bool,
) -> str:
    if full_dataset_ready and official_toolchain_ready:
        return (
            "Dataset size and fastText runtime are ready; run the official/equivalent "
            "baseline before claiming paper reproduction."
        )
    return (
        "The AG News conversion and local fallback baseline are runnable, but full "
        "paper baseline alignment still requires the full dataset, official/equivalent "
        "fastText runtime, and reviewed paper-target comparison."
    )
