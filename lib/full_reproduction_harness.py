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
import subprocess
import tarfile
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
FASTTEXT_FIXED_TRAIN_ARGS = ["-thread", "1", "-seed", "0"]
FASTTEXT_PATCH_ALLOWED_ARGS = {
    "-lr": {"type": "float", "min": 0.000001, "max": 5.0},
    "-epoch": {"type": "int", "min": 1, "max": 100},
    "-wordNgrams": {"type": "int", "min": 1, "max": 5},
    "-dim": {"type": "int", "min": 10, "max": 1000},
    "-minCount": {"type": "int", "min": 1, "max": 100},
    "-loss": {"type": "enum", "values": ["softmax", "hs", "ns", "one-vs-all"]},
}
FASTTEXT_PATCH_ARG_ORDER = list(FASTTEXT_PATCH_ALLOWED_ARGS)
FASTTEXT_PATCH_PROOF_ARTIFACT_NAMES = {
    "improvement_report": "improvement-report.json",
    "baseline_report": "baseline-report.json",
    "dataset_provenance": "dataset-provenance.json",
    "runtime_probe": "fasttext-runtime-probe.json",
    "patch_proposal": "patch-proposal.json",
    "patch_diff": "patch-diff.patch",
    "train_log": "fasttext-patch-train.log",
    "test_log": "fasttext-patch-test.log",
    "client_handoff": "client-handoff.json",
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


def run_fasttext_binary_baseline(
    config: FullReproductionRunConfig,
    *,
    train_csv: Path,
    test_csv: Path,
    fasttext_binary: Path,
) -> dict[str, Any]:
    """Run a selected fastText-compatible binary and archive baseline logs."""
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
    if not runtime_probe["binary"]["available"]:
        raise FileNotFoundError(f"fastText binary is not executable: {fasttext_binary}")

    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    model_prefix = output_dir / "model"
    train_log_path = logs_dir / "fasttext-train.log"
    test_log_path = logs_dir / "fasttext-test.log"

    training_argv = [
        str(runtime_probe["binary"]["path"]),
        "supervised",
        "-input",
        str(artifacts["train_fasttext"]),
        "-output",
        str(model_prefix),
        *FASTTEXT_FIXED_TRAIN_ARGS,
    ]
    training_proc = _run_logged_command(
        training_argv,
        cwd=output_dir,
        timeout_seconds=config.max_train_seconds,
        log_path=train_log_path,
    )
    model_path = model_prefix.with_suffix(".bin")
    evaluation_argv = [
        str(runtime_probe["binary"]["path"]),
        "test",
        str(model_path),
        str(artifacts["test_fasttext"]),
    ]
    evaluation_proc = _run_logged_command(
        evaluation_argv,
        cwd=output_dir,
        timeout_seconds=120,
        log_path=test_log_path,
    )
    p_at_1 = _parse_fasttext_p_at_1(evaluation_proc.stdout)
    target_accuracy = float(FASTTEXT_AG_NEWS_PAPER_TARGET["target_accuracy"])
    tolerance = float(FASTTEXT_AG_NEWS_PAPER_TARGET["tolerance"])
    within_tolerance = abs(p_at_1 - target_accuracy) <= tolerance
    full_dataset_ready = bool(provenance["is_full_expected_size"])
    claim_gap_status = (
        "aligned_within_tolerance"
        if within_tolerance and full_dataset_ready
        else "gap_remains"
    )

    report_path = output_dir / "fasttext-baseline-report.json"
    runtime_probe_path = output_dir / "fasttext-runtime-probe.json"
    handoff_path = output_dir / "client-handoff.json"
    _write_json(runtime_probe_path, runtime_probe)
    _write_json(
        report_path,
        {
            "schema_version": "2026-05-13.fasttext-binary-baseline.v1",
            "status": "completed",
            "stage": "p2_plus_fasttext_binary_baseline",
            "paper_reference": {
                "paper_id": spec["paper_id"],
                "title": spec["title"],
                "paper_url": spec["paper_url"],
                "code_url": spec["code_url"],
            },
            "dataset": {
                "source_kind": provenance["source_kind"],
                "version": provenance["version"],
                "source_urls": provenance["source_urls"],
                "train_count": provenance["train_count"],
                "test_count": provenance["test_count"],
                "expected_rows": provenance["expected_rows"],
                "is_full_expected_size": full_dataset_ready,
                "expected_md5": provenance["expected_md5"],
                "actual_md5": provenance["actual_md5"],
                "hash_verification_status": provenance["hash_verification_status"],
                "limitations": _fasttext_binary_dataset_limitations(
                    provenance["limitations"]
                ),
            },
            "toolchain": {
                "runtime_status": runtime_probe["status"],
                "binary_path": runtime_probe["binary"]["path"],
                "runtime_probe": runtime_probe_path.relative_to(output_dir).as_posix(),
            },
            "commands": {
                "training": _redact_command_paths(training_argv, output_dir),
                "evaluation": _redact_command_paths(evaluation_argv, output_dir),
            },
            "execution": {
                "training_returncode": training_proc.returncode,
                "evaluation_returncode": evaluation_proc.returncode,
                "training_log": train_log_path.relative_to(output_dir).as_posix(),
                "evaluation_log": test_log_path.relative_to(output_dir).as_posix(),
                "model_artifact": model_path.relative_to(output_dir).as_posix(),
            },
            "metric": {
                "name": spec["primary_metric"],
                "p_at_1": p_at_1,
                "within_tolerance": within_tolerance,
            },
            "paper_target": FASTTEXT_AG_NEWS_PAPER_TARGET,
            "claim_gap": {
                "status": claim_gap_status,
                "summary": _fasttext_binary_baseline_gap_summary(
                    full_dataset_ready=full_dataset_ready,
                    within_tolerance=within_tolerance,
                ),
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
            "current_stage": "p2_plus_fasttext_binary_baseline",
            "metric_name": spec["primary_metric"],
            "metric_value": p_at_1,
            "recommended_next_action": "review_fasttext_baseline_gap",
            "allowed_patch_scope": [
                "confirm full AG News dataset hashes and row counts",
                "rerun selected fastText-compatible binary with archived logs",
                "compare paper target within tolerance",
            ],
            "blocked_claims": list(spec["blocked_claims"]),
            "official_scores_claimed": False,
        },
    )
    return {
        "status": "completed",
        "stage": "p2_plus_fasttext_binary_baseline",
        "paper_id": spec["paper_id"],
        "p_at_1": p_at_1,
        "within_tolerance": within_tolerance,
        "full_dataset_ready": full_dataset_ready,
        "baseline_report": str(report_path),
        "client_handoff": str(handoff_path),
        "official_scores_claimed": False,
    }


def run_fasttext_patch_round(
    config: FullReproductionRunConfig,
    *,
    train_csv: Path,
    test_csv: Path,
    fasttext_binary: Path,
    baseline_report: Path,
    proposal: dict[str, Any],
) -> dict[str, Any]:
    """Run one bounded client-proposed fastText hyperparameter patch round."""
    output_dir = config.output_dir.expanduser().resolve()
    spec = _read_json(config.target_spec_path)
    artifacts = prepare_ag_news_csv_dataset(
        target_spec_path=config.target_spec_path,
        output_dir=output_dir,
        train_csv=train_csv,
        test_csv=test_csv,
    )
    provenance = _read_json(artifacts["dataset_provenance"])
    baseline_payload = _read_json(baseline_report.expanduser().resolve())
    baseline_p_at_1 = _baseline_report_p_at_1(baseline_payload)
    normalized_proposal = _normalize_fasttext_patch_proposal(proposal)

    runtime_probe = probe_fasttext_runtime(explicit_binary=fasttext_binary)
    if not runtime_probe["binary"]["available"]:
        raise FileNotFoundError(f"fastText binary is not executable: {fasttext_binary}")

    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    model_prefix = output_dir / "patched-model"
    train_log_path = logs_dir / "fasttext-patch-train.log"
    test_log_path = logs_dir / "fasttext-patch-test.log"
    runtime_probe_path = output_dir / "fasttext-runtime-probe.json"
    proposal_path = output_dir / "patch-proposal.json"
    patch_diff_path = output_dir / "patch-diff.patch"
    report_path = output_dir / "improvement-report.json"
    handoff_path = output_dir / "client-handoff.json"

    patch_args = _fasttext_patch_arg_list(normalized_proposal["train_args"])
    training_argv = [
        str(runtime_probe["binary"]["path"]),
        "supervised",
        "-input",
        str(artifacts["train_fasttext"]),
        "-output",
        str(model_prefix),
        *patch_args,
        *FASTTEXT_FIXED_TRAIN_ARGS,
    ]
    model_path = model_prefix.with_suffix(".bin")
    evaluation_argv = [
        str(runtime_probe["binary"]["path"]),
        "test",
        str(model_path),
        str(artifacts["test_fasttext"]),
    ]

    redacted_training = _redact_command_paths(training_argv, output_dir)
    _write_json(runtime_probe_path, runtime_probe)
    _write_json(proposal_path, normalized_proposal)
    patch_diff_path.write_text(
        _render_fasttext_patch_diff(
            baseline_payload.get("commands", {}).get("training"),
            redacted_training,
        ),
        encoding="utf-8",
    )

    training_proc = _run_logged_command(
        training_argv,
        cwd=output_dir,
        timeout_seconds=config.max_train_seconds,
        log_path=train_log_path,
    )
    evaluation_proc = _run_logged_command(
        evaluation_argv,
        cwd=output_dir,
        timeout_seconds=120,
        log_path=test_log_path,
    )
    p_at_1 = _parse_fasttext_p_at_1(evaluation_proc.stdout)
    delta = round(p_at_1 - baseline_p_at_1, 6)
    improved = delta > 0
    target_accuracy = float(FASTTEXT_AG_NEWS_PAPER_TARGET["target_accuracy"])
    tolerance = float(FASTTEXT_AG_NEWS_PAPER_TARGET["tolerance"])
    within_tolerance = abs(p_at_1 - target_accuracy) <= tolerance
    full_dataset_ready = bool(provenance["is_full_expected_size"])
    loop_decision = _fasttext_patch_loop_decision(improved=improved)

    report = {
        "schema_version": "2026-05-13.fasttext-patch-round.v1",
        "status": "completed",
        "stage": "p3_fasttext_patch_round",
        "paper_reference": {
            "paper_id": spec["paper_id"],
            "title": spec["title"],
            "paper_url": spec["paper_url"],
            "code_url": spec["code_url"],
        },
        "baseline": {
            "report": str(baseline_report.expanduser().resolve()),
            "p_at_1": baseline_p_at_1,
            "full_dataset_ready": baseline_payload.get("dataset", {}).get(
                "is_full_expected_size"
            ),
        },
        "proposal": normalized_proposal,
        "dataset": {
            "source_kind": provenance["source_kind"],
            "version": provenance["version"],
            "train_count": provenance["train_count"],
            "test_count": provenance["test_count"],
            "is_full_expected_size": full_dataset_ready,
            "actual_md5": provenance["actual_md5"],
            "hash_verification_status": provenance["hash_verification_status"],
        },
        "toolchain": {
            "runtime_status": runtime_probe["status"],
            "binary_path": runtime_probe["binary"]["path"],
            "runtime_probe": runtime_probe_path.relative_to(output_dir).as_posix(),
        },
        "commands": {
            "training": redacted_training,
            "evaluation": _redact_command_paths(evaluation_argv, output_dir),
        },
        "execution": {
            "training_returncode": training_proc.returncode,
            "evaluation_returncode": evaluation_proc.returncode,
            "training_log": train_log_path.relative_to(output_dir).as_posix(),
            "evaluation_log": test_log_path.relative_to(output_dir).as_posix(),
            "model_artifact": model_path.relative_to(output_dir).as_posix(),
            "patch_diff": patch_diff_path.relative_to(output_dir).as_posix(),
            "proposal": proposal_path.relative_to(output_dir).as_posix(),
        },
        "metric": {
            "name": spec["primary_metric"],
            "baseline_p_at_1": baseline_p_at_1,
            "p_at_1": p_at_1,
            "delta": delta,
            "improved": improved,
            "within_tolerance": within_tolerance,
        },
        "paper_target": FASTTEXT_AG_NEWS_PAPER_TARGET,
        "loop_decision": loop_decision,
        "claim_gap": {
            "status": "patch_loop_proof" if improved else "patch_loop_no_improvement",
            "summary": (
                "One client-proposed fastText hyperparameter patch was executed and "
                "compared to the trusted local baseline. Human review is still required "
                "before escalating claims."
            ),
            "blocked_claims": list(spec["blocked_claims"]),
            "official_scores_claimed": False,
        },
        "official_scores_claimed": False,
    }
    _write_json(report_path, report)
    _write_json(
        handoff_path,
        {
            "schema_version": "2026-05-13.full-reproduction-client-handoff.v1",
            "paper_id": spec["paper_id"],
            "current_stage": "p3_fasttext_patch_round",
            "metric_name": spec["primary_metric"],
            "baseline_metric_value": baseline_p_at_1,
            "metric_value": p_at_1,
            "delta": delta,
            "improved": improved,
            "recommended_next_action": (
                "review_patch_round_then_try_next_proposal"
                if improved
                else "revise_proposal_or_stop"
            ),
            "allowed_patch_scope": [
                "fastText supervised hyperparameters in the allowlist",
                "one proposal per archived patch round",
                "human review before public claims",
            ],
            "blocked_claims": list(spec["blocked_claims"]),
            "official_scores_claimed": False,
        },
    )
    return {
        "status": "completed",
        "stage": "p3_fasttext_patch_round",
        "paper_id": spec["paper_id"],
        "baseline_p_at_1": baseline_p_at_1,
        "p_at_1": p_at_1,
        "delta": delta,
        "improved": improved,
        "within_tolerance": within_tolerance,
        "improvement_report": str(report_path),
        "patch_diff": str(patch_diff_path),
        "client_handoff": str(handoff_path),
        "official_scores_claimed": False,
    }


def run_fasttext_multi_proposal_loop(
    config: FullReproductionRunConfig,
    *,
    train_csv: Path,
    test_csv: Path,
    fasttext_binary: Path,
    baseline_report: Path,
    proposals: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run several bounded fastText proposals and keep a rollbackable best state."""
    if not proposals:
        raise ValueError("proposals must contain at least one proposal")

    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    spec = _read_json(config.target_spec_path)
    baseline_report_path = baseline_report.expanduser().resolve()
    baseline_payload = _read_json(baseline_report_path)
    baseline_p_at_1 = _baseline_report_p_at_1(baseline_payload)
    rounds_dir = output_dir / "rounds"
    rounds_dir.mkdir(parents=True, exist_ok=True)

    best_metric = baseline_p_at_1
    best_source = "baseline"
    best_round_id: str | None = None
    best_report: str | None = str(baseline_report_path)
    round_records: list[dict[str, Any]] = []
    rollback_events = 0

    for index, proposal in enumerate(proposals, start=1):
        proposal_id = _safe_fasttext_proposal_id(proposal.get("proposal_id"), index)
        round_id = f"round-{index:03d}-{proposal_id}"
        round_dir = rounds_dir / round_id
        try:
            result = run_fasttext_patch_round(
                FullReproductionRunConfig(
                    target_spec_path=config.target_spec_path,
                    output_dir=round_dir,
                    max_train_seconds=config.max_train_seconds,
                ),
                train_csv=train_csv,
                test_csv=test_csv,
                fasttext_binary=fasttext_binary,
                baseline_report=baseline_report_path,
                proposal=proposal,
            )
            metric_value = float(result["p_at_1"])
            improved_best = metric_value > best_metric
            if improved_best:
                best_metric = metric_value
                best_source = round_id
                best_round_id = round_id
                best_report = result["improvement_report"]
            else:
                rollback_events += 1
            round_records.append({
                "round_index": index,
                "round_id": round_id,
                "proposal_id": proposal_id,
                "status": "completed",
                "metric_value": metric_value,
                "delta_vs_baseline": round(metric_value - baseline_p_at_1, 6),
                "improved_best": improved_best,
                "best_after_round": best_metric,
                "best_source_after_round": best_source,
                "rollback_action": (
                    "promote_to_best" if improved_best else "keep_best_so_far"
                ),
                "improvement_report": result["improvement_report"],
                "official_scores_claimed": False,
            })
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            rollback_events += 1
            round_records.append({
                "round_index": index,
                "round_id": round_id,
                "proposal_id": proposal_id,
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "best_after_round": best_metric,
                "best_source_after_round": best_source,
                "rollback_action": "keep_best_so_far",
                "official_scores_claimed": False,
            })

    failure_count = sum(1 for record in round_records if record["status"] == "failed")
    completed_count = sum(1 for record in round_records if record["status"] == "completed")
    improved_count = sum(1 for record in round_records if record.get("improved_best"))
    status = "completed_with_failures" if failure_count else "completed"
    report_path = output_dir / "multi-round-report.json"
    handoff_path = output_dir / "client-handoff.json"
    rollback_summary = {
        "rollback_events": rollback_events,
        "rollback_strategy": "keep_best_so_far",
        "best_source": best_source,
        "best_metric": best_metric,
        "best_round_id": best_round_id,
        "best_report": best_report,
    }
    report = {
        "schema_version": "2026-05-14.fasttext-multi-proposal-loop.v1",
        "status": status,
        "stage": "p5_fasttext_multi_proposal_loop",
        "paper_reference": {
            "paper_id": spec["paper_id"],
            "title": spec["title"],
            "paper_url": spec["paper_url"],
            "code_url": spec["code_url"],
        },
        "baseline": {
            "report": str(baseline_report_path),
            "p_at_1": baseline_p_at_1,
        },
        "summary": {
            "proposal_count": len(proposals),
            "completed_count": completed_count,
            "failure_count": failure_count,
            "improved_count": improved_count,
            "best_metric": best_metric,
            "best_source": best_source,
        },
        "rounds": round_records,
        "rollback_summary": rollback_summary,
        "claim_boundary": (
            "bounded local fastText proposal loop with rollback evidence only; "
            "not an official leaderboard score or arbitrary autonomous research claim"
        ),
        "blocked_public_claims": list(spec["blocked_claims"]),
        "official_scores_claimed": False,
    }
    _write_json(report_path, report)
    _write_json(
        handoff_path,
        {
            "schema_version": "2026-05-14.full-reproduction-client-handoff.v1",
            "paper_id": spec["paper_id"],
            "current_stage": "p5_fasttext_multi_proposal_loop",
            "metric_name": spec["primary_metric"],
            "baseline_metric_value": baseline_p_at_1,
            "best_metric_value": best_metric,
            "best_source": best_source,
            "failure_count": failure_count,
            "rollback_summary": rollback_summary,
            "recommended_next_action": "package_release_proof_for_review",
            "blocked_claims": list(spec["blocked_claims"]),
            "official_scores_claimed": False,
        },
    )
    return {
        "status": status,
        "stage": "p5_fasttext_multi_proposal_loop",
        "paper_id": spec["paper_id"],
        "baseline_p_at_1": baseline_p_at_1,
        "best_metric": best_metric,
        "best_source": best_source,
        "best_round_id": best_round_id,
        "proposal_count": len(proposals),
        "completed_count": completed_count,
        "failure_count": failure_count,
        "rollback_summary": rollback_summary,
        "multi_round_report": str(report_path),
        "client_handoff": str(handoff_path),
        "official_scores_claimed": False,
    }


def write_fasttext_patch_round_proof_bundle(
    *,
    patch_round_report: Path,
    output_dir: Path,
    reviewer: str = "local-review",
    review_status: str = "approved_with_limitations",
) -> dict[str, Any]:
    """Package a completed fastText patch round as a reviewed proof bundle."""
    report_path = patch_round_report.expanduser().resolve()
    report = _read_json(report_path)
    if report.get("stage") != "p3_fasttext_patch_round":
        raise ValueError("patch_round_report must be a p3_fasttext_patch_round report")
    if report.get("official_scores_claimed") is not False:
        raise ValueError("patch round report must preserve official_scores_claimed=false")
    if not reviewer.strip():
        raise ValueError("reviewer must be a non-empty string")
    if review_status not in {"approved_with_limitations", "needs_more_evidence", "rejected"}:
        raise ValueError(
            "review_status must be approved_with_limitations, needs_more_evidence, or rejected"
        )

    output_dir = output_dir.expanduser().resolve()
    required_artifacts = _fasttext_patch_proof_required_artifacts(report_path, report)
    missing_artifacts = [
        role for role, source_path in required_artifacts.items()
        if not source_path.is_file()
    ]
    if missing_artifacts:
        return {
            "status": "blocked",
            "stage": "p4_fasttext_patch_proof_bundle",
            "patch_round_report": str(report_path),
            "output_dir": str(output_dir),
            "missing_artifacts": missing_artifacts,
            "official_scores_claimed": False,
        }

    artifacts_dir = output_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    archived_artifacts: list[dict[str, Any]] = []
    for role, source_path in required_artifacts.items():
        archive_name = FASTTEXT_PATCH_PROOF_ARTIFACT_NAMES[role]
        archive_path = artifacts_dir / archive_name
        shutil.copy2(source_path, archive_path)
        archived_artifacts.append({
            "role": role,
            "source_path": str(source_path),
            "archive_relative_path": archive_path.relative_to(output_dir).as_posix(),
            "sha256": _sha256_file(archive_path),
            "size_bytes": archive_path.stat().st_size,
        })

    metric_summary = dict(report.get("metric", {}))
    blocked_public_claims = _fasttext_patch_blocked_public_claims(report)
    allowed_public_claims = [
        (
            "local controlled fastText AG News patch-loop proof with archived "
            "proposal, command diff, logs, metrics, and human review"
        )
    ] if review_status == "approved_with_limitations" else []
    human_review = {
        "schema_version": "2026-05-14.fasttext-patch-human-review.v1",
        "reviewer": reviewer.strip(),
        "review_status": review_status,
        "stage": "p4_fasttext_patch_proof_bundle",
        "metric_summary": metric_summary,
        "artifact_checklist": [
            {"role": item["role"], "present": True}
            for item in archived_artifacts
        ],
        "allowed_public_claims": allowed_public_claims,
        "blocked_public_claims": blocked_public_claims,
        "limitations": [
            "single fastText AG News core-track patch round",
            "local proof only; not an official leaderboard score",
            "human review is required before stronger public claims",
        ],
        "official_scores_claimed": False,
    }
    human_review_path = output_dir / "human-review-report.json"
    _write_json(human_review_path, human_review)
    archived_artifacts.append({
        "role": "human_review_report",
        "source_path": str(human_review_path),
        "archive_relative_path": human_review_path.relative_to(output_dir).as_posix(),
        "sha256": _sha256_file(human_review_path),
        "size_bytes": human_review_path.stat().st_size,
    })

    artifact_index = {
        "schema_version": "2026-05-14.fasttext-patch-artifact-index.v1",
        "artifact_count": len(archived_artifacts),
        "artifacts": archived_artifacts,
        "official_scores_claimed": False,
    }
    artifact_index_path = output_dir / "artifact-index.json"
    _write_json(artifact_index_path, artifact_index)
    manifest = {
        "schema_version": "2026-05-14.fasttext-patch-proof-manifest.v1",
        "status": "completed",
        "stage": "p4_fasttext_patch_proof_bundle",
        "source_patch_round_report": str(report_path),
        "review_status": review_status,
        "reviewer": reviewer.strip(),
        "metric_summary": metric_summary,
        "claim_boundary": (
            "local controlled fastText patch-loop proof only; not a leaderboard "
            "score, full-paper reproduction, or arbitrary automatic improvement"
        ),
        "blocked_public_claims": blocked_public_claims,
        "artifact_count": len(archived_artifacts),
        "artifacts": archived_artifacts,
        "artifact_sha256": {
            item["role"]: item["sha256"] for item in archived_artifacts
        },
        "official_scores_claimed": False,
    }
    manifest_path = output_dir / "proof-manifest.json"
    _write_json(manifest_path, manifest)
    sha_path = output_dir / "SHA256SUMS"
    sha_path.write_text(
        "".join(
            f"{item['sha256']}  {item['archive_relative_path']}\n"
            for item in archived_artifacts
        ),
        encoding="utf-8",
    )
    summary_path = output_dir / "proof-summary.md"
    summary_path.write_text(
        _render_fasttext_patch_proof_summary(manifest),
        encoding="utf-8",
    )
    return {
        "status": "completed",
        "stage": "p4_fasttext_patch_proof_bundle",
        "proof_manifest": str(manifest_path),
        "human_review_report": str(human_review_path),
        "artifact_index": str(artifact_index_path),
        "sha256sums": str(sha_path),
        "proof_summary": str(summary_path),
        "artifact_count": len(archived_artifacts),
        "official_scores_claimed": False,
    }


def write_fasttext_release_proof_bundle(
    *,
    proof_manifest: Path,
    output_dir: Path,
    multi_round_report: Path | None = None,
    reviewer: str = "local-review",
) -> dict[str, Any]:
    """Package P4/P5 fastText proof artifacts into a downloadable review bundle."""
    if not reviewer.strip():
        raise ValueError("reviewer must be a non-empty string")

    proof_manifest_path = proof_manifest.expanduser().resolve()
    proof_payload = _read_json(proof_manifest_path)
    if proof_payload.get("stage") != "p4_fasttext_patch_proof_bundle":
        raise ValueError("proof_manifest must be a p4_fasttext_patch_proof_bundle manifest")
    if proof_payload.get("official_scores_claimed") is not False:
        raise ValueError("proof_manifest must preserve official_scores_claimed=false")

    multi_payload: dict[str, Any] | None = None
    multi_round_report_path: Path | None = None
    if multi_round_report is not None:
        multi_round_report_path = multi_round_report.expanduser().resolve()
        multi_payload = _read_json(multi_round_report_path)
        if multi_payload.get("stage") != "p5_fasttext_multi_proposal_loop":
            raise ValueError("multi_round_report must be a p5_fasttext_multi_proposal_loop report")
        if multi_payload.get("official_scores_claimed") is not False:
            raise ValueError("multi_round_report must preserve official_scores_claimed=false")

    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_dir = output_dir / "review-package"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    p4_dir = package_dir / "p4-proof"
    p4_dir.mkdir(parents=True, exist_ok=True)
    proof_root = proof_manifest_path.parent
    for source_path in sorted(proof_root.rglob("*")):
        if source_path.is_file():
            relative_path = source_path.relative_to(proof_root)
            target_path = p4_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)

    if multi_round_report_path is not None:
        p5_dir = package_dir / "p5-multi-round"
        p5_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(multi_round_report_path, p5_dir / "multi-round-report.json")

    p4_artifact_count = int(proof_payload.get("artifact_count", 0))
    multi_summary = _fasttext_multi_round_release_summary(multi_payload)
    tar_path = output_dir / "release-proof-bundle.tar.gz"
    if tar_path.exists():
        tar_path.unlink()
    with tarfile.open(tar_path, "w:gz") as archive:
        archive.add(package_dir, arcname="ml-research-loop-fasttext-proof")
    bundle_sha256 = _sha256_file(tar_path)
    sha_path = output_dir / "release-proof-bundle.sha256"
    sha_path.write_text(
        f"{bundle_sha256}  {tar_path.name}\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": "2026-05-14.fasttext-release-proof-bundle.v1",
        "status": "completed",
        "stage": "p5_fasttext_release_proof_bundle",
        "reviewer": reviewer.strip(),
        "source_proof_manifest": str(proof_manifest_path),
        "source_multi_round_report": (
            str(multi_round_report_path) if multi_round_report_path is not None else None
        ),
        "download_artifact": {
            "path": str(tar_path),
            "sha256": bundle_sha256,
            "checksum_file": str(sha_path),
            "format": "tar.gz",
        },
        "p4_summary": {
            "review_status": proof_payload.get("review_status"),
            "artifact_count": p4_artifact_count,
            "metric_summary": proof_payload.get("metric_summary", {}),
        },
        "multi_round_summary": multi_summary,
        "claim_boundary": (
            "downloadable local fastText proof bundle for review; not an official "
            "leaderboard score, full-paper reproduction claim, or general autonomous "
            "research improvement claim"
        ),
        "blocked_public_claims": list(proof_payload.get("blocked_public_claims", [])),
        "official_scores_claimed": False,
    }
    manifest_path = output_dir / "release-proof-manifest.json"
    _write_json(manifest_path, manifest)
    checklist_path = output_dir / "release-review-checklist.md"
    checklist_path.write_text(
        _render_fasttext_release_review_checklist(manifest),
        encoding="utf-8",
    )
    return {
        "status": "completed",
        "stage": "p5_fasttext_release_proof_bundle",
        "release_manifest": str(manifest_path),
        "review_checklist": str(checklist_path),
        "download_bundle": str(tar_path),
        "checksum_file": str(sha_path),
        "bundle_sha256": bundle_sha256,
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


def _run_logged_command(
    argv: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    log_path: Path,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_seconds,
    )
    log_path.write_text(proc.stdout, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed with returncode {proc.returncode}: {' '.join(argv)}"
        )
    return proc


def _parse_fasttext_p_at_1(output: str) -> float:
    for line in output.splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[0] == "P@1":
            return round(float(parts[1]), 6)
    raise ValueError("fastText test output did not contain P@1")


def _baseline_report_p_at_1(report: dict[str, Any]) -> float:
    metric = report.get("metric")
    if isinstance(metric, dict) and "p_at_1" in metric:
        return round(float(metric["p_at_1"]), 6)
    if "p_at_1" in report:
        return round(float(report["p_at_1"]), 6)
    raise ValueError("baseline report does not contain metric.p_at_1")


def _normalize_fasttext_patch_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(proposal, dict):
        raise ValueError("fastText patch proposal must be an object")
    proposal_id = proposal.get("proposal_id", "fasttext-patch-round-001")
    if not isinstance(proposal_id, str) or not proposal_id.strip():
        raise ValueError("proposal_id must be a non-empty string")
    reason = proposal.get("reason", "")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")
    raw_train_args = proposal.get("train_args")
    if not isinstance(raw_train_args, dict) or not raw_train_args:
        raise ValueError("proposal.train_args must be a non-empty object")

    train_args: dict[str, int | float | str] = {}
    for raw_flag, raw_value in raw_train_args.items():
        if not isinstance(raw_flag, str) or not raw_flag.strip():
            raise ValueError("proposal.train_args keys must be non-empty strings")
        flag = raw_flag.strip()
        if not flag.startswith("-"):
            flag = f"-{flag}"
        if flag not in FASTTEXT_PATCH_ALLOWED_ARGS:
            allowed = ", ".join(FASTTEXT_PATCH_ARG_ORDER)
            raise ValueError(f"unsupported fastText patch arg {flag!r}; allowed: {allowed}")
        train_args[flag] = _normalize_fasttext_patch_value(flag, raw_value)

    return {
        "proposal_id": proposal_id.strip(),
        "reason": reason.strip(),
        "validation_status": "accepted",
        "train_args": train_args,
        "fixed_train_args": {"-thread": 1, "-seed": 0},
        "official_scores_claimed": False,
    }


def _normalize_fasttext_patch_value(flag: str, raw_value: Any) -> int | float | str:
    rule = FASTTEXT_PATCH_ALLOWED_ARGS[flag]
    value_type = rule["type"]
    if value_type == "enum":
        value = str(raw_value)
        if value not in rule["values"]:
            raise ValueError(f"{flag} must be one of: {', '.join(rule['values'])}")
        return value
    if isinstance(raw_value, bool):
        raise ValueError(f"{flag} must be a number, not a boolean")
    if value_type == "int":
        value = int(raw_value)
    else:
        value = float(raw_value)
    minimum = rule["min"]
    maximum = rule["max"]
    if value < minimum or value > maximum:
        raise ValueError(f"{flag} must be between {minimum} and {maximum}")
    return value


def _fasttext_patch_arg_list(train_args: dict[str, int | float | str]) -> list[str]:
    argv: list[str] = []
    for flag in FASTTEXT_PATCH_ARG_ORDER:
        if flag in train_args:
            argv.extend([flag, str(train_args[flag])])
    return argv


def _render_fasttext_patch_diff(
    baseline_training_command: Any,
    patched_training_command: list[str],
) -> str:
    baseline = _command_to_text(baseline_training_command)
    patched = _command_to_text(patched_training_command)
    return (
        "--- a/fasttext-train-command\n"
        "+++ b/fasttext-train-command\n"
        "@@ -1 +1 @@\n"
        f"-{baseline}\n"
        f"+{patched}\n"
    )


def _command_to_text(command: Any) -> str:
    if isinstance(command, list):
        return " ".join(str(item) for item in command)
    if isinstance(command, str) and command:
        return command
    return "fasttext supervised -input data/train.txt -output model -thread 1 -seed 0"


def _fasttext_patch_loop_decision(*, improved: bool) -> dict[str, Any]:
    if improved:
        return {
            "decision": "continue_after_human_review",
            "reason_category": "metric_improved",
            "requires_human_confirmation": True,
            "recommended_next_action": "review_patch_round_then_try_next_proposal",
            "official_scores_claimed": False,
        }
    return {
        "decision": "revise_or_stop",
        "reason_category": "metric_not_improved",
        "requires_human_confirmation": True,
        "recommended_next_action": "revise_proposal_or_stop",
        "official_scores_claimed": False,
    }


def _safe_fasttext_proposal_id(raw_id: Any, index: int) -> str:
    if isinstance(raw_id, str) and raw_id.strip():
        cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", raw_id.strip()).strip("-")
        if cleaned:
            return cleaned[:80]
    return f"proposal-{index:03d}"


def _fasttext_multi_round_release_summary(
    multi_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if multi_payload is None:
        return {
            "included": False,
            "proposal_count": 0,
            "completed_count": 0,
            "failure_count": 0,
            "improved_count": 0,
            "rollback_events": 0,
            "best_metric": None,
            "best_source": None,
        }
    summary = dict(multi_payload.get("summary", {}))
    rollback_summary = dict(multi_payload.get("rollback_summary", {}))
    return {
        "included": True,
        "status": multi_payload.get("status"),
        "proposal_count": int(summary.get("proposal_count", 0)),
        "completed_count": int(summary.get("completed_count", 0)),
        "failure_count": int(summary.get("failure_count", 0)),
        "improved_count": int(summary.get("improved_count", 0)),
        "rollback_events": int(rollback_summary.get("rollback_events", 0)),
        "best_metric": summary.get("best_metric"),
        "best_source": summary.get("best_source"),
    }


def _fasttext_patch_proof_required_artifacts(
    report_path: Path,
    report: dict[str, Any],
) -> dict[str, Path]:
    report_dir = report_path.parent
    execution = report.get("execution", {})
    baseline = report.get("baseline", {})
    toolchain = report.get("toolchain", {})
    return {
        "improvement_report": report_path,
        "baseline_report": Path(str(baseline.get("report", ""))).expanduser(),
        "dataset_provenance": report_dir / "dataset-provenance.json",
        "runtime_probe": _resolve_report_relative_path(
            report_dir,
            toolchain.get("runtime_probe", "fasttext-runtime-probe.json"),
        ),
        "patch_proposal": _resolve_report_relative_path(
            report_dir,
            execution.get("proposal", "patch-proposal.json"),
        ),
        "patch_diff": _resolve_report_relative_path(
            report_dir,
            execution.get("patch_diff", "patch-diff.patch"),
        ),
        "train_log": _resolve_report_relative_path(
            report_dir,
            execution.get("training_log", "logs/fasttext-patch-train.log"),
        ),
        "test_log": _resolve_report_relative_path(
            report_dir,
            execution.get("evaluation_log", "logs/fasttext-patch-test.log"),
        ),
        "client_handoff": report_dir / "client-handoff.json",
    }


def _resolve_report_relative_path(base_dir: Path, value: Any) -> Path:
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else base_dir / path


def _fasttext_patch_blocked_public_claims(report: dict[str, Any]) -> list[str]:
    blocked = list(report.get("claim_gap", {}).get("blocked_claims", []))
    blocked.extend([
        "official_leaderboard_score",
        "full_paper_all_tables_reproduced",
        "arbitrary_unattended_research_improvement",
    ])
    deduped: list[str] = []
    for claim in blocked:
        if isinstance(claim, str) and claim and claim not in deduped:
            deduped.append(claim)
    return deduped


def _render_fasttext_patch_proof_summary(manifest: dict[str, Any]) -> str:
    metric = manifest["metric_summary"]
    return "\n".join([
        "# fastText AG News Patch Proof Bundle",
        "",
        f"- Stage: `{manifest['stage']}`",
        f"- Review status: `{manifest['review_status']}`",
        f"- Baseline P@1: `{metric.get('baseline_p_at_1')}`",
        f"- Patch P@1: `{metric.get('p_at_1')}`",
        f"- Delta: `{metric.get('delta')}`",
        f"- Improved: `{metric.get('improved')}`",
        f"- Artifact count: `{manifest['artifact_count']}`",
        f"- Claim boundary: {manifest['claim_boundary']}",
        "- `official_scores_claimed=false`",
        "",
        "## Artifacts",
        "",
        *[
            (
                f"- `{item['role']}` -> `{item['archive_relative_path']}` "
                f"sha256 `{item['sha256']}`"
            )
            for item in manifest["artifacts"]
        ],
        "",
    ])


def _render_fasttext_release_review_checklist(manifest: dict[str, Any]) -> str:
    download = manifest["download_artifact"]
    multi_summary = manifest["multi_round_summary"]
    return "\n".join([
        "# fastText Release Proof Review Checklist",
        "",
        "## Claim Boundary",
        "",
        f"- {manifest['claim_boundary']}",
        "- `official_scores_claimed=false` must remain true for every included artifact.",
        "",
        "## Download Artifact",
        "",
        f"- Bundle: `{Path(download['path']).name}`",
        f"- SHA-256: `{download['sha256']}`",
        "- Verify locally with `shasum -a 256 -c release-proof-bundle.sha256`.",
        "- Inspect archive contents with `tar -tzf release-proof-bundle.tar.gz`.",
        "",
        "## Review Checks",
        "",
        "- Confirm the P4 proof manifest, artifact index, SHA256SUMS, and human review report are present.",
        "- Confirm the P5 multi-round report is present when `multi_round_summary.included=true`.",
        "- Confirm failures or rejected proposals are preserved instead of hidden.",
        "- Confirm rollback events keep the best reviewed metric rather than promoting failed rounds.",
        "- Confirm no public doc claims official leaderboard, full-paper reproduction, or arbitrary autonomous improvement.",
        "",
        "## Included Multi-Round Summary",
        "",
        f"- Included: `{multi_summary['included']}`",
        f"- Proposals: `{multi_summary['proposal_count']}`",
        f"- Failed proposals: `{multi_summary['failure_count']}`",
        f"- Rollback events: `{multi_summary['rollback_events']}`",
        f"- Best metric: `{multi_summary['best_metric']}`",
        "",
    ])


def _redact_command_paths(argv: list[str], output_dir: Path) -> list[str]:
    redacted: list[str] = []
    for value in argv:
        try:
            path = Path(value)
            if path.is_absolute() and path.resolve().is_relative_to(output_dir):
                redacted.append(path.resolve().relative_to(output_dir).as_posix())
                continue
        except (OSError, ValueError):
            pass
        redacted.append(value)
    return redacted


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
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


def _fasttext_binary_dataset_limitations(provenance_limitations: list[str]) -> list[str]:
    limitations = [
        item
        for item in provenance_limitations
        if "python fallback" not in item.lower()
    ]
    limitations.append(
        "selected fastText-compatible binary result with archived train/test logs; "
        "official leaderboard score not claimed"
    )
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


def _fasttext_binary_baseline_gap_summary(
    *,
    full_dataset_ready: bool,
    within_tolerance: bool,
) -> str:
    if full_dataset_ready and within_tolerance:
        return (
            "The selected fastText-compatible binary run is within tolerance on the "
            "full-size dataset; archive review is still required before stronger claims."
        )
    if not full_dataset_ready:
        return (
            "The fastText-compatible binary path executed, but the provided AG News CSV "
            "does not match the full expected row counts, so full reproduction remains blocked."
        )
    return (
        "The full-size dataset path executed, but the observed P@1 is outside the configured "
        "paper-target tolerance."
    )
