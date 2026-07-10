from __future__ import annotations

from typing import Any


def evaluate_submission_candidate_gate(
    *,
    candidate_id: str,
    current_best_score: float,
    candidate_score: float,
    current_cv_score: float,
    candidate_cv_score: float,
    current_unsafe_predicted_safe: int,
    candidate_unsafe_predicted_safe: int,
    current_safe_predicted_unsafe: int | None = None,
    candidate_safe_predicted_unsafe: int | None = None,
    remaining_total_submissions: int,
    min_score_delta: float = 0.003,
    max_cv_regression: float = 0.001,
    max_safe_false_positive_delta: int | None = None,
) -> dict[str, Any]:
    """Gate one ArGuard B1 candidate before spending a scarce Codabench submission."""

    score_delta = round(candidate_score - current_best_score, 10)
    cv_delta = round(candidate_cv_score - current_cv_score, 10)
    unsafe_miss_delta = candidate_unsafe_predicted_safe - current_unsafe_predicted_safe
    safe_false_positive_delta = None
    if (
        current_safe_predicted_unsafe is not None
        and candidate_safe_predicted_unsafe is not None
    ):
        safe_false_positive_delta = (
            candidate_safe_predicted_unsafe - current_safe_predicted_unsafe
        )
    reasons: list[str] = []

    if remaining_total_submissions <= 0:
        reasons.append("submission_budget_exhausted")
    if score_delta < min_score_delta:
        reasons.append("insufficient_local_score_delta")
    if cv_delta < -max_cv_regression:
        reasons.append("cv_regression")
    if unsafe_miss_delta > 0:
        reasons.append("unsafe_miss_regression")
    if (
        safe_false_positive_delta is not None
        and max_safe_false_positive_delta is not None
        and safe_false_positive_delta > max_safe_false_positive_delta
    ):
        reasons.append("safe_false_positive_regression")

    recommended = not reasons
    return {
        "candidate_id": candidate_id,
        "decision": "PASS" if recommended else "HOLD",
        "recommended_for_codabench_submission": recommended,
        "official_scores_claimed": False,
        "metric": "local_macro_f1",
        "current_best_score": current_best_score,
        "candidate_score": candidate_score,
        "score_delta": round(score_delta, 4),
        "current_cv_score": current_cv_score,
        "candidate_cv_score": candidate_cv_score,
        "cv_delta": round(cv_delta, 4),
        "current_unsafe_predicted_safe": current_unsafe_predicted_safe,
        "candidate_unsafe_predicted_safe": candidate_unsafe_predicted_safe,
        "unsafe_miss_delta": unsafe_miss_delta,
        "current_safe_predicted_unsafe": current_safe_predicted_unsafe,
        "candidate_safe_predicted_unsafe": candidate_safe_predicted_unsafe,
        "safe_false_positive_delta": safe_false_positive_delta,
        "remaining_total_submissions": remaining_total_submissions,
        "min_score_delta": min_score_delta,
        "max_cv_regression": max_cv_regression,
        "max_safe_false_positive_delta": max_safe_false_positive_delta,
        "reasons": reasons,
    }
