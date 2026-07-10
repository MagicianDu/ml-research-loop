from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

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


def _load_p4_runner_module():
    script = (
        Path(__file__).resolve().parents[0].parent
        / "arguard-b1-p4-official-guided-method-search"
        / "run_arguard_b1_p4_official_guided_search.py"
    )
    spec = importlib.util.spec_from_file_location("arguard_b1_p4_runner", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load P4 runner from {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P4 = _load_p4_runner_module()
P2 = P4.P2


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
    return P4._probability_for_model(model, train, eval_frame)


def _candidate_builder_for_logreg(
    *,
    c_value: float,
    char_range: tuple[int, int] = (3, 5),
    selector_name: str = "prompt",
    class_weight: str | None = "balanced",
) -> Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]:
    selector = P2._select_normalised_prompt if selector_name == "norm_ar" else P2._select_prompt

    def builder(train_frame: pd.DataFrame, eval_frame: pd.DataFrame) -> np.ndarray:
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

    return builder


def _evaluate_spec(
    *,
    train: pd.DataFrame,
    dev: pd.DataFrame,
    truth_safe: np.ndarray,
    current_candidate: dict[str, Any],
    safe_fp_budget_delta: int,
    trial_id: str,
    source: str,
    operator: str,
    change_surface: str,
    params: dict[str, Any],
    probability_builder: Callable[[pd.DataFrame, pd.DataFrame], np.ndarray],
) -> dict[str, Any]:
    probability = probability_builder(train, dev)
    evaluation = P4._best_threshold_with_safe_budget(
        truth_safe,
        probability,
        max_safe_predicted_unsafe=(
            current_candidate["evaluation"]["safe_predicted_unsafe_count"]
            + safe_fp_budget_delta
        ),
    )
    candidate = {
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
    return candidate


def _direction_score(
    *,
    candidate: dict[str, Any],
    current_candidate: dict[str, Any],
    cv_result: dict[str, Any] | None = None,
) -> float:
    candidate_eval = candidate["evaluation"]
    current_eval = current_candidate["evaluation"]
    local_delta = candidate["score"] - current_candidate["score"]
    unsafe_miss_delta = (
        candidate_eval["unsafe_predicted_safe_count"]
        - current_eval["unsafe_predicted_safe_count"]
    )
    safe_fp_delta = (
        candidate_eval["safe_predicted_unsafe_count"]
        - current_eval["safe_predicted_unsafe_count"]
    )
    cv_delta = 0.0
    if cv_result is not None:
        cv_delta = (
            cv_result["candidate_cv"]["macro_f1"]
            - cv_result["baseline_cv"]["macro_f1"]
        )
    return float(
        local_delta
        + 0.50 * cv_delta
        - 0.00012 * max(0, safe_fp_delta)
        - 0.00025 * max(0, unsafe_miss_delta)
    )


def _select_best_by_direction_score(
    candidates: list[dict[str, Any]],
    current_candidate: dict[str, Any],
) -> dict[str, Any]:
    if not candidates:
        raise ValueError("candidate list is empty")
    for candidate in candidates:
        candidate["direction_score"] = _direction_score(
            candidate=candidate,
            current_candidate=current_candidate,
        )
    return max(
        candidates,
        key=lambda candidate: (candidate["direction_score"], candidate["score"]),
    )


def _gate_and_strip_candidate(
    *,
    train: pd.DataFrame,
    candidate: dict[str, Any],
    current_candidate: dict[str, Any],
    remaining_total_submissions: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cv_result = P4._cv_score_for_candidate(
        train=train,
        candidate_builder=candidate["probability_builder"],
        threshold=candidate["threshold"],
    )
    candidate["direction_score"] = _direction_score(
        candidate=candidate,
        current_candidate=current_candidate,
        cv_result=cv_result,
    )
    stripped_candidate = {
        key: value
        for key, value in candidate.items()
        if key != "probability_builder"
    }
    gate_result = P4._candidate_gate_result(
        candidate=stripped_candidate,
        current_candidate=current_candidate,
        cv_result=cv_result,
        remaining_total_submissions=remaining_total_submissions,
    )
    gate_result["direction_score"] = stripped_candidate["direction_score"]
    submission_reasons = gate_result["submission_gate"].get("reasons", [])
    near_pass_only_short_delta = (
        gate_result["status"] == "blocked"
        and submission_reasons == ["insufficient_local_score_delta"]
        and gate_result["submission_gate"]["score_delta"] > 0
    )
    if near_pass_only_short_delta:
        gate_result["status"] = "near_pass"
        gate_result["hard_blockers"] = []
        gate_result["submission_blockers"] = submission_reasons
        gate_result["gate_reason"] = (
            "near-pass direction, but local delta is below submission gate"
        )
    elif gate_result["status"] == "blocked" and not gate_result["hard_blockers"]:
        gate_result["status"] = "near_pass"
        gate_result["gate_reason"] = "near-pass direction, but not submission-ready"
    return stripped_candidate, gate_result


def _build_candidate_rounds(
    *,
    train: pd.DataFrame,
    dev: pd.DataFrame,
    current_candidate: dict[str, Any],
    remaining_total_submissions: int,
) -> list[dict[str, Any]]:
    truth_safe = dev["label"].astype(str).to_numpy() == "safe"

    regularization_specs = [
        (2.25, (3, 5), "prompt", "balanced"),
        (2.50, (3, 5), "prompt", "balanced"),
        (2.75, (3, 5), "prompt", "balanced"),
        (2.50, (3, 6), "prompt", "balanced"),
        (1.75, (3, 5), "prompt", "balanced"),
        (2.00, (3, 5), "prompt", None),
    ]
    regularization_candidates: list[dict[str, Any]] = []
    for index, (c_value, char_range, selector_name, class_weight) in enumerate(
        regularization_specs,
        start=1,
    ):
        regularization_candidates.append(
            _evaluate_spec(
                train=train,
                dev=dev,
                truth_safe=truth_safe,
                current_candidate=current_candidate,
                safe_fp_budget_delta=10,
                trial_id=f"p5-cv-stable-regularization-{index:02d}",
                source="expanded_logreg_grid",
                operator="tune.cv_stable_regularization",
                change_surface="P1-family regularization and char n-gram grid",
                params={
                    "C": c_value,
                    "char_range": list(char_range),
                    "selector": selector_name,
                    "class_weight": class_weight,
                    "safe_fp_budget_delta": 10,
                },
                probability_builder=_candidate_builder_for_logreg(
                    c_value=c_value,
                    char_range=char_range,
                    selector_name=selector_name,
                    class_weight=class_weight,
                ),
            )
        )
    regularization_candidate = _select_best_by_direction_score(
        regularization_candidates,
        current_candidate,
    )
    regularization_candidate["trial_id"] = "p5-cv-stable-regularization"

    threshold_candidates: list[dict[str, Any]] = []
    baseline_builder = _candidate_builder_for_logreg(c_value=2.0)
    for safe_fp_budget_delta in (10, 15, 20, 30):
        threshold_candidates.append(
            _evaluate_spec(
                train=train,
                dev=dev,
                truth_safe=truth_safe,
                current_candidate=current_candidate,
                safe_fp_budget_delta=safe_fp_budget_delta,
                trial_id=f"p5-safe-recall-frontier-delta-{safe_fp_budget_delta}",
                source="expanded_threshold_grid",
                operator="refine.safe_recall_frontier",
                change_surface="decision threshold under explicit safe false-positive budgets",
                params={
                    "base_model": BASELINE_ID,
                    "safe_fp_budget_delta": safe_fp_budget_delta,
                },
                probability_builder=baseline_builder,
            )
        )
    threshold_candidate = _select_best_by_direction_score(
        threshold_candidates,
        current_candidate,
    )
    threshold_candidate["trial_id"] = "p5-safe-recall-frontier"

    normalization_specs = [
        (2.0, (3, 5)),
        (2.5, (3, 5)),
        (3.0, (3, 5)),
        (2.5, (3, 6)),
        (2.0, (2, 5)),
    ]
    normalization_candidates: list[dict[str, Any]] = []
    for index, (c_value, char_range) in enumerate(normalization_specs, start=1):
        normalization_candidates.append(
            _evaluate_spec(
                train=train,
                dev=dev,
                truth_safe=truth_safe,
                current_candidate=current_candidate,
                safe_fp_budget_delta=12,
                trial_id=f"p5-arabic-normalization-surface-{index:02d}",
                source="expanded_normalization_grid",
                operator="adapt.arabic_normalization_surface",
                change_surface="Arabic normalization selector with local threshold search",
                params={
                    "C": c_value,
                    "char_range": list(char_range),
                    "selector": "norm_ar",
                    "class_weight": "balanced",
                    "safe_fp_budget_delta": 12,
                },
                probability_builder=_candidate_builder_for_logreg(
                    c_value=c_value,
                    char_range=char_range,
                    selector_name="norm_ar",
                ),
            )
        )
    normalization_candidate = _select_best_by_direction_score(
        normalization_candidates,
        current_candidate,
    )
    normalization_candidate["trial_id"] = "p5-arabic-normalization-surface"

    norm_builder = _candidate_builder_for_logreg(c_value=2.0, selector_name="norm_ar")
    norm_c3_builder = _candidate_builder_for_logreg(c_value=3.0, selector_name="norm_ar")
    c25_builder = _candidate_builder_for_logreg(c_value=2.5, char_range=(3, 5))
    char25_c4_builder = _candidate_builder_for_logreg(c_value=4.0, char_range=(2, 5))
    cwnone_builder = _candidate_builder_for_logreg(c_value=2.0, class_weight=None)

    ensemble_specs: list[dict[str, Any]] = [
        {
            "label": "p2-memory-no-fasttext-equal",
            "weights": {
                "char25_c4": 1.0,
                "norm_c3": 1.0,
                "cwnone": 1.0,
            },
        },
        {
            "label": "p2-memory-no-fasttext-norm-heavy",
            "weights": {
                "char25_c4": 0.8,
                "norm_c3": 1.2,
                "cwnone": 1.0,
            },
        },
        {
            "label": "conservative-base-norm-c25",
            "weights": {
                "base": 0.50,
                "norm": 0.25,
                "c25": 0.25,
            },
        },
        {
            "label": "conservative-base-norm-c25-cwnone",
            "weights": {
                "base": 0.40,
                "norm": 0.20,
                "c25": 0.20,
                "cwnone": 0.20,
            },
        },
    ]
    ensemble_candidates: list[dict[str, Any]] = []
    ensemble_builders = {
        "base": baseline_builder,
        "norm": norm_builder,
        "norm_c3": norm_c3_builder,
        "c25": c25_builder,
        "char25_c4": char25_c4_builder,
        "cwnone": cwnone_builder,
    }
    for index, spec in enumerate(ensemble_specs, start=1):
        weights = spec["weights"]

        def builder(
            train_frame: pd.DataFrame,
            eval_frame: pd.DataFrame,
            weights: dict[str, float] = weights,
        ) -> np.ndarray:
            parts = []
            part_weights = []
            for name, weight in weights.items():
                if weight:
                    parts.append(ensemble_builders[name](train_frame, eval_frame))
                    part_weights.append(weight)
            return np.average(np.vstack(parts), axis=0, weights=np.asarray(part_weights))

        ensemble_candidates.append(
            _evaluate_spec(
                train=train,
                dev=dev,
                truth_safe=truth_safe,
                current_candidate=current_candidate,
                safe_fp_budget_delta=15,
                trial_id=f"p5-memory-guided-family-ensemble-{index:02d}",
                source="memory_guided_probability_ensemble",
                operator="combine.memory_guided_model_family_views",
                change_surface="memory-guided no-fastText family ensemble frontier",
                params={
                    "label": spec["label"],
                    "weights": weights,
                    "safe_fp_budget_delta": 15,
                },
                probability_builder=builder,
            )
        )
    ensemble_candidate = _select_best_by_direction_score(
        ensemble_candidates,
        current_candidate,
    )
    ensemble_candidate["trial_id"] = "p5-memory-guided-family-ensemble"

    risk_specs = [
        (
            "p5-risk-char25-c4",
            "adapt.character_robustness",
            _candidate_builder_for_logreg(c_value=4.0, char_range=(2, 5)),
            {"C": 4.0, "char_range": [2, 5], "selector": "prompt"},
        ),
        (
            "p5-risk-norm-c3",
            "adapt.arabic_normalization_surface",
            _candidate_builder_for_logreg(c_value=3.0, selector_name="norm_ar"),
            {"C": 3.0, "char_range": [3, 5], "selector": "norm_ar"},
        ),
    ]
    risk_candidates: list[dict[str, Any]] = []
    for trial_id, base_operator, builder, params in risk_specs:
        risk_candidates.append(
            _evaluate_spec(
                train=train,
                dev=dev,
                truth_safe=truth_safe,
                current_candidate=current_candidate,
                safe_fp_budget_delta=45,
                trial_id=trial_id,
                source="expanded_risk_audit",
                operator="audit.high_dev_score_risk",
                change_surface=f"high-dev-score audit for {base_operator}",
                params={
                    **params,
                    "audited_operator": base_operator,
                    "safe_fp_budget_delta": 45,
                },
                probability_builder=builder,
            )
        )
    risk_candidate = max(risk_candidates, key=lambda candidate: candidate["score"])
    risk_candidate["trial_id"] = "p5-high-dev-risk-audit"

    selected = [
        regularization_candidate,
        threshold_candidate,
        normalization_candidate,
        ensemble_candidate,
        risk_candidate,
    ]
    rounds: list[dict[str, Any]] = []
    for round_number, candidate in enumerate(selected, start=1):
        candidate, gate_result = _gate_and_strip_candidate(
            train=train,
            candidate=candidate,
            current_candidate=current_candidate,
            remaining_total_submissions=remaining_total_submissions,
        )
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
            f"{operator_id} was selected after P4 found no safe local gain and "
            f"the only official-submitted score remains {official_result.get('score')} "
            f"for submission {official_result.get('submission_id')}."
        ),
        "hypothesis": (
            "A broader but still local evidence-gated search can separate promising "
            "directions from dev-only gains before spending another scarce submission."
        ),
        "change_surface": candidate["change_surface"],
        "expected_effect": (
            f"local macro-F1={candidate['score']:.6f}; "
            f"unsafe->safe={evaluation['unsafe_predicted_safe_count']}; "
            f"safe->unsafe={evaluation['safe_predicted_unsafe_count']}; "
            f"direction_score={candidate.get('direction_score', 0.0):.6f}"
        ),
        "risk": (
            "Local dev gains may come from threshold overfit, CV regression, or safe "
            "false-positive inflation; official score is rounded and cannot be inferred."
        ),
        "cheapest_validation": (
            "Evaluate on public dev labels, 3-fold train CV, unsafe miss delta, safe "
            "false-positive delta, and submission-budget gate."
        ),
        "rollback_or_stop_condition": (
            "Stop or downweight if gate reports CV regression, insufficient local delta, "
            "unsafe miss regression, or safe false-positive regression."
        ),
        "method": "arguard_b1_p5_expanded_exploration",
        "optimizer": candidate["source"],
        "adapter": "arguard-b1-p5-expanded-exploration",
        "target_scope": "public_train_dev_only",
        "params": candidate.get("params", {}),
        "official_scores_claimed": False,
    }


def build_method_search_inputs(p5_payload: dict[str, Any]) -> dict[str, Any]:
    official_result = p5_payload["official_result"]
    current_candidate = p5_payload["current_candidate"]
    candidate_rounds = p5_payload["candidate_rounds"]
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
            {
                "proposals": [
                    _proposal_from_candidate(candidate, official_result)
                ]
            }
        )
        round_gate_results.append({"gate_results": [gate_result]})

    return {
        "context": {
            "schema_version": "2026-06-30.arguard-b1-p5-expanded-context.v1",
            "target_id": TARGET_ID,
            "objective": (
                "Run five local-evidence MethodSearch rounds after the official P1 "
                "score to find a better optimization direction without claiming a new "
                "official score."
            ),
            "official_result": official_result,
            "current_candidate": {
                "trial_id": current_candidate["trial_id"],
                "score": current_candidate["score"],
                "evaluation": current_candidate["evaluation"],
            },
            "best_direction": p5_payload.get("best_direction"),
            "submission_budget": p5_payload.get("submission_budget", {}),
            "prior_memory": p5_payload.get("prior_memory"),
            "official_scores_claimed": False,
        },
        "operators": operators,
        "round_proposals": round_proposals,
        "round_gate_results": round_gate_results,
    }


def _pick_best_direction(candidate_rounds: list[dict[str, Any]]) -> dict[str, Any]:
    scored_rounds = [
        item for item in candidate_rounds if "direction_score" in item["proposal"]
    ]
    if not scored_rounds:
        scored_rounds = candidate_rounds
    best_round = max(
        scored_rounds,
        key=lambda item: (
            item["gate_result"]["status"] == "passed",
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
            "Gate-passing direction found."
            if gate_result["status"] == "passed"
            else "Best local direction remains exploratory because submission gate did not pass."
        ),
        "official_scores_claimed": False,
    }


def _write_readme(path: Path, *, payload: dict[str, Any], trajectory: dict[str, Any]) -> None:
    best = payload["best_direction"]
    recommendation = payload["submission_recommendation"]
    lines = [
        "# ArGuard B1 P5 扩展探索",
        "",
        "本目录沿着已提交 P1 官方结果继续运行 5 轮 ml-research-loop MethodSearch/gate/memory 探索，目标是找出更有希望的下一步方向，而不是直接消耗新的 Codabench 提交次数。",
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
            "- 所有 evidence 都来自公开 train/dev 的 local evidence 和 3-fold train CV。",
            "- P5 用 official P1 score 作为方向反馈，但不把 local evidence 升格为 official score。",
            "- 如果 gate 没有 `passed`，不会生成新的 `prediction.zip`。",
            "",
            "## 文件",
            "",
            "- `expanded-exploration-run.json`：候选、CV、gate、best direction 和提交建议。",
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
    p4_memory: Path | None,
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
            "but P5 does not claim a new official score."
        ),
        "official_scores_claimed": False,
    }
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
    best_direction = _pick_best_direction(candidate_rounds)
    prior_memory = _load_optional_json(p4_memory)
    payload = {
        "schema_version": "2026-06-30.arguard-b1-p5-expanded-exploration.v1",
        "target_id": TARGET_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "expanded_method_search_exploration",
        "official_result": official_result,
        "official_scores_claimed": False,
        "claim_boundary": (
            "Local public train/dev evidence only. P5 searches for direction quality "
            "and does not upload or claim a new official score."
        ),
        "dataset": {
            "train_rows": int(len(train)),
            "dev_with_label_rows": int(len(dev)),
        },
        "submission_budget": submission_budget,
        "current_candidate": current_candidate,
        "prior_memory": prior_memory,
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
        trajectory_name="arguard-b1-p5-expanded-exploration",
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
            "At least one expanded-search candidate passed local/CV/safe gate."
            if best_round
            else "No expanded-search candidate passed local/CV/safe gate; use best_direction for next exploration, not submission."
        ),
        "official_scores_claimed": False,
    }
    payload["method_search_trajectory_ref"] = "method-search-trajectory.json"
    payload["submission_recommendation"] = recommendation
    payload["generated_prediction_zip"] = None
    _json_write(output_dir / "expanded-exploration-run.json", payload)
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
        "--p4-memory",
        default=(
            "docs/hf-evaluation/arguard-b1-p4-official-guided-method-search/"
            "gate-feedback-memory-store.json"
        ),
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
        p4_memory=args.p4_memory,
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
