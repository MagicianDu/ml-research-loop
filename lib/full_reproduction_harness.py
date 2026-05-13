"""Harness for full-paper reproduction baseline runs."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import time
from typing import Any


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


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
