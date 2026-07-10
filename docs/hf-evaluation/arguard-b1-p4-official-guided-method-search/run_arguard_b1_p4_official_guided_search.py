from __future__ import annotations

import argparse
import importlib.util
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from lib.benchmarks.arguard_b1_search_gate import evaluate_submission_candidate_gate
from lib.failure_driven_proposal import run_method_search_trajectory


REQUIRED_PROPOSAL_FIELDS = [
    "operator_id",
    "why_this_operator_applies",
    "hypothesis",
    "change_surface",
    "expected_effect",
    "risk",
    "cheapest_validation",
    "rollback_or_stop_condition",
]

TARGET_ID = "arguard-b1-binary-classification"
BASELINE_ID = "p1-current-word-char-logreg"


def _load_p2_runner_module():
    script = (
        Path(__file__).resolve().parents[0].parent
        / "arguard-b1-p2-offline-search"
        / "run_arguard_b1_p2_offline_search.py"
    )
    spec = importlib.util.spec_from_file_location("arguard_b1_p2_runner", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load P2 runner from {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P2 = _load_p2_runner_module()


def _json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_optional_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _best_threshold_with_safe_budget(
    truth_safe: np.ndarray,
    safe_probabilities: np.ndarray,
    *,
    max_safe_predicted_unsafe: int,
    start: float = 0.25,
    stop: float = 0.8,
    steps: int = 221,
) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    fallback: dict[str, Any] | None = None
    for threshold in np.linspace(start, stop, steps):
        evaluation = P2._macro_f1_from_safe_predictions(
            truth_safe,
            safe_probabilities >= threshold,
        )
        candidate = {**evaluation, "threshold": float(threshold)}
        if fallback is None or candidate["macro_f1"] > fallback["macro_f1"]:
            fallback = candidate
        if candidate["safe_predicted_unsafe_count"] > max_safe_predicted_unsafe:
            continue
        if best is None or candidate["macro_f1"] > best["macro_f1"]:
            best = candidate
    if best is not None:
        best["safe_budget_satisfied"] = True
        return best
    assert fallback is not None
    fallback["safe_budget_satisfied"] = False
    return fallback


def _probability_for_model(
    model: Any,
    train: pd.DataFrame,
    eval_frame: pd.DataFrame,
) -> np.ndarray:
    return P2._fit_safe_probability(model, train, eval_frame)


def _cv_score_for_candidate(
    *,
    train: pd.DataFrame,
    candidate_builder: Callable[[pd.DataFrame, pd.DataFrame], np.ndarray],
    threshold: float,
) -> dict[str, Any]:
    labels = train["label"].astype(str).to_numpy()
    truth_safe = labels == "safe"
    baseline_predictions = np.empty(len(train), dtype=bool)
    candidate_predictions = np.empty(len(train), dtype=bool)
    folds: list[dict[str, Any]] = []
    splitter = StratifiedKFold(n_splits=3, shuffle=True, random_state=20260630)
    for fold_index, (train_indices, valid_indices) in enumerate(
        splitter.split(train, labels),
        start=1,
    ):
        train_fold = train.iloc[train_indices].copy()
        valid_fold = train.iloc[valid_indices].copy()
        baseline_probability = _probability_for_model(
            P2._build_logreg_model(c_value=2.0),
            train_fold,
            valid_fold,
        )
        candidate_probability = candidate_builder(train_fold, valid_fold)
        baseline_predictions[valid_indices] = baseline_probability >= 0.5
        candidate_predictions[valid_indices] = candidate_probability >= threshold
        folds.append(
            {
                "fold": fold_index,
                "baseline": P2._macro_f1_from_safe_predictions(
                    labels[valid_indices] == "safe",
                    baseline_predictions[valid_indices],
                ),
                "candidate": P2._macro_f1_from_safe_predictions(
                    labels[valid_indices] == "safe",
                    candidate_predictions[valid_indices],
                ),
            }
        )
    return {
        "baseline_cv": P2._macro_f1_from_safe_predictions(truth_safe, baseline_predictions),
        "candidate_cv": P2._macro_f1_from_safe_predictions(truth_safe, candidate_predictions),
        "folds": folds,
    }


def _candidate_gate_result(
    *,
    candidate: dict[str, Any],
    current_candidate: dict[str, Any],
    cv_result: dict[str, Any],
    remaining_total_submissions: int,
) -> dict[str, Any]:
    current_eval = current_candidate["evaluation"]
    candidate_eval = candidate["evaluation"]
    gate = evaluate_submission_candidate_gate(
        candidate_id=candidate["trial_id"],
        current_best_score=current_candidate["score"],
        candidate_score=candidate["score"],
        current_cv_score=cv_result["baseline_cv"]["macro_f1"],
        candidate_cv_score=cv_result["candidate_cv"]["macro_f1"],
        current_unsafe_predicted_safe=current_eval["unsafe_predicted_safe_count"],
        candidate_unsafe_predicted_safe=candidate_eval["unsafe_predicted_safe_count"],
        current_safe_predicted_unsafe=current_eval["safe_predicted_unsafe_count"],
        candidate_safe_predicted_unsafe=candidate_eval["safe_predicted_unsafe_count"],
        remaining_total_submissions=remaining_total_submissions,
        min_score_delta=0.001,
        max_cv_regression=0.001,
        max_safe_false_positive_delta=10,
    )
    hard_blockers = list(gate["reasons"])
    if not candidate["evaluation"].get("safe_budget_satisfied", True):
        hard_blockers.append("safe_budget_not_satisfied")
    hard_blockers = sorted(set(hard_blockers), key=hard_blockers.index)
    return {
        "proposal_id": candidate["trial_id"],
        "operator_id": candidate["operator"],
        "status": "passed" if gate["recommended_for_codabench_submission"] else "blocked",
        "score": candidate["score"],
        "metric": "local_macro_f1",
        "hard_blockers": hard_blockers,
        "gate_reason": (
            "passes official-guided local submission gate"
            if gate["recommended_for_codabench_submission"]
            else "blocked by official-guided local submission gate"
        ),
        "evaluation": candidate["evaluation"],
        "cv_result": {
            "baseline_macro_f1": cv_result["baseline_cv"]["macro_f1"],
            "candidate_macro_f1": cv_result["candidate_cv"]["macro_f1"],
        },
        "submission_gate": gate,
        "official_scores_claimed": False,
    }


def _proposal_from_candidate(candidate: dict[str, Any], official_result: dict[str, Any]) -> dict[str, Any]:
    evaluation = candidate["evaluation"]
    proposal = {
        "proposal_id": candidate["trial_id"],
        "operator_id": candidate["operator"],
        "why_this_operator_applies": (
            f"{candidate['operator']} is anchored on the only official submitted "
            f"ArGuard B1 path ({official_result.get('submission_id')}, score "
            f"{official_result.get('score')}) and searches a low-variance surface."
        ),
        "hypothesis": (
            "A conservative change near the official-submitted P1 family may improve "
            "or preserve the rounded official score without repeating the P2 safe "
            "false-positive regression."
        ),
        "change_surface": candidate["change_surface"],
        "expected_effect": (
            f"local macro-F1={candidate['score']:.6f}; "
            f"unsafe->safe={evaluation['unsafe_predicted_safe_count']}; "
            f"safe->unsafe={evaluation['safe_predicted_unsafe_count']}"
        ),
        "risk": (
            "The public score is rounded to two decimals, so local deltas may not "
            "translate to an official-score change; threshold overfit remains possible."
        ),
        "cheapest_validation": (
            "Reuse public train/dev local macro-F1, 3-fold train CV, safe false-positive "
            "budget, and scarce-submission gate before any upload."
        ),
        "rollback_or_stop_condition": (
            "Stop if local delta is below 0.001, train CV regresses by more than 0.001, "
            "or safe false positives exceed the P1 budget by more than 10."
        ),
        "method": "arguard_b1_official_guided_local_search",
        "optimizer": candidate["source"],
        "adapter": "arguard-b1-p4-official-guided-method-search",
        "target_scope": "public_train_dev_only",
        "params": candidate.get("params", {}),
        "official_scores_claimed": False,
    }
    return proposal


def _round_record(
    *,
    round_number: int,
    candidate: dict[str, Any],
    gate_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "round_number": round_number,
        "proposal": candidate,
        "gate_result": gate_result,
    }


def _select_best(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if not candidates:
        raise ValueError("candidate list is empty")
    return max(candidates, key=lambda candidate: candidate["score"])


def _evaluate_spec(
    *,
    train: pd.DataFrame,
    dev: pd.DataFrame,
    truth_safe: np.ndarray,
    current_safe_fp_budget: int,
    trial_id: str,
    source: str,
    operator: str,
    change_surface: str,
    params: dict[str, Any],
    probability_builder: Callable[[pd.DataFrame, pd.DataFrame], np.ndarray],
) -> dict[str, Any]:
    probability = probability_builder(train, dev)
    evaluation = _best_threshold_with_safe_budget(
        truth_safe,
        probability,
        max_safe_predicted_unsafe=current_safe_fp_budget,
    )
    return {
        "trial_id": trial_id,
        "source": source,
        "operator": operator,
        "change_surface": change_surface,
        "score": evaluation["macro_f1"],
        "threshold": evaluation["threshold"],
        "evaluation": evaluation,
        "params": params,
        "probability_builder": probability_builder,
    }


def _build_candidate_rounds(
    *,
    train: pd.DataFrame,
    dev: pd.DataFrame,
    current_candidate: dict[str, Any],
    remaining_total_submissions: int,
) -> list[dict[str, Any]]:
    truth_safe = dev["label"].astype(str).to_numpy() == "safe"
    safe_fp_budget = current_candidate["evaluation"]["safe_predicted_unsafe_count"] + 10

    def baseline_builder(train_frame: pd.DataFrame, eval_frame: pd.DataFrame) -> np.ndarray:
        return _probability_for_model(
            P2._build_logreg_model(c_value=2.0),
            train_frame,
            eval_frame,
        )
    threshold_candidate = _evaluate_spec(
        train=train,
        dev=dev,
        truth_safe=truth_safe,
        current_safe_fp_budget=safe_fp_budget,
        trial_id="p4-threshold-safe-budget",
        source="official_guided_threshold_search",
        operator="refine.official_anchor_threshold",
        change_surface="P1 logistic regression decision threshold",
        params={"base_model": BASELINE_ID, "search": "safe_budget_threshold_grid"},
        probability_builder=baseline_builder,
    )

    regularization_specs = [
        ("p4-logreg-c1p5-char35", 1.5, (3, 5), "prompt", "balanced"),
        ("p4-logreg-c2p5-char35", 2.5, (3, 5), "prompt", "balanced"),
        ("p4-logreg-c3-char36", 3.0, (3, 6), "prompt", "balanced"),
        ("p4-logreg-c2-norm", 2.0, (3, 5), "norm_ar", "balanced"),
        ("p4-logreg-c2-cwnone", 2.0, (3, 5), "prompt", None),
    ]
    regularization_candidates: list[dict[str, Any]] = []
    for trial_id, c_value, char_range, selector_name, class_weight in regularization_specs:
        selector = P2._select_normalised_prompt if selector_name == "norm_ar" else P2._select_prompt

        def model_builder(
            train_frame: pd.DataFrame,
            eval_frame: pd.DataFrame,
            c_value: float = c_value,
            char_range: tuple[int, int] = char_range,
            selector: Callable[[pd.DataFrame], pd.Series] = selector,
            class_weight: str | None = class_weight,
        ) -> np.ndarray:
            return _probability_for_model(
                P2._build_logreg_model(
                    selector=selector,
                    c_value=c_value,
                    char_range=char_range,
                    class_weight=class_weight,
                ),
                train_frame,
                eval_frame,
            )

        regularization_candidates.append(
            _evaluate_spec(
                train=train,
                dev=dev,
                truth_safe=truth_safe,
                current_safe_fp_budget=safe_fp_budget,
                trial_id=trial_id,
                source="official_guided_logreg_search",
                operator="tune.official_anchor_regularization",
                change_surface="P1-family logistic regression regularization and features",
                params={
                    "C": c_value,
                    "char_range": list(char_range),
                    "selector": selector_name,
                    "class_weight": class_weight,
                },
                probability_builder=model_builder,
            )
        )
    regularization_candidate = _select_best(regularization_candidates)
    regularization_candidate["trial_id"] = "p4-regularization-safe-budget"

    def norm_builder(train_frame: pd.DataFrame, eval_frame: pd.DataFrame) -> np.ndarray:
        return _probability_for_model(
            P2._build_logreg_model(selector=P2._select_normalised_prompt, c_value=2.0),
            train_frame,
            eval_frame,
        )

    def c25_builder(train_frame: pd.DataFrame, eval_frame: pd.DataFrame) -> np.ndarray:
        return _probability_for_model(
            P2._build_logreg_model(c_value=2.5, char_range=(3, 5)),
            train_frame,
            eval_frame,
        )

    def blend_builder(
        train_frame: pd.DataFrame,
        eval_frame: pd.DataFrame,
        *,
        base_weight: float,
        norm_weight: float,
        c25_weight: float,
    ) -> np.ndarray:
        parts = []
        weights = []
        if base_weight:
            parts.append(baseline_builder(train_frame, eval_frame))
            weights.append(base_weight)
        if norm_weight:
            parts.append(norm_builder(train_frame, eval_frame))
            weights.append(norm_weight)
        if c25_weight:
            parts.append(c25_builder(train_frame, eval_frame))
            weights.append(c25_weight)
        return np.average(np.vstack(parts), axis=0, weights=np.asarray(weights))

    ensemble_specs = [
        ("p4-ensemble-p1-norm-3to1", 0.75, 0.25, 0.0),
        ("p4-ensemble-p1-c25-3to1", 0.75, 0.0, 0.25),
        ("p4-ensemble-p1-norm-c25-2to1to1", 0.5, 0.25, 0.25),
    ]
    ensemble_candidates: list[dict[str, Any]] = []
    for trial_id, base_weight, norm_weight, c25_weight in ensemble_specs:
        def builder(
            train_frame: pd.DataFrame,
            eval_frame: pd.DataFrame,
            base_weight: float = base_weight,
            norm_weight: float = norm_weight,
            c25_weight: float = c25_weight,
        ) -> np.ndarray:
            return blend_builder(
                train_frame,
                eval_frame,
                base_weight=base_weight,
                norm_weight=norm_weight,
                c25_weight=c25_weight,
            )

        ensemble_candidates.append(
            _evaluate_spec(
                train=train,
                dev=dev,
                truth_safe=truth_safe,
                current_safe_fp_budget=safe_fp_budget,
                trial_id=trial_id,
                source="official_guided_conservative_ensemble",
                operator="combine.conservative_model_family_views",
                change_surface="conservative P1-family probability ensemble",
                params={
                    "base_weight": base_weight,
                    "norm_weight": norm_weight,
                    "c25_weight": c25_weight,
                },
                probability_builder=builder,
            )
        )
    ensemble_candidate = _select_best(ensemble_candidates)
    ensemble_candidate["trial_id"] = "p4-conservative-ensemble"

    selected = [threshold_candidate, regularization_candidate, ensemble_candidate]
    rounds: list[dict[str, Any]] = []
    for round_number, candidate in enumerate(selected, start=1):
        cv_result = _cv_score_for_candidate(
            train=train,
            candidate_builder=candidate["probability_builder"],
            threshold=candidate["threshold"],
        )
        candidate = {
            key: value
            for key, value in candidate.items()
            if key != "probability_builder"
        }
        gate_result = _candidate_gate_result(
            candidate=candidate,
            current_candidate=current_candidate,
            cv_result=cv_result,
            remaining_total_submissions=remaining_total_submissions,
        )
        rounds.append(
            _round_record(
                round_number=round_number,
                candidate=candidate,
                gate_result=gate_result,
            )
        )
    return rounds


def build_method_search_inputs(p4_payload: dict[str, Any]) -> dict[str, Any]:
    official_result = p4_payload["official_result"]
    current_candidate = p4_payload["current_candidate"]
    candidate_rounds = p4_payload["candidate_rounds"]
    operators: list[str] = []
    round_proposals: list[dict[str, Any]] = []
    round_gate_results: list[dict[str, Any]] = []
    for round_item in candidate_rounds:
        candidate = dict(round_item["proposal"])
        gate_result = dict(round_item["gate_result"])
        proposal_id = candidate.get("proposal_id") or candidate["trial_id"]
        operator_id = candidate.get("operator_id") or candidate["operator"]
        if operator_id not in operators:
            operators.append(operator_id)
        proposal = _proposal_from_candidate(
            {
                "trial_id": proposal_id,
                "operator": operator_id,
                "source": candidate.get("source", "official_guided_search"),
                "change_surface": candidate.get(
                    "change_surface",
                    "official-guided ArGuard B1 local candidate",
                ),
                "score": candidate["score"],
                "evaluation": candidate["evaluation"],
                "params": candidate.get("params", {}),
            },
            official_result,
        )
        round_proposals.append({"proposals": [proposal]})
        round_gate_results.append({"gate_results": [gate_result]})

    return {
        "context": {
            "schema_version": "2026-06-30.arguard-b1-p4-official-guided-context.v1",
            "target_id": TARGET_ID,
            "objective": (
                "Use official score 0.93 as outcome evidence and continue ArGuard B1 "
                "optimization through MethodSearch/gate, without manual promotion."
            ),
            "official_result": official_result,
            "current_candidate": {
                "trial_id": current_candidate["trial_id"],
                "score": current_candidate["score"],
                "evaluation": current_candidate["evaluation"],
            },
            "submission_budget": p4_payload.get("submission_budget", {}),
            "prior_memory": p4_payload.get("prior_memory"),
            "official_scores_claimed": False,
        },
        "operators": operators,
        "round_proposals": round_proposals,
        "round_gate_results": round_gate_results,
    }


def _write_prediction_zip(
    *,
    output_dir: Path,
    train: pd.DataFrame,
    dev_without_label: pd.DataFrame,
    candidate_round: dict[str, Any],
) -> str | None:
    gate_result = candidate_round["gate_result"]
    if gate_result["status"] != "passed":
        return None
    candidate = candidate_round["proposal"]
    params = candidate.get("params", {})
    if candidate["operator"] == "refine.official_anchor_threshold":
        probability = _probability_for_model(
            P2._build_logreg_model(c_value=2.0),
            train,
            dev_without_label,
        )
    elif candidate["operator"] == "tune.official_anchor_regularization":
        selector = (
            P2._select_normalised_prompt
            if params.get("selector") == "norm_ar"
            else P2._select_prompt
        )
        probability = _probability_for_model(
            P2._build_logreg_model(
                selector=selector,
                c_value=float(params.get("C", 2.0)),
                char_range=tuple(params.get("char_range", [3, 5])),
                class_weight=params.get("class_weight"),
            ),
            train,
            dev_without_label,
        )
    else:
        base_probability = _probability_for_model(
            P2._build_logreg_model(c_value=2.0),
            train,
            dev_without_label,
        )
        norm_probability = _probability_for_model(
            P2._build_logreg_model(selector=P2._select_normalised_prompt, c_value=2.0),
            train,
            dev_without_label,
        )
        c25_probability = _probability_for_model(
            P2._build_logreg_model(c_value=2.5, char_range=(3, 5)),
            train,
            dev_without_label,
        )
        weights = np.asarray(
            [
                float(params.get("base_weight", 0.5)),
                float(params.get("norm_weight", 0.25)),
                float(params.get("c25_weight", 0.25)),
            ]
        )
        probability = np.average(
            np.vstack([base_probability, norm_probability, c25_probability]),
            axis=0,
            weights=weights,
        )
    prediction_csv = output_dir / "candidate-prediction.csv"
    P2._write_prediction_csv(
        prediction_csv,
        dev_without_label["id"].tolist(),
        probability >= float(candidate["threshold"]),
    )
    prediction_zip = output_dir / "candidate-prediction.zip"
    with zipfile.ZipFile(prediction_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(prediction_csv, arcname="prediction.csv")
    return "candidate-prediction.zip"


def run(
    *,
    repo_dir: Path,
    output_dir: Path,
    p3_memory: Path | None,
    official_submission_id: str,
    official_score: float,
    visible_rank: int,
    top_visible_score: float,
    leaderboard_entry_count: int,
    used_total_submissions: int,
    total_submission_limit: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = repo_dir / "taskB" / "data"
    train = P2._read_labeled_csv(data_dir / "train.csv")
    dev = P2._read_labeled_csv(data_dir / "dev_with_label.csv")
    dev_without_label = P2._read_unlabeled_csv(data_dir / "dev_without_label.csv")
    truth_safe = dev["label"].astype(str).to_numpy() == "safe"

    current_probability = _probability_for_model(
        P2._build_logreg_model(c_value=2.0),
        train,
        dev,
    )
    current_eval = P2._macro_f1_from_safe_predictions(
        truth_safe,
        current_probability >= 0.5,
    )
    current_candidate = {
        "trial_id": BASELINE_ID,
        "source": "p1_official_submitted_sklearn_logreg",
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
    official_result = {
        "source": "codabench_logged_in_browser_observation",
        "competition_url": "https://www.codabench.org/competitions/16652/#/participate-tab",
        "submission_id": official_submission_id,
        "file_name": "prediction.zip",
        "status": "Finished",
        "score": float(official_score),
        "visible_rank": int(visible_rank),
        "leaderboard_entry_count": int(leaderboard_entry_count),
        "top_visible_score": float(top_visible_score),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": (
            "Browser-observed Codabench result evidence. It can guide local optimizer/gate "
            "search, but a new official-score claim still requires explicit review."
        ),
        "official_scores_claimed": False,
    }
    prior_memory = _load_optional_json(p3_memory)
    submission_budget = {
        "daily_limit_observed": 5,
        "total_limit_observed": total_submission_limit,
        "used_total_submissions_observed": used_total_submissions,
        "remaining_total_submissions": total_submission_limit - used_total_submissions,
    }
    candidate_rounds = _build_candidate_rounds(
        train=train,
        dev=dev,
        current_candidate=current_candidate,
        remaining_total_submissions=submission_budget["remaining_total_submissions"],
    )
    payload = {
        "schema_version": "2026-06-30.arguard-b1-p4-official-guided-search.v1",
        "target_id": TARGET_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "official_guided_method_search",
        "official_result": official_result,
        "official_scores_claimed": False,
        "claim_boundary": (
            "Uses an official returned Codabench score as outcome evidence for local "
            "search direction. It does not upload another submission or claim a new score."
        ),
        "dataset": {
            "train_rows": int(len(train)),
            "dev_with_label_rows": int(len(dev)),
            "dev_without_label_rows": int(len(dev_without_label)),
        },
        "submission_budget": submission_budget,
        "current_candidate": current_candidate,
        "prior_memory": prior_memory,
        "candidate_rounds": candidate_rounds,
    }
    inputs = build_method_search_inputs(payload)
    inputs_dir = output_dir / "inputs"
    _json_write(output_dir / "official-result-observation.json", official_result)
    _json_write(inputs_dir / "trajectory-context.json", inputs["context"])
    for index, proposals in enumerate(inputs["round_proposals"], start=1):
        _json_write(inputs_dir / f"round-{index:03d}-llm-proposals.json", proposals)
    for index, gates in enumerate(inputs["round_gate_results"], start=1):
        _json_write(inputs_dir / f"round-{index:03d}-gate-results.json", gates)

    trajectory = run_method_search_trajectory(
        trajectory_name="arguard-b1-p4-official-guided-method-search",
        objective=inputs["context"]["objective"],
        context=inputs["context"],
        gate_results_by_round=inputs["round_gate_results"],
        round_count=3,
        mode="optimization-run",
        optimizer_sources=["llm"],
        operators=inputs["operators"],
        llm_proposals_by_round=inputs["round_proposals"],
        execute_llm=False,
        execute_optimizer_runtimes=False,
        allow_style_fallback=True,
        output_dir=output_dir / "run",
        feedback_store_path=output_dir / "gate-feedback-memory-store.json",
        output_path=output_dir / "method-search-trajectory.json",
        overwrite=True,
    )
    best_round = None
    passed_rounds = [
        item for item in candidate_rounds if item["gate_result"]["status"] == "passed"
    ]
    if passed_rounds:
        best_round = max(passed_rounds, key=lambda item: item["proposal"]["score"])
    recommendation = {
        "decision": "READY_FOR_MANUAL_REVIEW" if best_round else "HOLD",
        "recommended_for_codabench_submission": best_round is not None,
        "candidate_id": best_round["proposal"]["trial_id"] if best_round else None,
        "reason": (
            "At least one official-guided P1-family candidate passed local/CV/safe gate."
            if best_round
            else "No official-guided candidate passed local/CV/safe gate."
        ),
        "official_scores_claimed": False,
    }
    generated_prediction_zip = None
    if best_round is not None:
        generated_prediction_zip = _write_prediction_zip(
            output_dir=output_dir,
            train=train,
            dev_without_label=dev_without_label,
            candidate_round=best_round,
        )
        recommendation["candidate_prediction_zip"] = generated_prediction_zip
    payload["method_search_trajectory_ref"] = "method-search-trajectory.json"
    payload["submission_recommendation"] = recommendation
    payload["generated_prediction_zip"] = generated_prediction_zip
    _json_write(output_dir / "official-guided-search-run.json", payload)
    _json_write(output_dir / "submission-recommendation-gate.json", recommendation)
    _write_readme(output_dir / "README.md", payload=payload, trajectory=trajectory)
    return payload


def _write_readme(path: Path, *, payload: dict[str, Any], trajectory: dict[str, Any]) -> None:
    recommendation = payload["submission_recommendation"]
    official = payload["official_result"]
    lines = [
        "# ArGuard B1 P4 官方结果引导 MethodSearch",
        "",
        "本目录把 Codabench 已返回的 P1 官方结果作为 outcome evidence，继续通过 ml-research-loop 自身的 MethodSearch/gate/memory 路径做下一轮低风险搜索。",
        "",
        "## 结论",
        "",
        f"- official submission: `{official['submission_id']}`。",
        f"- official score: `{official['score']}`，visible rank: `{official['visible_rank']}` / `{official['leaderboard_entry_count']}`。",
        f"- MethodSearch status: `{trajectory.get('status')}`。",
        f"- submission recommendation: `{recommendation['decision']}`。",
        f"- recommended_for_codabench_submission: `{str(recommendation['recommended_for_codabench_submission']).lower()}`。",
        "- `official_scores_claimed=false`：本轮不上传新 submission，不声明新官方提升。",
        "",
        "## 边界",
        "",
        "- P4 使用公开 train/dev 重训和评估 P1-family 低风险候选。",
        "- gate 同时检查 local macro-F1、3-fold train CV、safe 误伤预算和剩余提交预算。",
        "- 若生成 `candidate-prediction.zip`，它也只是待人工复核的候选包，不会自动上传。",
        "",
        "## 文件",
        "",
        "- `official-result-observation.json`：登录态 Codabench 页面观察到的官方结果。",
        "- `official-guided-search-run.json`：P4 候选、CV、gate 和提交建议。",
        "- `method-search-trajectory.json`：MethodSearch/gate/tell/memory 轨迹。",
        "- `gate-feedback-memory-store.json`：gate 反馈记忆。",
        "- `submission-recommendation-gate.json`：是否建议人工复核下一次提交。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-dir",
        default=".external/ArGuard-2026-tasks",
        type=Path,
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--p3-memory",
        default="docs/hf-evaluation/arguard-b1-p3-method-search-trajectory/gate-feedback-memory-store.json",
        type=Path,
    )
    parser.add_argument("--official-submission-id", default="819950")
    parser.add_argument("--official-score", default=0.93, type=float)
    parser.add_argument("--visible-rank", default=3, type=int)
    parser.add_argument("--top-visible-score", default=0.94, type=float)
    parser.add_argument("--leaderboard-entry-count", default=6, type=int)
    parser.add_argument("--used-total-submissions", default=1, type=int)
    parser.add_argument("--total-submission-limit", default=100, type=int)
    args = parser.parse_args()
    payload = run(
        repo_dir=args.repo_dir,
        output_dir=args.output_dir,
        p3_memory=args.p3_memory,
        official_submission_id=args.official_submission_id,
        official_score=args.official_score,
        visible_rank=args.visible_rank,
        top_visible_score=args.top_visible_score,
        leaderboard_entry_count=args.leaderboard_entry_count,
        used_total_submissions=args.used_total_submissions,
        total_submission_limit=args.total_submission_limit,
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "submission_recommendation": payload["submission_recommendation"],
                "official_score": payload["official_result"]["score"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
