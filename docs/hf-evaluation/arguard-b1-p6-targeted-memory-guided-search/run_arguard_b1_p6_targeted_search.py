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
P5_FOCUS_ID = "p5-memory-guided-family-ensemble"


def _load_p5_runner_module():
    script = (
        Path(__file__).resolve().parents[0].parent
        / "arguard-b1-p5-expanded-exploration"
        / "run_arguard_b1_p5_expanded_exploration.py"
    )
    spec = importlib.util.spec_from_file_location("arguard_b1_p5_runner", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load P5 runner from {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P5 = _load_p5_runner_module()
P4 = P5.P4
P2 = P5.P2


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


def _probability_for_model(
    model: Any,
    train: pd.DataFrame,
    eval_frame: pd.DataFrame,
) -> np.ndarray:
    return P5._probability_for_model(model, train, eval_frame)


def _logreg_builder(
    *,
    c_value: float,
    char_range: tuple[int, int] = (3, 5),
    selector_name: str = "prompt",
    class_weight: str | None = "balanced",
) -> Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]:
    return P5._candidate_builder_for_logreg(
        c_value=c_value,
        char_range=char_range,
        selector_name=selector_name,
        class_weight=class_weight,
    )


def _member_builder_catalog() -> dict[str, Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]]:
    return {
        "base": _logreg_builder(c_value=2.0),
        "char25_c3p5": _logreg_builder(c_value=3.5, char_range=(2, 5)),
        "char25_c4": _logreg_builder(c_value=4.0, char_range=(2, 5)),
        "char25_c4p5": _logreg_builder(c_value=4.5, char_range=(2, 5)),
        "norm_c2p75": _logreg_builder(c_value=2.75, selector_name="norm_ar"),
        "norm_c3": _logreg_builder(c_value=3.0, selector_name="norm_ar"),
        "norm_c3p25": _logreg_builder(c_value=3.25, selector_name="norm_ar"),
        "cwnone_c1p8": _logreg_builder(c_value=1.8, class_weight=None),
        "cwnone_c2": _logreg_builder(c_value=2.0, class_weight=None),
        "cwnone_c2p2": _logreg_builder(c_value=2.2, class_weight=None),
    }


def _weighted_builder(
    weights: dict[str, float],
) -> Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]:
    catalog = _member_builder_catalog()

    def builder(train_frame: pd.DataFrame, eval_frame: pd.DataFrame) -> np.ndarray:
        parts = []
        part_weights = []
        for name, weight in weights.items():
            if not weight:
                continue
            parts.append(catalog[name](train_frame, eval_frame))
            part_weights.append(weight)
        return np.average(np.vstack(parts), axis=0, weights=np.asarray(part_weights))

    return builder


def _evaluate_weighted_spec(
    *,
    train: pd.DataFrame,
    dev: pd.DataFrame,
    truth_safe: np.ndarray,
    current_candidate: dict[str, Any],
    trial_id: str,
    source: str,
    operator: str,
    change_surface: str,
    label: str,
    weights: dict[str, float],
    safe_fp_budget_delta: int,
) -> dict[str, Any]:
    return P5._evaluate_spec(
        train=train,
        dev=dev,
        truth_safe=truth_safe,
        current_candidate=current_candidate,
        safe_fp_budget_delta=safe_fp_budget_delta,
        trial_id=trial_id,
        source=source,
        operator=operator,
        change_surface=change_surface,
        params={
            "label": label,
            "weights": weights,
            "safe_fp_budget_delta": safe_fp_budget_delta,
        },
        probability_builder=_weighted_builder(weights),
    )


def _select_best_by_direction(
    candidates: list[dict[str, Any]],
    current_candidate: dict[str, Any],
) -> dict[str, Any]:
    return P5._select_best_by_direction_score(candidates, current_candidate)


def _select_best_by_local_score(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if not candidates:
        raise ValueError("candidate list is empty")
    return max(candidates, key=lambda candidate: candidate["score"])


def _multi_seed_cv_for_candidate(
    *,
    train: pd.DataFrame,
    candidate_builder: Callable[[pd.DataFrame, pd.DataFrame], np.ndarray],
    threshold: float,
    seeds: list[int],
) -> dict[str, Any]:
    labels = train["label"].astype(str).to_numpy()
    truth_safe = labels == "safe"
    seed_results: list[dict[str, Any]] = []
    for seed in seeds:
        baseline_predictions = np.empty(len(train), dtype=bool)
        candidate_predictions = np.empty(len(train), dtype=bool)
        splitter = StratifiedKFold(n_splits=3, shuffle=True, random_state=seed)
        for train_indices, valid_indices in splitter.split(train, labels):
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
        baseline_eval = P2._macro_f1_from_safe_predictions(
            truth_safe,
            baseline_predictions,
        )
        candidate_eval = P2._macro_f1_from_safe_predictions(
            truth_safe,
            candidate_predictions,
        )
        seed_results.append(
            {
                "seed": seed,
                "baseline_macro_f1": baseline_eval["macro_f1"],
                "candidate_macro_f1": candidate_eval["macro_f1"],
                "delta": candidate_eval["macro_f1"] - baseline_eval["macro_f1"],
                "candidate_safe_predicted_unsafe": candidate_eval[
                    "safe_predicted_unsafe_count"
                ],
                "candidate_unsafe_predicted_safe": candidate_eval[
                    "unsafe_predicted_safe_count"
                ],
            }
        )
    deltas = [item["delta"] for item in seed_results]
    return {
        "seeds": seeds,
        "seed_results": seed_results,
        "mean_delta": float(np.mean(deltas)),
        "min_delta": float(np.min(deltas)),
        "max_delta": float(np.max(deltas)),
        "std_delta": float(np.std(deltas)),
        "all_seed_deltas_non_negative": all(delta >= 0 for delta in deltas),
    }


def _gate_and_strip_candidate(
    *,
    train: pd.DataFrame,
    candidate: dict[str, Any],
    current_candidate: dict[str, Any],
    remaining_total_submissions: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return P5._gate_and_strip_candidate(
        train=train,
        candidate=candidate,
        current_candidate=current_candidate,
        remaining_total_submissions=remaining_total_submissions,
    )


def _build_candidate_rounds(
    *,
    train: pd.DataFrame,
    dev: pd.DataFrame,
    current_candidate: dict[str, Any],
    remaining_total_submissions: int,
) -> list[dict[str, Any]]:
    truth_safe = dev["label"].astype(str).to_numpy() == "safe"
    p5_equal_weights = {
        "char25_c4": 1.0,
        "norm_c3": 1.0,
        "cwnone_c2": 1.0,
    }

    weight_specs = [
        ("equal", p5_equal_weights),
        ("char-heavy", {"char25_c4": 1.2, "norm_c3": 0.9, "cwnone_c2": 0.9}),
        ("norm-heavy", {"char25_c4": 0.85, "norm_c3": 1.3, "cwnone_c2": 0.85}),
        ("cwnone-heavy", {"char25_c4": 0.9, "norm_c3": 0.9, "cwnone_c2": 1.2}),
        ("base-anchored", {"base": 0.2, "char25_c4": 1.0, "norm_c3": 1.0, "cwnone_c2": 0.8}),
    ]
    weight_candidates = [
        _evaluate_weighted_spec(
            train=train,
            dev=dev,
            truth_safe=truth_safe,
            current_candidate=current_candidate,
            trial_id=f"p6-family-weight-frontier-{index:02d}",
            source="targeted_probability_ensemble",
            operator="combine.memory_guided_weight_frontier",
            change_surface="P5 memory-guided family ensemble weight frontier",
            label=label,
            weights=weights,
            safe_fp_budget_delta=15,
        )
        for index, (label, weights) in enumerate(weight_specs, start=1)
    ]
    weight_candidate = _select_best_by_direction(weight_candidates, current_candidate)
    weight_candidate["trial_id"] = "p6-family-weight-frontier"

    threshold_candidates = [
        _evaluate_weighted_spec(
            train=train,
            dev=dev,
            truth_safe=truth_safe,
            current_candidate=current_candidate,
            trial_id=f"p6-threshold-tightening-delta-{safe_delta}",
            source="targeted_threshold_grid",
            operator="refine.memory_guided_threshold_tightening",
            change_surface="P5 family ensemble threshold and safe false-positive budget",
            label=f"safe-fp-delta-{safe_delta}",
            weights=p5_equal_weights,
            safe_fp_budget_delta=safe_delta,
        )
        for safe_delta in (0, 1, 2, 5, 8, 10)
    ]
    threshold_candidate = _select_best_by_direction(
        threshold_candidates,
        current_candidate,
    )
    threshold_candidate["trial_id"] = "p6-threshold-tightening"

    member_specs = [
        ("char-c3p5", {"char25_c3p5": 1.0, "norm_c3": 1.0, "cwnone_c2": 1.0}),
        ("char-c4p5", {"char25_c4p5": 1.0, "norm_c3": 1.0, "cwnone_c2": 1.0}),
        ("norm-c2p75", {"char25_c4": 1.0, "norm_c2p75": 1.0, "cwnone_c2": 1.0}),
        ("norm-c3p25", {"char25_c4": 1.0, "norm_c3p25": 1.0, "cwnone_c2": 1.0}),
        ("cwnone-c1p8", {"char25_c4": 1.0, "norm_c3": 1.0, "cwnone_c1p8": 1.0}),
        ("cwnone-c2p2", {"char25_c4": 1.0, "norm_c3": 1.0, "cwnone_c2p2": 1.0}),
    ]
    member_candidates = [
        _evaluate_weighted_spec(
            train=train,
            dev=dev,
            truth_safe=truth_safe,
            current_candidate=current_candidate,
            trial_id=f"p6-member-regularization-frontier-{index:02d}",
            source="targeted_member_regularization",
            operator="tune.memory_guided_member_regularization",
            change_surface="P5 family ensemble member regularization frontier",
            label=label,
            weights=weights,
            safe_fp_budget_delta=15,
        )
        for index, (label, weights) in enumerate(member_specs, start=1)
    ]
    member_candidate = _select_best_by_direction(member_candidates, current_candidate)
    member_candidate["trial_id"] = "p6-member-regularization-frontier"

    cv_candidate = dict(weight_candidate)
    cv_candidate["trial_id"] = "p6-cv-stability-audit"
    cv_candidate["source"] = "targeted_cv_stability_audit"
    cv_candidate["operator"] = "audit.memory_guided_cv_stability"
    cv_candidate["change_surface"] = "P5 family ensemble multi-seed train CV stability"
    cv_seeds = [20260630, 20260701]
    cv_candidate["params"] = {
        **dict(cv_candidate.get("params", {})),
        "cv_seeds": cv_seeds,
        "audited_candidate": weight_candidate["trial_id"],
    }
    cv_candidate["cv_stability_result"] = _multi_seed_cv_for_candidate(
        train=train,
        candidate_builder=cv_candidate["probability_builder"],
        threshold=cv_candidate["threshold"],
        seeds=cv_seeds,
    )

    relaxed_specs = [
        ("pure-char25-c4-relaxed", {"char25_c4": 1.0}, 45),
        ("pure-norm-c3-relaxed", {"norm_c3": 1.0}, 45),
        ("char-heavy-relaxed-30", {"char25_c4": 1.6, "norm_c3": 0.8}, 30),
        ("char-heavy-relaxed-45", {"char25_c4": 1.8, "norm_c3": 0.7}, 45),
    ]
    relaxed_candidates = [
        _evaluate_weighted_spec(
            train=train,
            dev=dev,
            truth_safe=truth_safe,
            current_candidate=current_candidate,
            trial_id=f"p6-relaxed-risk-boundary-{index:02d}",
            source="targeted_relaxed_risk_audit",
            operator="audit.memory_guided_relaxed_risk_boundary",
            change_surface="P5 family ensemble relaxed safe false-positive risk boundary",
            label=label,
            weights=weights,
            safe_fp_budget_delta=safe_delta,
        )
        for index, (label, weights, safe_delta) in enumerate(relaxed_specs, start=1)
    ]
    relaxed_candidate = _select_best_by_local_score(relaxed_candidates)
    relaxed_candidate["trial_id"] = "p6-relaxed-risk-boundary"

    selected = [
        weight_candidate,
        threshold_candidate,
        member_candidate,
        cv_candidate,
        relaxed_candidate,
    ]
    rounds: list[dict[str, Any]] = []
    for round_number, candidate in enumerate(selected, start=1):
        candidate, gate_result = _gate_and_strip_candidate(
            train=train,
            candidate=candidate,
            current_candidate=current_candidate,
            remaining_total_submissions=remaining_total_submissions,
        )
        if candidate.get("cv_stability_result"):
            gate_result["cv_stability_result"] = candidate["cv_stability_result"]
        rounds.append(
            {
                "round_number": round_number,
                "proposal": candidate,
                "gate_result": gate_result,
            }
        )
    return rounds


def _proposal_from_candidate(candidate: dict[str, Any], official_result: dict[str, Any]) -> dict[str, Any]:
    evaluation = candidate["evaluation"]
    operator_id = candidate.get("operator_id") or candidate["operator"]
    return {
        "proposal_id": candidate.get("proposal_id") or candidate["trial_id"],
        "operator_id": operator_id,
        "why_this_operator_applies": (
            f"{operator_id} directly exploits the P5 near-pass direction "
            f"`{P5_FOCUS_ID}` after gate memory upweighted the model-family "
            "combination pattern."
        ),
        "hypothesis": (
            "A narrower search around the P5 no-fastText family ensemble may cross "
            "the local submission gate without reintroducing the P2 CV and safe "
            "false-positive regression."
        ),
        "change_surface": candidate["change_surface"],
        "expected_effect": (
            f"local macro-F1={candidate['score']:.6f}; "
            f"unsafe->safe={evaluation['unsafe_predicted_safe_count']}; "
            f"safe->unsafe={evaluation['safe_predicted_unsafe_count']}; "
            f"direction_score={candidate.get('direction_score', 0.0):.6f}"
        ),
        "risk": (
            "The candidate can still be a dev-threshold artifact; submit only if "
            "local delta, train CV, unsafe miss, and safe false-positive gates all pass."
        ),
        "cheapest_validation": (
            "Reuse public train/dev local macro-F1, 3-fold train CV, optional multi-seed "
            "CV audit, and scarce-submission gate."
        ),
        "rollback_or_stop_condition": (
            "Stop or downweight if local delta remains below gate, CV regresses, unsafe "
            "miss increases, or safe false positives exceed the allowed budget."
        ),
        "method": "arguard_b1_p6_targeted_memory_guided_search",
        "optimizer": candidate["source"],
        "adapter": "arguard-b1-p6-targeted-memory-guided-search",
        "target_scope": "public_train_dev_only",
        "params": candidate.get("params", {}),
        "official_scores_claimed": False,
    }


def build_method_search_inputs(p6_payload: dict[str, Any]) -> dict[str, Any]:
    official_result = p6_payload["official_result"]
    current_candidate = p6_payload["current_candidate"]
    candidate_rounds = p6_payload["candidate_rounds"]
    operators: list[str] = []
    round_proposals: list[dict[str, Any]] = []
    round_gate_results: list[dict[str, Any]] = []
    for round_item in candidate_rounds:
        candidate = dict(round_item["proposal"])
        gate_result = dict(round_item["gate_result"])
        operator_id = candidate.get("operator_id") or candidate["operator"]
        if operator_id not in operators:
            operators.append(operator_id)
        round_proposals.append(
            {"proposals": [_proposal_from_candidate(candidate, official_result)]}
        )
        round_gate_results.append({"gate_results": [gate_result]})

    return {
        "context": {
            "schema_version": "2026-07-01.arguard-b1-p6-targeted-context.v1",
            "target_id": TARGET_ID,
            "objective": (
                "Run five targeted MethodSearch rounds around the P5 memory-guided "
                "family ensemble near-pass and let gate decide whether it is ready "
                "for another Codabench review submission."
            ),
            "search_focus": P5_FOCUS_ID,
            "official_result": official_result,
            "current_candidate": {
                "trial_id": current_candidate["trial_id"],
                "score": current_candidate["score"],
                "evaluation": current_candidate["evaluation"],
            },
            "p5_best_direction": p6_payload.get("p5_best_direction"),
            "p5_memory_summary": p6_payload.get("p5_memory_summary"),
            "best_direction": p6_payload.get("best_direction"),
            "submission_budget": p6_payload.get("submission_budget", {}),
            "official_scores_claimed": False,
        },
        "operators": operators,
        "round_proposals": round_proposals,
        "round_gate_results": round_gate_results,
    }


def _pick_best_direction(candidate_rounds: list[dict[str, Any]]) -> dict[str, Any]:
    status_rank = {"passed": 2, "near_pass": 1, "blocked": 0}
    best_round = max(
        candidate_rounds,
        key=lambda item: (
            status_rank.get(item["gate_result"]["status"], 0),
            item["proposal"].get("direction_score", -999.0),
            item["proposal"]["score"],
        ),
    )
    candidate = best_round["proposal"]
    gate_result = best_round["gate_result"]
    return {
        "candidate_id": candidate["trial_id"],
        "operator_id": candidate["operator"],
        "source": candidate["source"],
        "local_macro_f1": candidate["score"],
        "direction_score": candidate.get("direction_score"),
        "gate_status": gate_result["status"],
        "hard_blockers": gate_result.get("hard_blockers", []),
        "submission_ready": gate_result["status"] == "passed",
        "reason": (
            "Gate-passing targeted candidate found."
            if gate_result["status"] == "passed"
            else "Best targeted direction remains exploratory because submission gate did not pass."
        ),
        "official_scores_claimed": False,
    }


def _p5_memory_summary(
    *,
    p5_payload: dict[str, Any] | None,
    p5_memory: dict[str, Any] | None,
) -> dict[str, Any]:
    latest_memory = {}
    if isinstance(p5_memory, dict) and isinstance(p5_memory.get("latest_memory"), dict):
        latest_memory = p5_memory["latest_memory"]
    return {
        "p5_best_direction": (
            p5_payload.get("best_direction")
            if isinstance(p5_payload, dict)
            else None
        ),
        "recommended_operator_shift": latest_memory.get("recommended_operator_shift"),
        "operator_weights": latest_memory.get("operator_weights"),
        "official_scores_claimed": False,
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
    weights = candidate.get("params", {}).get("weights")
    if not isinstance(weights, dict):
        return None
    probability = _weighted_builder(
        {str(name): float(weight) for name, weight in weights.items()}
    )(train, dev_without_label)
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


def _write_readme(path: Path, *, payload: dict[str, Any], trajectory: dict[str, Any]) -> None:
    best = payload["best_direction"]
    recommendation = payload["submission_recommendation"]
    lines = [
        "# ArGuard B1 P6 定向 memory-guided 搜索",
        "",
        "本目录接续 P5 的 near-pass 结论，只围绕 `p5-memory-guided-family-ensemble` 做 5 轮定向探索，目标是判断它是否能跨过提交 gate，而不是扩大到新的无关搜索空间。",
        "",
        "## 结论",
        "",
        f"- MethodSearch status: `{trajectory.get('status')}`。",
        f"- best direction: `{best['candidate_id']}` / `{best['operator_id']}`。",
        f"- best direction gate status: `{best['gate_status']}`。",
        f"- submission recommendation: `{recommendation['decision']}`。",
        f"- recommended_for_codabench_submission: `{str(recommendation['recommended_for_codabench_submission']).lower()}`。",
        "- `official_scores_claimed=false`：本轮没有上传新 submission，也没有声明新的官方提升。",
        "",
        "## 5 轮探索",
        "",
    ]
    for item in payload["candidate_rounds"]:
        candidate = item["proposal"]
        gate_result = item["gate_result"]
        lines.append(
            f"- round {item['round_number']}: `{candidate['trial_id']}` / "
            f"`{candidate['operator']}`，local macro-F1 "
            f"`{candidate['score']:.6f}`，gate `{gate_result['status']}`，"
            f"blockers `{gate_result.get('hard_blockers', [])}`。"
        )
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 所有 evidence 都来自公开 train/dev 的 local evidence 和 train CV。",
            "- P6 使用 P5 memory 作为方向选择依据，但不能自行宣称 official score 提升。",
            "- 只有 gate `passed` 才会生成 `candidate-prediction.zip` 进入人工提交复核。",
            "",
            "## 文件",
            "",
            "- `targeted-search-run.json`：候选、CV、gate、best direction 和提交建议。",
            "- `method-search-trajectory.json`：5 轮 MethodSearch/gate/tell/memory 轨迹。",
            "- `gate-feedback-memory-store.json`：gate 反馈后的 operator memory。",
            "- `submission-recommendation-gate.json`：是否建议进入人工提交复核。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run(
    *,
    repo_dir: Path,
    output_dir: Path,
    p5_run: Path | None,
    p5_memory: Path | None,
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
            "Browser-observed Codabench result. It can guide local exploration, "
            "but P6 does not claim a new official score."
        ),
        "official_scores_claimed": False,
    }
    submission_budget = {
        "daily_limit_observed": 5,
        "total_limit_observed": total_submission_limit,
        "used_total_submissions_observed": used_total_submissions,
        "remaining_total_submissions": total_submission_limit - used_total_submissions,
    }
    p5_payload = _load_optional_json(p5_run)
    p5_memory_payload = _load_optional_json(p5_memory)
    candidate_rounds = _build_candidate_rounds(
        train=train,
        dev=dev,
        current_candidate=current_candidate,
        remaining_total_submissions=submission_budget["remaining_total_submissions"],
    )
    best_direction = _pick_best_direction(candidate_rounds)
    payload = {
        "schema_version": "2026-07-01.arguard-b1-p6-targeted-search.v1",
        "target_id": TARGET_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "targeted_memory_guided_method_search",
        "search_focus": P5_FOCUS_ID,
        "official_result": official_result,
        "official_scores_claimed": False,
        "claim_boundary": (
            "Local public train/dev evidence only. P6 searches the P5 near-pass "
            "direction and does not upload or claim a new official score."
        ),
        "dataset": {
            "train_rows": int(len(train)),
            "dev_with_label_rows": int(len(dev)),
            "dev_without_label_rows": int(len(dev_without_label)),
        },
        "submission_budget": submission_budget,
        "current_candidate": current_candidate,
        "p5_best_direction": (
            p5_payload.get("best_direction")
            if isinstance(p5_payload, dict)
            else None
        ),
        "p5_memory_summary": _p5_memory_summary(
            p5_payload=p5_payload,
            p5_memory=p5_memory_payload,
        ),
        "candidate_rounds": candidate_rounds,
        "best_direction": best_direction,
    }
    inputs = build_method_search_inputs(payload)
    inputs_dir = output_dir / "inputs"
    _json_write(inputs_dir / "trajectory-context.json", inputs["context"])
    for index, proposals in enumerate(inputs["round_proposals"], start=1):
        _json_write(inputs_dir / f"round-{index:03d}-llm-proposals.json", proposals)
    for index, gates in enumerate(inputs["round_gate_results"], start=1):
        _json_write(inputs_dir / f"round-{index:03d}-gate-results.json", gates)

    trajectory = run_method_search_trajectory(
        trajectory_name="arguard-b1-p6-targeted-memory-guided-search",
        objective=inputs["context"]["objective"],
        context=inputs["context"],
        gate_results_by_round=inputs["round_gate_results"],
        round_count=5,
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
    passed_rounds = [
        item for item in candidate_rounds if item["gate_result"]["status"] == "passed"
    ]
    best_round = max(
        passed_rounds,
        key=lambda item: item["proposal"]["score"],
    ) if passed_rounds else None
    recommendation = {
        "decision": "READY_FOR_MANUAL_REVIEW" if best_round else "HOLD",
        "recommended_for_codabench_submission": best_round is not None,
        "candidate_id": best_round["proposal"]["trial_id"] if best_round else None,
        "reason": (
            "A targeted memory-guided candidate passed local/CV/safe gate."
            if best_round
            else "No targeted memory-guided candidate passed local/CV/safe gate; continue using best_direction for exploration only."
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
    _json_write(output_dir / "targeted-search-run.json", payload)
    _json_write(output_dir / "submission-recommendation-gate.json", recommendation)
    _write_readme(output_dir / "README.md", payload=payload, trajectory=trajectory)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-dir",
        default=".external/ArGuard-2026-tasks",
        type=Path,
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--p5-run",
        default="docs/hf-evaluation/arguard-b1-p5-expanded-exploration/expanded-exploration-run.json",
        type=Path,
    )
    parser.add_argument(
        "--p5-memory",
        default="docs/hf-evaluation/arguard-b1-p5-expanded-exploration/gate-feedback-memory-store.json",
        type=Path,
    )
    parser.add_argument("--official-submission-id", default="819950")
    parser.add_argument("--official-score", default=0.93, type=float)
    parser.add_argument("--visible-rank", default=3, type=int)
    parser.add_argument("--top-visible-score", default=0.94, type=float)
    parser.add_argument("--leaderboard-entry-count", default=6, type=int)
    parser.add_argument("--used-total-submissions", default=1, type=int)
    parser.add_argument("--total-submission-limit", default=10, type=int)
    args = parser.parse_args()
    payload = run(
        repo_dir=args.repo_dir,
        output_dir=args.output_dir,
        p5_run=args.p5_run,
        p5_memory=args.p5_memory,
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
                "best_direction": payload["best_direction"],
                "submission_recommendation": payload["submission_recommendation"],
                "official_score": payload["official_result"]["score"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
