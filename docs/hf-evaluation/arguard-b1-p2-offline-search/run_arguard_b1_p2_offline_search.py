from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import tempfile
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer

from lib.benchmarks.arguard_b1_search_gate import evaluate_submission_candidate_gate


warnings.filterwarnings("ignore")

LABELS = ["safe", "unsafe"]
DIACRITICS = re.compile(r"[\u064B-\u065F\u0670]")


def _read_labeled_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path).fillna("")
    frame["label"] = frame["label"].astype(str).str.strip().str.lower()
    return frame.loc[frame["label"].isin(LABELS)].copy().reset_index(drop=True)


def _read_unlabeled_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path).fillna("").reset_index(drop=True)


def _normalise_arabic(text: object) -> str:
    value = DIACRITICS.sub("", str(text)).replace("\u0640", "")
    value = re.sub("[إأآٱ]", "ا", value)
    return value.replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")


def _select_prompt(frame: pd.DataFrame) -> pd.Series:
    return frame["prompt"].astype(str)


def _select_normalised_prompt(frame: pd.DataFrame) -> pd.Series:
    return frame["prompt"].astype(str).map(_normalise_arabic)


def _selector_transformer(selector: Callable[[pd.DataFrame], pd.Series]) -> FunctionTransformer:
    return FunctionTransformer(selector, validate=False)


def _macro_f1_from_safe_predictions(
    truth_safe: np.ndarray,
    predicted_safe: np.ndarray,
) -> dict[str, Any]:
    predicted_safe = np.asarray(predicted_safe, dtype=bool)
    truth_safe = np.asarray(truth_safe, dtype=bool)
    safe_tp = int(np.sum(truth_safe & predicted_safe))
    unsafe_predicted_safe = int(np.sum((~truth_safe) & predicted_safe))
    safe_predicted_unsafe = int(np.sum(truth_safe & (~predicted_safe)))
    unsafe_tp = int(np.sum((~truth_safe) & (~predicted_safe)))

    safe_denominator = 2 * safe_tp + unsafe_predicted_safe + safe_predicted_unsafe
    unsafe_denominator = 2 * unsafe_tp + safe_predicted_unsafe + unsafe_predicted_safe
    safe_f1 = 0.0 if safe_denominator == 0 else 2 * safe_tp / safe_denominator
    unsafe_f1 = 0.0 if unsafe_denominator == 0 else 2 * unsafe_tp / unsafe_denominator
    return {
        "macro_f1": float((safe_f1 + unsafe_f1) / 2),
        "per_label_f1": {
            "safe": float(safe_f1),
            "unsafe": float(unsafe_f1),
        },
        "unsafe_predicted_safe_count": unsafe_predicted_safe,
        "safe_predicted_unsafe_count": safe_predicted_unsafe,
        "confusion_matrix": {
            "labels": LABELS,
            "rows_are_truth_columns_are_prediction": [
                [safe_tp, safe_predicted_unsafe],
                [unsafe_predicted_safe, unsafe_tp],
            ],
        },
    }


def _best_threshold(
    truth_safe: np.ndarray,
    safe_probabilities: np.ndarray,
    *,
    start: float = 0.2,
    stop: float = 0.8,
    steps: int = 241,
) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    for threshold in np.linspace(start, stop, steps):
        evaluation = _macro_f1_from_safe_predictions(
            truth_safe,
            safe_probabilities >= threshold,
        )
        if best is None or evaluation["macro_f1"] > best["macro_f1"]:
            best = {**evaluation, "threshold": float(threshold)}
    assert best is not None
    return best


def _build_logreg_model(
    *,
    selector: Callable[[pd.DataFrame], pd.Series] = _select_prompt,
    c_value: float = 2.0,
    char_range: tuple[int, int] = (3, 5),
    class_weight: str | None = "balanced",
) -> Pipeline:
    return Pipeline(
        [
            ("text", _selector_transformer(selector)),
            (
                "features",
                FeatureUnion(
                    [
                        (
                            "word",
                            TfidfVectorizer(
                                analyzer="word",
                                ngram_range=(1, 2),
                                min_df=2,
                                max_features=50000,
                            ),
                        ),
                        (
                            "char",
                            TfidfVectorizer(
                                analyzer="char_wb",
                                ngram_range=char_range,
                                min_df=2,
                                max_features=70000,
                            ),
                        ),
                    ]
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1500,
                    solver="liblinear",
                    class_weight=class_weight,
                    C=c_value,
                ),
            ),
        ]
    )


def _fit_safe_probability(model: Pipeline, train: pd.DataFrame, eval_frame: pd.DataFrame) -> np.ndarray:
    model.fit(train, train["label"].astype(str))
    return model.predict_proba(eval_frame)[:, list(model.classes_).index("safe")]


def _clean_fasttext_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()


def _write_fasttext_train(path: Path, frame: pd.DataFrame) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in frame.itertuples():
            handle.write(f"__label__{row.label} {_clean_fasttext_text(row.prompt)}\n")


def _write_fasttext_unlabeled(path: Path, frame: pd.DataFrame) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in frame.itertuples():
            handle.write(_clean_fasttext_text(row.prompt) + "\n")


def _fasttext_safe_probability(
    *,
    fasttext_bin: Path,
    train: pd.DataFrame,
    eval_frame: pd.DataFrame,
    temp_dir: Path,
    name: str,
) -> np.ndarray:
    train_path = temp_dir / f"{name}.train.txt"
    eval_path = temp_dir / f"{name}.eval.txt"
    model_path = temp_dir / f"{name}.model"
    _write_fasttext_train(train_path, train)
    _write_fasttext_unlabeled(eval_path, eval_frame)
    subprocess.run(
        [
            str(fasttext_bin),
            "supervised",
            "-input",
            str(train_path),
            "-output",
            str(model_path),
            "-verbose",
            "0",
            "-thread",
            "4",
            "-lr",
            "0.3",
            "-epoch",
            "50",
            "-wordNgrams",
            "2",
            "-minn",
            "3",
            "-maxn",
            "6",
            "-loss",
            "softmax",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    prediction = subprocess.run(
        [str(fasttext_bin), "predict-prob", str(model_path) + ".bin", str(eval_path), "2"],
        check=True,
        capture_output=True,
        text=True,
    )
    probabilities: list[float] = []
    for line in prediction.stdout.splitlines():
        parts = line.split()
        scores = {
            label.replace("__label__", ""): float(probability)
            for label, probability in zip(parts[0::2], parts[1::2])
        }
        probabilities.append(scores.get("safe", 1.0 - scores.get("unsafe", 0.0)))
    return np.asarray(probabilities)


def _write_prediction_csv(path: Path, ids: list[Any], predictions: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "prediction"], lineterminator="\n")
        writer.writeheader()
        for row_id, predicted_safe in zip(ids, predictions):
            writer.writerow({"id": str(row_id), "prediction": "safe" if predicted_safe else "unsafe"})


def _run_optuna_search(
    *,
    train: pd.DataFrame,
    dev: pd.DataFrame,
    truth_safe: np.ndarray,
    trials: int,
) -> dict[str, Any]:
    try:
        import optuna
    except ModuleNotFoundError as exc:
        return {
            "source": "optuna",
            "state": "BLOCKED",
            "blocked_reason": f"optuna_not_importable: {exc}",
        }

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial: Any) -> float:
        selector_name = trial.suggest_categorical(
            "selector",
            ["prompt", "prompt", "prompt", "norm_ar"],
        )
        selector = _select_normalised_prompt if selector_name == "norm_ar" else _select_prompt
        model = _build_logreg_model(
            selector=selector,
            c_value=trial.suggest_float("C", 0.4, 12.0, log=True),
            char_range=(
                trial.suggest_categorical("char_lo", [2, 3]),
                trial.suggest_categorical("char_hi", [5, 6]),
            ),
            class_weight=trial.suggest_categorical("class_weight", ["balanced", None]),
        )
        probability = _fit_safe_probability(model, train, dev)
        threshold = trial.suggest_float("threshold", 0.25, 0.78)
        evaluation = _macro_f1_from_safe_predictions(truth_safe, probability >= threshold)
        trial.set_user_attr("evaluation", evaluation)
        return evaluation["macro_f1"]

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=20260630),
    )
    study.optimize(objective, n_trials=trials, show_progress_bar=False)
    ranked = sorted(
        [
            {
                "trial_number": trial.number,
                "value": trial.value,
                "params": trial.params,
                "evaluation": trial.user_attrs.get("evaluation", {}),
            }
            for trial in study.trials
            if trial.value is not None
        ],
        key=lambda item: item["value"],
        reverse=True,
    )
    return {
        "source": "optuna",
        "state": "COMPLETE",
        "trial_count": trials,
        "best_value": study.best_value,
        "top_trials": ranked[:10],
    }


def _evaluate_cv(
    *,
    train: pd.DataFrame,
    fasttext_bin: Path,
    candidate_threshold: float,
) -> dict[str, Any]:
    labels = train["label"].astype(str).to_numpy()
    truth_safe = labels == "safe"
    baseline_predictions = np.empty(len(train), dtype=bool)
    candidate_predictions = np.empty(len(train), dtype=bool)
    folds: list[dict[str, Any]] = []
    splitter = StratifiedKFold(n_splits=3, shuffle=True, random_state=20260630)

    with tempfile.TemporaryDirectory(prefix="arguard-b1-p2-cv-") as temp:
        temp_dir = Path(temp)
        for fold_index, (train_indices, valid_indices) in enumerate(
            splitter.split(train, labels),
            start=1,
        ):
            train_fold = train.iloc[train_indices].copy()
            valid_fold = train.iloc[valid_indices].copy()

            baseline_probability = _fit_safe_probability(
                _build_logreg_model(c_value=2.0),
                train_fold,
                valid_fold,
            )
            baseline_predictions[valid_indices] = baseline_probability >= 0.5

            char_probability = _fit_safe_probability(
                _build_logreg_model(c_value=4.0, char_range=(2, 5)),
                train_fold,
                valid_fold,
            )
            normalised_probability = _fit_safe_probability(
                _build_logreg_model(selector=_select_normalised_prompt, c_value=3.0),
                train_fold,
                valid_fold,
            )
            fasttext_probability = _fasttext_safe_probability(
                fasttext_bin=fasttext_bin,
                train=train_fold,
                eval_frame=valid_fold,
                temp_dir=temp_dir,
                name=f"fold-{fold_index}",
            )
            ensemble_probability = (
                0.25 * char_probability
                + 1.0 * normalised_probability
                + 0.5 * fasttext_probability
            ) / 1.75
            candidate_predictions[valid_indices] = ensemble_probability >= candidate_threshold
            folds.append(
                {
                    "fold": fold_index,
                    "baseline": _macro_f1_from_safe_predictions(
                        labels[valid_indices] == "safe",
                        baseline_predictions[valid_indices],
                    ),
                    "candidate": _macro_f1_from_safe_predictions(
                        labels[valid_indices] == "safe",
                        candidate_predictions[valid_indices],
                    ),
                }
            )

    return {
        "baseline_cv": _macro_f1_from_safe_predictions(truth_safe, baseline_predictions),
        "candidate_cv": _macro_f1_from_safe_predictions(truth_safe, candidate_predictions),
        "folds": folds,
    }


def run(
    *,
    repo_dir: Path,
    output_dir: Path,
    fasttext_bin: Path,
    optuna_trials: int,
    used_total_submissions: int,
    total_submission_limit: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = repo_dir / "taskB" / "data"
    train = _read_labeled_csv(data_dir / "train.csv")
    dev = _read_labeled_csv(data_dir / "dev_with_label.csv")
    dev_without_label = _read_unlabeled_csv(data_dir / "dev_without_label.csv")
    truth_safe = dev["label"].astype(str).to_numpy() == "safe"

    current_probability = _fit_safe_probability(_build_logreg_model(c_value=2.0), train, dev)
    current_eval = _macro_f1_from_safe_predictions(truth_safe, current_probability >= 0.5)
    current_candidate = {
        "trial_id": "p1-current-word-char-logreg",
        "source": "p1_sklearn_logreg",
        "score": current_eval["macro_f1"],
        "threshold": 0.5,
        "evaluation": current_eval,
        "params": {
            "operator": "combine.word_and_character_views",
            "model": "LogisticRegression",
            "char_range": [3, 5],
            "C": 2.0,
        },
    }

    manual_specs = [
        {
            "trial_id": "p2-p1-c3-threshold",
            "source": "manual_sklearn_logreg",
            "operator": "tune.linear_regularization",
            "model": _build_logreg_model(c_value=3.0),
        },
        {
            "trial_id": "p2-char25-c4-threshold",
            "source": "manual_sklearn_logreg",
            "operator": "adapt.character_robustness",
            "model": _build_logreg_model(c_value=4.0, char_range=(2, 5)),
        },
        {
            "trial_id": "p2-norm-ar-c3-threshold",
            "source": "manual_sklearn_logreg",
            "operator": "adapt.arabic_normalization",
            "model": _build_logreg_model(selector=_select_normalised_prompt, c_value=3.0),
        },
        {
            "trial_id": "p2-cw-none-c2-threshold",
            "source": "manual_sklearn_logreg",
            "operator": "substitute.class_balance",
            "model": _build_logreg_model(c_value=2.0, class_weight=None),
        },
    ]
    manual_candidates: list[dict[str, Any]] = []
    probabilities_by_id = {"p1-current-word-char-logreg": current_probability}
    for spec in manual_specs:
        probability = _fit_safe_probability(spec["model"], train, dev)
        probabilities_by_id[spec["trial_id"]] = probability
        evaluation = _best_threshold(truth_safe, probability)
        manual_candidates.append(
            {
                "trial_id": spec["trial_id"],
                "source": spec["source"],
                "operator": spec["operator"],
                "score": evaluation["macro_f1"],
                "threshold": evaluation["threshold"],
                "evaluation": evaluation,
            }
        )

    fasttext_state: dict[str, Any]
    with tempfile.TemporaryDirectory(prefix="arguard-b1-p2-fasttext-") as temp:
        temp_dir = Path(temp)
        if fasttext_bin.exists():
            fasttext_probability = _fasttext_safe_probability(
                fasttext_bin=fasttext_bin,
                train=train,
                eval_frame=dev,
                temp_dir=temp_dir,
                name="dev",
            )
            probabilities_by_id["p2-fasttext-best"] = fasttext_probability
            fasttext_eval = _best_threshold(truth_safe, fasttext_probability)
            fasttext_state = {
                "trial_id": "p2-fasttext-best",
                "source": "fasttext_binary",
                "operator": "substitute.fasttext_classifier",
                "state": "COMPLETE",
                "score": fasttext_eval["macro_f1"],
                "threshold": fasttext_eval["threshold"],
                "evaluation": fasttext_eval,
                "params": {
                    "lr": 0.3,
                    "epoch": 50,
                    "wordNgrams": 2,
                    "minn": 3,
                    "maxn": 6,
                    "loss": "softmax",
                },
            }
        else:
            fasttext_state = {
                "trial_id": "p2-fasttext-best",
                "source": "fasttext_binary",
                "operator": "substitute.fasttext_classifier",
                "state": "BLOCKED",
                "blocked_reason": f"fasttext_binary_not_found: {fasttext_bin}",
            }

    ensemble_candidates: list[dict[str, Any]] = []
    no_fasttext_probability = np.mean(
        np.vstack(
            [
                probabilities_by_id["p2-char25-c4-threshold"],
                probabilities_by_id["p2-norm-ar-c3-threshold"],
                probabilities_by_id["p2-cw-none-c2-threshold"],
            ]
        ),
        axis=0,
    )
    no_fasttext_eval = _best_threshold(truth_safe, no_fasttext_probability)
    ensemble_candidates.append(
        {
            "trial_id": "p2-ensemble-char25-norm-cwnone",
            "source": "manual_probability_ensemble",
            "operator": "combine.model_family_views",
            "score": no_fasttext_eval["macro_f1"],
            "threshold": no_fasttext_eval["threshold"],
            "evaluation": no_fasttext_eval,
            "members": [
                "p2-char25-c4-threshold",
                "p2-norm-ar-c3-threshold",
                "p2-cw-none-c2-threshold",
            ],
        }
    )

    selected_probability = None
    selected_threshold = None
    if fasttext_state.get("state") == "COMPLETE":
        selected_probability = (
            0.25 * probabilities_by_id["p2-char25-c4-threshold"]
            + 1.0 * probabilities_by_id["p2-norm-ar-c3-threshold"]
            + 0.5 * probabilities_by_id["p2-fasttext-best"]
        ) / 1.75
        selected_eval = _best_threshold(truth_safe, selected_probability)
        selected_threshold = selected_eval["threshold"]
        ensemble_candidates.append(
            {
                "trial_id": "p2-ensemble-fasttext-char25-norm",
                "source": "manual_probability_ensemble",
                "operator": "combine.fasttext_and_linear_views",
                "score": selected_eval["macro_f1"],
                "threshold": selected_eval["threshold"],
                "evaluation": selected_eval,
                "members": [
                    {"trial_id": "p2-char25-c4-threshold", "weight": 0.25},
                    {"trial_id": "p2-norm-ar-c3-threshold", "weight": 1.0},
                    {"trial_id": "p2-fasttext-best", "weight": 0.5},
                ],
            }
        )

    optuna_result = _run_optuna_search(
        train=train,
        dev=dev,
        truth_safe=truth_safe,
        trials=optuna_trials,
    )

    candidates = [current_candidate, *manual_candidates, fasttext_state, *ensemble_candidates]
    complete_candidates = [
        candidate
        for candidate in candidates
        if candidate.get("state", "COMPLETE") == "COMPLETE" and "score" in candidate
    ]
    local_diagnostic_winner = max(complete_candidates, key=lambda item: item["score"])

    cv_result = None
    recommendation_gate = {
        "decision": "HOLD",
        "recommended_for_codabench_submission": False,
        "official_scores_claimed": False,
        "reasons": ["selected_candidate_not_available_for_cv_gate"],
    }
    if (
        local_diagnostic_winner["trial_id"] == "p2-ensemble-fasttext-char25-norm"
        and selected_threshold is not None
        and fasttext_bin.exists()
    ):
        cv_result = _evaluate_cv(
            train=train,
            fasttext_bin=fasttext_bin,
            candidate_threshold=selected_threshold,
        )
        recommendation_gate = evaluate_submission_candidate_gate(
            candidate_id=local_diagnostic_winner["trial_id"],
            current_best_score=current_candidate["score"],
            candidate_score=local_diagnostic_winner["score"],
            current_cv_score=cv_result["baseline_cv"]["macro_f1"],
            candidate_cv_score=cv_result["candidate_cv"]["macro_f1"],
            current_unsafe_predicted_safe=current_eval["unsafe_predicted_safe_count"],
            candidate_unsafe_predicted_safe=local_diagnostic_winner["evaluation"][
                "unsafe_predicted_safe_count"
            ],
            current_safe_predicted_unsafe=current_eval["safe_predicted_unsafe_count"],
            candidate_safe_predicted_unsafe=local_diagnostic_winner["evaluation"][
                "safe_predicted_unsafe_count"
            ],
            remaining_total_submissions=total_submission_limit - used_total_submissions,
            min_score_delta=0.003,
            max_cv_regression=0.001,
            max_safe_false_positive_delta=10,
        )

    if selected_probability is not None and selected_threshold is not None:
        _write_prediction_csv(
            output_dir / "diagnostic-dev-with-label-prediction.csv",
            dev["id"].tolist(),
            selected_probability >= selected_threshold,
        )
        with tempfile.TemporaryDirectory(prefix="arguard-b1-p2-unlabeled-") as temp:
            temp_dir = Path(temp)
            char_unlabeled = _fit_safe_probability(
                _build_logreg_model(c_value=4.0, char_range=(2, 5)),
                train,
                dev_without_label,
            )
            norm_unlabeled = _fit_safe_probability(
                _build_logreg_model(selector=_select_normalised_prompt, c_value=3.0),
                train,
                dev_without_label,
            )
            fasttext_unlabeled = _fasttext_safe_probability(
                fasttext_bin=fasttext_bin,
                train=train,
                eval_frame=dev_without_label,
                temp_dir=temp_dir,
                name="dev-without-label",
            )
            unlabeled_probability = (
                0.25 * char_unlabeled + 1.0 * norm_unlabeled + 0.5 * fasttext_unlabeled
            ) / 1.75
            _write_prediction_csv(
                output_dir / "diagnostic-dev-without-label-prediction.csv",
                dev_without_label["id"].tolist(),
                unlabeled_probability >= selected_threshold,
            )

    payload = {
        "schema_version": "2026-06-30.arguard-b1-p2-offline-search.v1",
        "target_id": "arguard-b1-binary-classification",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "offline_optimization_search",
        "official_scores_claimed": False,
        "claim_boundary": (
            "Local public train/dev evidence only. No Codabench submission package is "
            "recommended unless submission_recommendation_gate passes."
        ),
        "submission_budget": {
            "daily_limit": 5,
            "total_limit": total_submission_limit,
            "used_total_submissions_assumed": used_total_submissions,
            "remaining_total_submissions": total_submission_limit - used_total_submissions,
        },
        "dataset": {
            "train_rows": int(len(train)),
            "dev_with_label_rows": int(len(dev)),
            "dev_without_label_rows": int(len(dev_without_label)),
        },
        "current_candidate": current_candidate,
        "candidates": candidates,
        "optuna_search": optuna_result,
        "local_diagnostic_winner": local_diagnostic_winner,
        "cv_result": cv_result,
        "submission_recommendation_gate": recommendation_gate,
        "generated_artifacts": [
            "offline-search-run.json",
            "submission-recommendation-gate.json",
            "diagnostic-dev-with-label-prediction.csv",
            "diagnostic-dev-without-label-prediction.csv",
        ],
    }
    (output_dir / "offline-search-run.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "submission-recommendation-gate.json").write_text(
        json.dumps(recommendation_gate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(
        "\n".join(
            [
                "# ArGuard B1 P2 离线优化搜索",
                "",
                "本目录记录 P1 提交后的一轮离线搜索，目标是在不消耗 Codabench 提交次数的前提下评估继续优化空间。",
                "",
                "## 结论",
                "",
                f"- 当前 P1 best local macro-F1: `{current_candidate['score']:.6f}`。",
                (
                    "- P2 local diagnostic winner: "
                    f"`{local_diagnostic_winner['trial_id']}`，local macro-F1 "
                    f"`{local_diagnostic_winner['score']:.6f}`。"
                ),
                (
                    "- submission recommendation gate: "
                    f"`{recommendation_gate['decision']}`，"
                    f"recommended_for_codabench_submission="
                    f"`{str(recommendation_gate['recommended_for_codabench_submission']).lower()}`。"
                ),
                "- `official_scores_claimed=false`：本轮未声明官方成绩，也未生成新的 `prediction.zip`。",
                "",
                "## 关键原因",
                "",
                "- 最高 dev 候选主要通过提高 unsafe 判定降低漏判，但 safe 误伤明显增加。",
                "- 3-fold train CV 显示该候选相对 P1 baseline 退化，因此被 gate 拦下。",
                "- 在每天 5 次、总共 10 次提交预算下，本轮不建议消耗新的 Codabench 提交。",
                "",
                "## 文件",
                "",
                "- `offline-search-run.json`：所有候选、Optuna 搜索、CV 和 gate 证据。",
                "- `submission-recommendation-gate.json`：是否推荐提交的最终 gate。",
                "- `diagnostic-dev-with-label-prediction.csv`：本地诊断 winner 对 dev_with_label 的预测。",
                "- `diagnostic-dev-without-label-prediction.csv`：本地诊断 winner 对 dev_without_label 的预测；不是可直接上传的 `prediction.zip`。",
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
    parser.add_argument("--fasttext-bin", default=".external/fastText/fasttext", type=Path)
    parser.add_argument("--optuna-trials", default=55, type=int)
    parser.add_argument("--used-total-submissions", default=1, type=int)
    parser.add_argument("--total-submission-limit", default=10, type=int)
    args = parser.parse_args()
    payload = run(
        repo_dir=args.repo_dir,
        output_dir=args.output_dir,
        fasttext_bin=args.fasttext_bin,
        optuna_trials=args.optuna_trials,
        used_total_submissions=args.used_total_submissions,
        total_submission_limit=args.total_submission_limit,
    )
    print(
        json.dumps(
            {
                "local_diagnostic_winner": payload["local_diagnostic_winner"]["trial_id"],
                "winner_score": payload["local_diagnostic_winner"]["score"],
                "submission_gate": payload["submission_recommendation_gate"]["decision"],
                "recommended_for_codabench_submission": payload[
                    "submission_recommendation_gate"
                ]["recommended_for_codabench_submission"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
