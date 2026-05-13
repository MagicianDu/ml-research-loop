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
