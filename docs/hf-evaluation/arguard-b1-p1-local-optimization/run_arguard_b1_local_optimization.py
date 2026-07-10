from __future__ import annotations

import argparse
import csv
import json
import subprocess
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer
from sklearn.svm import LinearSVC


LABELS = ["safe", "unsafe"]


def _git_output(repo_dir: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path).fillna("")


def _normalise_labels(frame: pd.DataFrame) -> pd.DataFrame:
    normalised = frame.copy()
    normalised["label"] = normalised["label"].astype(str).str.strip().str.lower()
    return normalised


def _split_valid_labels(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    normalised = _normalise_labels(frame)
    valid_mask = normalised["label"].isin(LABELS)
    return normalised.loc[valid_mask].copy(), normalised.loc[~valid_mask].copy()


def _text_series(frame: pd.DataFrame) -> pd.Series:
    dialect = frame.get("dialect", "").astype(str)
    return frame["prompt"].astype(str) + " dialect_" + dialect


def _safe_ids(frame: pd.DataFrame, mask: Any, limit: int = 8) -> list[str]:
    return [str(value) for value in frame.loc[mask, "id"].head(limit).tolist()]


def _label_distribution(values: pd.Series) -> dict[str, int]:
    counts = Counter(values.astype(str).tolist())
    return {label: int(counts.get(label, 0)) for label in LABELS}


def _evaluate(frame: pd.DataFrame, predictions: list[str]) -> dict[str, Any]:
    y_true = frame["label"].astype(str).tolist()
    macro_f1 = float(f1_score(y_true, predictions, labels=LABELS, average="macro"))
    report = classification_report(
        y_true,
        predictions,
        labels=LABELS,
        output_dict=True,
        zero_division=0,
    )
    matrix = confusion_matrix(y_true, predictions, labels=LABELS)
    unsafe_predicted_safe = [truth == "unsafe" and pred == "safe" for truth, pred in zip(y_true, predictions)]
    safe_predicted_unsafe = [truth == "safe" and pred == "unsafe" for truth, pred in zip(y_true, predictions)]
    return {
        "macro_f1": macro_f1,
        "per_label": {
            label: {
                "precision": float(report[label]["precision"]),
                "recall": float(report[label]["recall"]),
                "f1": float(report[label]["f1-score"]),
                "support": int(report[label]["support"]),
            }
            for label in LABELS
        },
        "confusion_matrix": {
            "labels": LABELS,
            "rows_are_truth_columns_are_prediction": matrix.astype(int).tolist(),
        },
        "failure_analysis": {
            "unsafe_predicted_safe_count": int(sum(unsafe_predicted_safe)),
            "safe_predicted_unsafe_count": int(sum(safe_predicted_unsafe)),
            "unsafe_predicted_safe_ids_sample": _safe_ids(frame, unsafe_predicted_safe),
            "safe_predicted_unsafe_ids_sample": _safe_ids(frame, safe_predicted_unsafe),
        },
    }


def _majority_predictions(train: pd.DataFrame, frame: pd.DataFrame) -> list[str]:
    majority = train["label"].astype(str).mode().iloc[0]
    return [majority] * len(frame)


def _text_selector() -> FunctionTransformer:
    return FunctionTransformer(lambda frame: _text_series(frame), validate=False)


def _prompt_selector() -> FunctionTransformer:
    return FunctionTransformer(lambda frame: frame["prompt"].astype(str), validate=False)


def _candidate_specs() -> list[dict[str, Any]]:
    return [
        {
            "trial_id": "b1-round-001-word-logreg",
            "round": 1,
            "optimizer_source": "sklearn_logreg",
            "operator_id": "adapt.lexical_word_ngram",
            "why_this_operator_applies": "B1 is a binary text classification task; word n-grams are the cheapest lexical safety baseline.",
            "hypothesis": "Arabic harmful-prompt labels expose repeated lexical and phrase cues that a balanced linear model can capture.",
            "change_surface": "Prompt text vectorizer and linear classifier only.",
            "expected_effect": "Beat majority baseline on macro-F1 without relying on external scorer.",
            "risk": "Dialect spelling variation and obfuscation may make word tokens brittle.",
            "cheapest_validation": "Train on public train.csv and compute local macro-F1 on dev_with_label.csv.",
            "rollback_stop_condition": "Prune if macro-F1 does not improve the current best local gate score.",
            "estimator": Pipeline(
                [
                    ("text", _prompt_selector()),
                    ("tfidf", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, max_features=60000)),
                    ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", solver="liblinear", C=1.0)),
                ]
            ),
        },
        {
            "trial_id": "b1-round-002-char-logreg",
            "round": 2,
            "optimizer_source": "sklearn_logreg",
            "operator_id": "adapt.character_robustness",
            "why_this_operator_applies": "Arabic dialect, spelling variation, and unsafe-content obfuscation make character features useful.",
            "hypothesis": "Character n-grams will reduce unsafe-as-safe misses relative to word-only features.",
            "change_surface": "Replace word tokenization with char_wb n-grams.",
            "expected_effect": "Improve macro-F1 and unsafe recall on local dev.",
            "risk": "Character features may overfit short artifacts and increase safe-as-unsafe errors.",
            "cheapest_validation": "Compare local macro-F1 and confusion matrix against round 1.",
            "rollback_stop_condition": "Prune if it fails to beat the current best macro-F1.",
            "estimator": Pipeline(
                [
                    ("text", _prompt_selector()),
                    ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=90000)),
                    ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", solver="liblinear", C=1.0)),
                ]
            ),
        },
        {
            "trial_id": "b1-round-003-word-char-logreg",
            "round": 3,
            "optimizer_source": "sklearn_logreg",
            "operator_id": "combine.word_and_character_views",
            "why_this_operator_applies": "The previous two candidates test complementary lexical views; B1 may benefit from combining them.",
            "hypothesis": "A combined word+character representation captures phrase cues and spelling robustness together.",
            "change_surface": "Feature union only; same linear classifier family.",
            "expected_effect": "Improve macro-F1 while keeping the method simple and reproducible.",
            "risk": "Higher-dimensional features may overfit dev and slow iteration.",
            "cheapest_validation": "One local train/dev run with the same gate.",
            "rollback_stop_condition": "Prune if it does not beat the current best score by the gate delta.",
            "estimator": Pipeline(
                [
                    ("text", _prompt_selector()),
                    (
                        "features",
                        FeatureUnion(
                            [
                                ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, max_features=50000)),
                                ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=70000)),
                            ]
                        ),
                    ),
                    ("clf", LogisticRegression(max_iter=1200, class_weight="balanced", solver="liblinear", C=2.0)),
                ]
            ),
        },
        {
            "trial_id": "b1-round-004-char-linear-svc",
            "round": 4,
            "optimizer_source": "sklearn_linear_svc",
            "operator_id": "substitute.margin_classifier",
            "why_this_operator_applies": "After feature-view search, substitute the classifier to test a large-margin objective.",
            "hypothesis": "LinearSVC may separate sparse Arabic safety features better than logistic regression.",
            "change_surface": "Classifier objective only, preserving character robustness.",
            "expected_effect": "Improve macro-F1 or reduce high-risk unsafe-as-safe errors.",
            "risk": "May trade calibration and safe recall for margin accuracy.",
            "cheapest_validation": "Same local train/dev gate and confusion analysis.",
            "rollback_stop_condition": "Prune if macro-F1 regresses versus current best.",
            "estimator": Pipeline(
                [
                    ("text", _prompt_selector()),
                    ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 6), min_df=2, max_features=100000)),
                    ("clf", LinearSVC(class_weight="balanced", C=0.7, max_iter=5000)),
                ]
            ),
        },
        {
            "trial_id": "b1-round-005-dialect-word-char-logreg",
            "round": 5,
            "optimizer_source": "sklearn_logreg",
            "operator_id": "combine.dialect_conditioned_text",
            "why_this_operator_applies": "The released data includes dialect; dialect-conditioned text may capture distribution shifts cheaply.",
            "hypothesis": "Appending dialect as a stable token helps separate dialect-specific lexical risk cues.",
            "change_surface": "Input representation includes dialect token plus prompt text.",
            "expected_effect": "Improve macro-F1 or keep score while reducing dialect-specific misses.",
            "risk": "Dialect token can encode split artifacts and overfit local dev.",
            "cheapest_validation": "Use the same train/dev gate and do not claim official improvement.",
            "rollback_stop_condition": "Prune if it does not improve the current best local gate score.",
            "estimator": Pipeline(
                [
                    ("text", _text_selector()),
                    (
                        "features",
                        FeatureUnion(
                            [
                                ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, max_features=50000)),
                                ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=70000)),
                            ]
                        ),
                    ),
                    ("clf", LogisticRegression(max_iter=1200, class_weight="balanced", solver="liblinear", C=1.5)),
                ]
            ),
        },
    ]


def _prediction_rows(ids: list[Any], labels: list[str]) -> list[dict[str, str]]:
    return [
        {"id": str(row_id), "prediction": str(label)}
        for row_id, label in zip(ids, labels)
    ]


def _write_prediction_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "prediction"],
            delimiter=",",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_prediction_zip(zip_path: Path, csv_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(csv_path, arcname="prediction.csv")


def _prediction_format_status(path: Path, expected_rows: int) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=",")
        rows = list(reader)
    labels = {row.get("prediction", "") for row in rows}
    return {
        "path": path.name,
        "header": reader.fieldnames,
        "header_ok": reader.fieldnames == ["id", "prediction"],
        "row_count": len(rows),
        "row_count_ok": len(rows) == expected_rows,
        "labels": sorted(labels),
        "labels_ok": labels.issubset(set(LABELS)),
        "format_ready": reader.fieldnames == ["id", "prediction"]
        and len(rows) == expected_rows
        and labels.issubset(set(LABELS)),
    }


def _zip_format_status(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path, "r") as archive:
        names = sorted(archive.namelist())
    return {
        "path": path.name,
        "members": names,
        "contains_prediction_csv": names == ["prediction.csv"],
        "format_ready": names == ["prediction.csv"],
    }


def run(
    repo_dir: Path,
    output_dir: Path,
    rounds: int,
    codabench_user: str = "",
    codabench_registered: bool = False,
) -> dict[str, Any]:
    task_dir = repo_dir / "taskB"
    data_dir = task_dir / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    train_path = data_dir / "train.csv"
    dev_labeled_path = data_dir / "dev_with_label.csv"
    dev_unlabeled_path = data_dir / "dev_without_label.csv"

    source_files = [
        str(path.relative_to(task_dir))
        for path in sorted(task_dir.glob("**/*"))
        if path.is_file()
    ]
    readiness = {
        "schema_version": "2026-06-29.arguard-b1-source-readiness.v1",
        "target_id": "arguard-b1-binary-classification",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source_repo": {
            "url": "https://github.com/araieval/ArGuard-2026-tasks",
            "commit": _git_output(repo_dir, ["rev-parse", "HEAD"]),
            "commit_time": _git_output(repo_dir, ["log", "-1", "--format=%cI"]),
            "commit_subject": _git_output(repo_dir, ["log", "-1", "--format=%s"]),
        },
        "taskB_files": source_files,
        "assets": {
            "train_csv": train_path.exists(),
            "dev_with_label_csv": dev_labeled_path.exists(),
            "dev_without_label_csv": dev_unlabeled_path.exists(),
            "scorer_script_released": any(path.suffix == ".py" for path in (task_dir / "scorer").glob("**/*") if path.is_file()),
            "format_checker_script_released": any(
                path.suffix == ".py" for path in (task_dir / "format_checker").glob("**/*") if path.is_file()
            ),
            "baseline_script_released": any(path.suffix == ".py" for path in (task_dir / "baselines").glob("**/*") if path.is_file()),
        },
        "codabench_browser_observation": {
            "competition_url": "https://www.codabench.org/competitions/16652/",
            "competition_title": "ArGuard-Subtask-B1-Binary Classification",
            "logged_in_user": codabench_user,
            "login_observed": bool(codabench_user),
            "registered_for_competition": codabench_registered,
            "phase_observed": "Development Phase",
            "phase_end_gmt_plus_8": "2026-07-19 08:00",
            "submission_format_observed": {
                "archive_filename": "prediction.zip",
                "csv_filename": "prediction.csv",
                "csv_encoding": "UTF-8",
                "columns": ["id", "prediction"],
                "allowed_prediction_values": LABELS,
            },
        },
        "official_scores_claimed": False,
        "claim_boundary": "Public train/dev local evidence only; no Codabench submission and no official leaderboard claim.",
    }

    raw_train = _read_csv(train_path)
    raw_dev = _read_csv(dev_labeled_path)
    train, invalid_train = _split_valid_labels(raw_train)
    dev, invalid_dev = _split_valid_labels(raw_dev)
    dev_unlabeled = _read_csv(dev_unlabeled_path)
    readiness["data_quality"] = {
        "raw_train_rows": int(len(raw_train)),
        "train_rows_after_label_filter": int(len(train)),
        "dropped_train_rows_with_invalid_label": int(len(invalid_train)),
        "dropped_train_ids_with_invalid_label": [str(value) for value in invalid_train["id"].tolist()],
        "raw_dev_with_label_rows": int(len(raw_dev)),
        "dev_with_label_rows_after_label_filter": int(len(dev)),
        "dropped_dev_rows_with_invalid_label": int(len(invalid_dev)),
        "dropped_dev_ids_with_invalid_label": [str(value) for value in invalid_dev["id"].tolist()],
    }

    baseline_predictions = _majority_predictions(train, dev)
    baseline_eval = _evaluate(dev, baseline_predictions)
    best_score = baseline_eval["macro_f1"]
    best_trial_id = "b1-baseline-majority"
    best_model: Any = None
    best_evaluation: dict[str, Any] = baseline_eval

    memory: dict[str, float] = {"baseline.majority": 1.0}
    trials: list[dict[str, Any]] = [
        {
            "trial_id": best_trial_id,
            "trial_number": 0,
            "state": "COMPLETE",
            "params": {
                "operator": "baseline.majority",
                "adapter": "local_sklearn_free",
                "slice": "public_train_to_dev_with_label",
                "patch_scope": "none",
                "model": "majority_label",
                "budget": "single_pass",
            },
            "value": best_score,
            "gate": {
                "decision": "BASELINE",
                "reason": "Initial local macro-F1 baseline.",
            },
            "user_attrs": {
                "trace": "Majority label baseline computed before optimizer rounds.",
                "artifact_refs": ["source-readiness.json"],
                "claim_boundary": readiness["claim_boundary"],
                "hard_blockers": [],
            },
            "evaluation": baseline_eval,
        }
    ]
    round_summaries: list[dict[str, Any]] = []

    train_x = train.copy()
    train_y = train["label"].astype(str)
    dev_x = dev.copy()
    min_delta = 0.001

    for spec in _candidate_specs()[:rounds]:
        trial_id = spec["trial_id"]
        proposal = {
            key: spec[key]
            for key in [
                "operator_id",
                "why_this_operator_applies",
                "hypothesis",
                "change_surface",
                "expected_effect",
                "risk",
                "cheapest_validation",
                "rollback_stop_condition",
            ]
        }
        analysis_before_proposal = best_evaluation.get("failure_analysis", {})
        model = spec["estimator"]
        state = "COMPLETE"
        hard_blockers: list[str] = []
        try:
            model.fit(train_x, train_y)
            predictions = model.predict(dev_x).astype(str).tolist()
            evaluation = _evaluate(dev, predictions)
            score = evaluation["macro_f1"]
            if score >= best_score + min_delta:
                decision = "PASS"
                reason = f"Local macro-F1 improved from {best_score:.6f} to {score:.6f}."
                best_score = score
                best_trial_id = trial_id
                best_model = model
                best_evaluation = evaluation
                memory[spec["operator_id"]] = memory.get(spec["operator_id"], 1.0) + 1.0
            else:
                decision = "PRUNE"
                reason = f"Local macro-F1 {score:.6f} did not improve current best {best_score:.6f} by delta {min_delta}."
                memory[spec["operator_id"]] = max(0.1, memory.get(spec["operator_id"], 1.0) - 0.25)
        except Exception as exc:  # pragma: no cover - evidence script fallback path
            state = "FAIL"
            score = None
            decision = "BLOCK"
            reason = f"Candidate failed during local train/dev validation: {exc}"
            hard_blockers = ["candidate_runtime_failure"]
            evaluation = {"error": str(exc)}
            memory[spec["operator_id"]] = max(0.1, memory.get(spec["operator_id"], 1.0) - 1.0)

        trial = {
            "trial_id": trial_id,
            "trial_number": spec["round"],
            "state": state,
            "params": {
                "operator": spec["operator_id"],
                "adapter": spec["optimizer_source"],
                "slice": "public_train_to_dev_with_label",
                "patch_scope": spec["change_surface"],
                "model": type(spec["estimator"].steps[-1][1]).__name__,
                "budget": "single_local_fit",
            },
            "value": score,
            "gate": {
                "decision": decision,
                "reason": reason,
                "metric": "local_macro_f1",
                "official_scores_claimed": False,
            },
            "proposal": proposal,
            "user_attrs": {
                "trace": {
                    "optimizer_source": spec["optimizer_source"],
                    "llm_or_operator_reasoning_trace": proposal,
                    "analysis_before_proposal": analysis_before_proposal,
                },
                "artifact_refs": ["local-optimization-run.json", "source-readiness.json"],
                "claim_boundary": readiness["claim_boundary"],
                "hard_blockers": hard_blockers,
            },
            "evaluation": evaluation,
        }
        trials.append(trial)
        round_summaries.append(
            {
                "round": spec["round"],
                "trial_id": trial_id,
                "operator_id": spec["operator_id"],
                "gate_decision": decision,
                "value": score,
                "best_after_round": best_score,
                "best_trial_after_round": best_trial_id,
                "memory_after_round": dict(sorted(memory.items())),
            }
        )

    if best_model is None:
        dev_submission_predictions = baseline_predictions
        unlabeled_predictions = _majority_predictions(train, dev_unlabeled)
    else:
        dev_submission_predictions = best_model.predict(dev.copy()).astype(str).tolist()
        unlabeled_predictions = best_model.predict(dev_unlabeled.copy()).astype(str).tolist()

    dev_diagnostic_path = output_dir / "local-diagnostic-dev-with-label.csv"
    prediction_csv_path = output_dir / "prediction.csv"
    prediction_zip_path = output_dir / "prediction.zip"
    _write_prediction_csv(dev_diagnostic_path, _prediction_rows(dev["id"].tolist(), dev_submission_predictions))
    _write_prediction_csv(
        prediction_csv_path,
        _prediction_rows(dev_unlabeled["id"].tolist(), unlabeled_predictions),
    )
    _write_prediction_zip(prediction_zip_path, prediction_csv_path)

    submission_gate = {
        "schema_version": "2026-06-29.arguard-b1-submission-gate.v1",
        "target_id": "arguard-b1-binary-classification",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "best_local_trial_id": best_trial_id,
        "best_local_macro_f1": best_score,
        "codabench_page_submission_contract": {
            "competition_url": "https://www.codabench.org/competitions/16652/",
            "archive_filename": "prediction.zip",
            "csv_filename": "prediction.csv",
            "csv_encoding": "UTF-8",
            "columns": ["id", "prediction"],
            "allowed_prediction_values": LABELS,
            "observed_logged_in_user": codabench_user,
            "registered_for_competition": codabench_registered,
        },
        "local_submission_package": {
            "diagnostic_dev_with_label_csv": _prediction_format_status(dev_diagnostic_path, len(dev)),
            "codabench_prediction_csv": _prediction_format_status(prediction_csv_path, len(dev_unlabeled)),
            "codabench_prediction_zip": _zip_format_status(prediction_zip_path),
        },
        "ready_for_manual_codabench_submission": codabench_registered,
        "manual_submission_required": True,
        "official_scores_claimed": False,
        "blockers": [] if codabench_registered else ["codabench_competition_registration_required"],
        "limitations": [
            "official_scorer_script_not_released_in_public_github_repo",
            "official_format_checker_script_not_released_in_public_github_repo",
            "no_codabench_submission_uploaded_in_this_run",
            "official_scores_claimed_false_until_public_result_verifier_confirms_submission_result",
        ],
        "claim_boundary": readiness["claim_boundary"],
    }

    payload = {
        "schema_version": "2026-06-29.arguard-b1-local-optimization-run.v1",
        "target_id": "arguard-b1-binary-classification",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "local_optimization_run",
        "official_scores_claimed": False,
        "metric": "local_macro_f1",
        "dataset": {
            "train_rows": int(len(train)),
            "dev_with_label_rows": int(len(dev)),
            "dev_without_label_rows": int(len(dev_unlabeled)),
            "dropped_train_rows_with_invalid_label": int(len(invalid_train)),
            "dropped_dev_rows_with_invalid_label": int(len(invalid_dev)),
            "train_label_distribution": _label_distribution(train["label"]),
            "dev_label_distribution": _label_distribution(dev["label"]),
        },
        "source_readiness_ref": "source-readiness.json",
        "submission_gate_ref": "codabench-submission-gate.json",
        "baseline_trial_id": "b1-baseline-majority",
        "best_trial_id": best_trial_id,
        "best_local_macro_f1": best_score,
        "round_count": len(round_summaries),
        "rounds": round_summaries,
        "trials": trials,
        "gate_feedback_memory": dict(sorted(memory.items())),
        "claim_boundary": readiness["claim_boundary"],
    }

    (output_dir / "source-readiness.json").write_text(
        json.dumps(readiness, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "local-optimization-run.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "codabench-submission-gate.json").write_text(
        json.dumps(submission_gate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(
        "\n".join(
            [
                "# ArGuard B1 P1 本地优化证据",
                "",
                "本目录记录一次公开 train/dev 上的本地 baseline、5 轮 optimizer/gate 和 submission gate。",
                "",
                "## 结论",
                "",
                f"- best local trial: `{best_trial_id}`",
                f"- best local macro-F1: `{best_score:.6f}`",
                f"- train 清洗后 `{len(train)}` 行；过滤空/非法 label `{len(invalid_train)}` 行。",
                "- 5 轮 gate 里 `word_char_logreg` 成为当前 best，后续 `LinearSVC` 和 dialect-conditioned 变体被剪枝。",
                "- 登录态页面确认 Codabench 要上传 `prediction.zip`，其中包含 UTF-8 `prediction.csv`，列为 `id,prediction`。",
                "- `official_scores_claimed=false`：未提交 Codabench，未宣称官方榜单成绩。",
                f"- Codabench submission gate 当前为 `ready_for_manual_codabench_submission={str(codabench_registered).lower()}`。",
                "",
                "## 阻断",
                "",
                (
                    "- 当前登录用户已注册参赛，页面出现 `Submission upload`；下一步仍需人工授权上传。"
                    if codabench_registered
                    else "- 当前登录用户可见竞赛页，但尚未注册参赛；注册需要接受 Codabench terms，属于外部状态变更。"
                ),
                "- 公开仓库有 train/dev 数据，但 official scorer 和 format checker 仍未释放为可执行脚本；最终成绩只能由 Codabench submission/result 验证。",
                "",
                "## 文件",
                "",
                "- `source-readiness.json`：公开仓库资产和源码状态。",
                "- `local-optimization-run.json`：baseline、每轮 proposal、gate、trial、memory。",
                "- `codabench-submission-gate.json`：Codabench 页面确认的提交格式检查和人工提交阻断。",
                "- `local-diagnostic-dev-with-label.csv`：对 dev_with_label 的本地诊断预测。",
                "- `prediction.csv`：对 dev_without_label 的 Codabench 格式预测文件。",
                "- `prediction.zip`：待人工确认后上传的 Codabench submission package。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--codabench-user", default="")
    parser.add_argument("--codabench-registered", action="store_true")
    args = parser.parse_args()
    payload = run(
        args.repo_dir,
        args.output_dir,
        args.rounds,
        codabench_user=args.codabench_user,
        codabench_registered=args.codabench_registered,
    )
    print(json.dumps({"best_trial_id": payload["best_trial_id"], "best_local_macro_f1": payload["best_local_macro_f1"]}))


if __name__ == "__main__":
    main()
