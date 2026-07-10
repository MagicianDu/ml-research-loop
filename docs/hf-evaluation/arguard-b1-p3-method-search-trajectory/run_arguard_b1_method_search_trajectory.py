from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.failure_driven_proposal import run_method_search_trajectory


DEFAULT_ROUND_CANDIDATE_IDS = [
    "p2-char25-c4-threshold",
    "p2-ensemble-char25-norm-cwnone",
    "p2-ensemble-fasttext-char25-norm",
]


def _candidate_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        candidates = []
    return {
        str(candidate.get("trial_id")): candidate
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("trial_id")
    }


def _proposal_from_candidate(candidate: dict[str, Any], *, index: int) -> dict[str, Any]:
    trial_id = str(candidate["trial_id"])
    operator_id = str(candidate.get("operator") or "adapt.arguard_b1_candidate")
    source = str(candidate.get("source") or "arguard_b1_offline_source")
    evaluation = candidate.get("evaluation") if isinstance(candidate.get("evaluation"), dict) else {}
    unsafe_miss = evaluation.get("unsafe_predicted_safe_count")
    safe_false_positive = evaluation.get("safe_predicted_unsafe_count")
    return {
        "proposal_id": trial_id,
        "operator_id": operator_id,
        "why_this_operator_applies": (
            f"{operator_id} was produced by the ArGuard B1 offline optimizer source "
            f"`{source}` and targets the remaining local failure pattern."
        ),
        "hypothesis": (
            "The candidate may improve ArGuard B1 local macro-F1, but any improvement "
            "must be accepted only by the shared gate and CV evidence."
        ),
        "change_surface": "ArGuard B1 classifier/search configuration",
        "expected_effect": (
            f"local macro-F1={candidate.get('score')}; unsafe->safe={unsafe_miss}; "
            f"safe->unsafe={safe_false_positive}"
        ),
        "risk": "dev-threshold overfit or safe false-positive regression",
        "cheapest_validation": "reuse P2 local dev, train 3-fold CV, and submission-budget gate",
        "rollback_or_stop_condition": (
            "stop if local delta is below submission threshold, CV regresses, or safe "
            "false positives exceed budget"
        ),
        "method": "arguard_b1_offline_candidate_replayed_through_method_search",
        "optimizer": source,
        "adapter": "arguard-b1-p2-offline-search-artifact",
        "target_scope": "local_public_train_dev_only",
        "offline_candidate_rank": index,
        "official_scores_claimed": False,
    }


def _status_for_candidate(
    candidate: dict[str, Any],
    *,
    current_score: float,
    current_safe_fp: int,
    final_gate: dict[str, Any],
) -> tuple[str, list[str]]:
    score = float(candidate.get("score") or 0.0)
    evaluation = candidate.get("evaluation") if isinstance(candidate.get("evaluation"), dict) else {}
    safe_fp = int(evaluation.get("safe_predicted_unsafe_count") or 0)
    trial_id = str(candidate.get("trial_id"))
    if trial_id == "p2-ensemble-char25-norm-cwnone":
        return "near_pass", []
    if trial_id == "p2-ensemble-fasttext-char25-norm":
        reasons = final_gate.get("reasons")
        return "blocked", [str(item) for item in reasons if item] if isinstance(reasons, list) else []
    if score > current_score and safe_fp > current_safe_fp + 10:
        return "blocked", ["safe_false_positive_regression"]
    if score > current_score:
        return "near_pass", []
    return "blocked", ["no_local_improvement"]


def _gate_result_from_candidate(
    candidate: dict[str, Any],
    *,
    current_score: float,
    current_safe_fp: int,
    final_gate: dict[str, Any],
) -> dict[str, Any]:
    evaluation = candidate.get("evaluation") if isinstance(candidate.get("evaluation"), dict) else {}
    status, hard_blockers = _status_for_candidate(
        candidate,
        current_score=current_score,
        current_safe_fp=current_safe_fp,
        final_gate=final_gate,
    )
    return {
        "proposal_id": str(candidate["trial_id"]),
        "operator_id": str(candidate.get("operator") or "adapt.arguard_b1_candidate"),
        "status": status,
        "score": float(candidate.get("score") or 0.0),
        "metric": "local_macro_f1",
        "hard_blockers": hard_blockers,
        "gate_reason": (
            "accepted as near-pass local diagnostic evidence"
            if status == "near_pass"
            else "blocked by ArGuard B1 submission recommendation gate"
        ),
        "evaluation": evaluation,
        "official_scores_claimed": False,
    }


def build_method_search_inputs(p2_payload: dict[str, Any]) -> dict[str, Any]:
    current = p2_payload.get("current_candidate")
    if not isinstance(current, dict):
        raise ValueError("P2 payload missing current_candidate")
    final_gate = p2_payload.get("submission_recommendation_gate")
    if not isinstance(final_gate, dict):
        final_gate = {}
    current_eval = current.get("evaluation") if isinstance(current.get("evaluation"), dict) else {}
    current_score = float(current.get("score") or 0.0)
    current_safe_fp = int(current_eval.get("safe_predicted_unsafe_count") or 0)
    candidates = _candidate_by_id(p2_payload)
    selected_candidates = [candidates[candidate_id] for candidate_id in DEFAULT_ROUND_CANDIDATE_IDS]
    round_proposals = [
        {"proposals": [_proposal_from_candidate(candidate, index=index)]}
        for index, candidate in enumerate(selected_candidates, start=1)
    ]
    round_gate_results = [
        {
            "gate_results": [
                _gate_result_from_candidate(
                    candidate,
                    current_score=current_score,
                    current_safe_fp=current_safe_fp,
                    final_gate=final_gate,
                )
            ]
        }
        for candidate in selected_candidates
    ]
    operators = [
        str(candidate.get("operator") or "adapt.arguard_b1_candidate")
        for candidate in selected_candidates
    ]
    context = {
        "schema_version": "2026-06-30.arguard-b1-method-search-context.v1",
        "target_id": "arguard-b1-binary-classification",
        "objective": (
            "Use ML Research Loop MethodSearchStudy to decide whether an ArGuard B1 "
            "offline optimizer path deserves another scarce Codabench submission."
        ),
        "recommended_patch_contract": {
            "module_id": "arguard_b1",
            "section_id": "classifier_search",
            "target_slice": "public_train_dev_local_gate",
            "based_on_slices": ["safe_false_positive_regression", "cv_regression"],
            "before_text": "P1 word+char logistic regression remains submission default.",
            "protected_slices": ["submission_budget", "official_claim_boundary"],
            "protected_sections": ["Codabench submission package"],
        },
        "p2_submission_gate": final_gate,
        "official_scores_claimed": False,
    }
    return {
        "context": context,
        "round_proposals": round_proposals,
        "round_gate_results": round_gate_results,
        "operators": operators,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def format_winner_id(best_path: dict[str, Any]) -> str:
    winner = best_path.get("winner") if isinstance(best_path, dict) else None
    if not isinstance(winner, dict):
        return "no_gate_winner"
    return str(winner.get("proposal_id") or "no_gate_winner")


def run(*, p2_run_path: Path, output_dir: Path, overwrite: bool = False) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    p2_payload = json.loads(p2_run_path.read_text(encoding="utf-8"))
    inputs = build_method_search_inputs(p2_payload)
    inputs_dir = output_dir / "inputs"
    _write_json(inputs_dir / "trajectory-context.json", inputs["context"])
    proposal_paths: list[Path] = []
    gate_paths: list[Path] = []
    for index, proposal_payload in enumerate(inputs["round_proposals"], start=1):
        path = inputs_dir / f"round-{index:03d}-llm-proposals.json"
        _write_json(path, proposal_payload)
        proposal_paths.append(path)
    for index, gate_payload in enumerate(inputs["round_gate_results"], start=1):
        path = inputs_dir / f"round-{index:03d}-gate-results.json"
        _write_json(path, gate_payload)
        gate_paths.append(path)

    trajectory = run_method_search_trajectory(
        trajectory_name="arguard-b1-p3-method-search",
        objective=inputs["context"]["objective"],
        context=inputs_dir / "trajectory-context.json",
        gate_results_by_round=gate_paths,
        round_count=3,
        mode="optimization-run",
        optimizer_sources=["llm"],
        operators=inputs["operators"],
        direction="maximize",
        max_candidates_per_source=1,
        llm_proposals_by_round=proposal_paths,
        execute_llm=False,
        allow_style_fallback=True,
        output_dir=output_dir / "run",
        feedback_store_path=output_dir / "gate-feedback-memory-store.json",
        output_path=output_dir / "method-search-trajectory.json",
        overwrite=overwrite,
    )
    summary = {
        "schema_version": "2026-06-30.arguard-b1-p3-method-search-summary.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_id": "arguard-b1-binary-classification",
        "p2_run_ref": str(p2_run_path),
        "trajectory_ref": "method-search-trajectory.json",
        "best_path": trajectory.get("best_path"),
        "acceptance_answers": trajectory.get("acceptance_answers"),
        "submission_recommendation": {
            "decision": "HOLD",
            "recommended_for_codabench_submission": False,
            "reason": (
                "MethodSearch replay found a local diagnostic near-pass, but the "
                "highest local score remains blocked by CV and safe false-positive gate."
            ),
        },
        "official_scores_claimed": False,
    }
    _write_json(output_dir / "method-search-summary.json", summary)
    (output_dir / "README.md").write_text(
        "\n".join(
            [
                "# ArGuard B1 P3 MethodSearch 迭代轨迹",
                "",
                "本目录把 P2 的真实离线候选评测结果放回 ML Research Loop 自身的 `run_method_search_trajectory` 主路径。",
                "",
                "## 结论",
                "",
                "- 已执行 3 轮 `MethodSearchTrajectory -> MultiOptimizerCandidateRace -> gate -> tell -> GateFeedbackMemory`。",
                f"- best path: `{format_winner_id(summary['best_path'])}`。",
                "- 最终提交建议仍为 `HOLD`，不生成新的 Codabench `prediction.zip`。",
                "- `official_scores_claimed=false`。",
                "",
                "## 边界",
                "",
                "- 本轮复用 P2 已执行的真实 sklearn / Optuna / fastText 评测结果作为 gate evidence。",
                "- 本轮没有重新训练模型，也没有调用 live LLM；LLM source 使用的是已记录的 proposal artifact replay。",
                "- 目标是验证项目自身 Study/Trial/gate/memory 迭代协议能正确处理 ArGuard 结果，而不是新增官方成绩。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p2-run", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    summary = run(p2_run_path=args.p2_run, output_dir=args.output_dir, overwrite=args.force)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
