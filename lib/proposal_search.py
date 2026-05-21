from __future__ import annotations

from typing import Any


PROMOTION_SPLITS = ("canary", "holdout", "external")


def build_proposal_search(items: list[dict[str, Any]]) -> dict[str, Any]:
    proposals = [_normalize_item(item) for item in items]
    rollback_proposals = [_rollback_summary(item) for item in proposals if item["failed"]]
    eligible = [item for item in proposals if not item["failed"] and item["has_gain"]]
    frontier = [_frontier_summary(item) for item in _pareto_frontier(eligible)]
    best = _best_candidate(eligible)
    continue_branches = [_continue_summary(item) for item in eligible if _should_continue(item)]

    if not proposals:
        status = "no_proposals"
    elif best is None:
        status = "rollback_or_revise"
    elif best["has_promotion_evidence"]:
        status = "supported_candidate_found"
    else:
        status = "candidate_needs_confirmation"

    return {
        "status": status,
        "best_proposal_id": best["proposal_id"] if best else None,
        "pareto_frontier": frontier,
        "rollback_proposals": rollback_proposals,
        "continue_branches": continue_branches,
        "claim_boundary": (
            "local proposal search summary only; not an official score claim and not a release claim"
        ),
        "official_scores_claimed": False,
    }


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    proposal = item.get("proposal") if isinstance(item.get("proposal"), dict) else {}
    evaluation = item.get("evaluation") if isinstance(item.get("evaluation"), dict) else {}
    score_delta = _score_delta(item, evaluation)
    failure_labels = _failure_labels(item)
    rollback_reason = _rollback_reason(item)
    negative_promotion_split = _negative_promotion_split(score_delta)
    if negative_promotion_split:
        failure_labels = failure_labels or [f"{negative_promotion_split}_regression"]
        rollback_reason = rollback_reason or f"{negative_promotion_split}_delta_lt_0"
    proposal_id = item.get("proposal_id") or proposal.get("proposal_id")
    promotion_evidence = _has_promotion_evidence(item, score_delta)
    failed = bool(failure_labels or rollback_reason)

    return {
        "proposal_id": proposal_id,
        "proposal_family": item.get("proposal_family") or proposal.get("proposal_family"),
        "parent_proposal_id": item.get("parent_proposal_id") or proposal.get("parent_proposal_id"),
        "score_delta": score_delta,
        "failure_labels": failure_labels,
        "rollback_reason": rollback_reason,
        "promote_to_default": item.get("promote_to_default") is True,
        "continue_branch": item.get("continue_branch") is True,
        "recommended_next_action": item.get("recommended_next_action"),
        "has_gain": _numeric_delta(score_delta.get("dev")) > 0,
        "has_promotion_evidence": promotion_evidence,
        "failed": failed,
    }


def _score_delta(item: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, float]:
    explicit = item.get("score_delta")
    if isinstance(explicit, dict):
        return {
            str(split): float(value)
            for split, value in explicit.items()
            if isinstance(value, (int, float))
        }

    score_delta: dict[str, float] = {}
    for split in ("dev", "canary", "holdout", "external"):
        value = item.get(f"{split}_delta", evaluation.get(f"{split}_delta"))
        numeric = _metric_delta_value(value)
        if numeric is not None:
            score_delta[split] = numeric
    return score_delta


def _metric_delta_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("SHIFT"), (int, float)):
        return float(value["SHIFT"])
    for metric_value in value.values():
        if isinstance(metric_value, (int, float)):
            return float(metric_value)
    return None


def _failure_labels(item: dict[str, Any]) -> list[str]:
    labels = item.get("failure_labels")
    if isinstance(labels, list):
        return [str(label) for label in labels if str(label)]
    validation = item.get("proposal_validation")
    if isinstance(validation, dict) and validation.get("status") == "rejected":
        validation_labels = validation.get("failure_labels", [])
        if isinstance(validation_labels, list):
            return [str(label) for label in validation_labels if str(label)]
    if item.get("status") in {"invalid_proposal", "needs_rollback_or_more_evidence"}:
        return [str(item["status"])]
    return []


def _rollback_reason(item: dict[str, Any]) -> str | None:
    reason = item.get("rollback_reason")
    if isinstance(reason, str) and reason.strip():
        return reason
    reasons = item.get("rollback_reasons")
    if isinstance(reasons, list) and reasons:
        return str(reasons[0])
    evaluation = item.get("evaluation")
    if isinstance(evaluation, dict):
        evaluation_reasons = evaluation.get("rollback_reasons")
        if isinstance(evaluation_reasons, list) and evaluation_reasons:
            return str(evaluation_reasons[0])
    return None


def _has_promotion_evidence(item: dict[str, Any], score_delta: dict[str, float]) -> bool:
    if item.get("promote_to_default") is True or item.get("promotion_gate_passed") is True:
        return True
    evaluation = item.get("evaluation")
    if isinstance(evaluation, dict) and evaluation.get("promotion_gate_passed") is True:
        return True
    return any(score_delta.get(split, 0.0) > 0 for split in PROMOTION_SPLITS)


def _negative_promotion_split(score_delta: dict[str, float]) -> str | None:
    for split in PROMOTION_SPLITS:
        if score_delta.get(split, 0.0) < 0:
            return split
    return None


def _pareto_frontier(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frontier: list[dict[str, Any]] = []
    for item in items:
        if not any(_dominates(other, item) for other in items if other is not item):
            frontier.append(item)
    return sorted(frontier, key=_sort_key)


def _dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left["proposal_family"] != right["proposal_family"]:
        return False
    left_dev = _numeric_delta(left["score_delta"].get("dev"))
    right_dev = _numeric_delta(right["score_delta"].get("dev"))
    left_promotion = _promotion_score(left)
    right_promotion = _promotion_score(right)
    return (
        left_dev >= right_dev
        and left_promotion >= right_promotion
        and (left_dev > right_dev or left_promotion > right_promotion)
    )


def _promotion_score(item: dict[str, Any]) -> float:
    values = [_numeric_delta(item["score_delta"].get(split)) for split in PROMOTION_SPLITS]
    return max(values or [0.0])


def _best_candidate(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    return sorted(items, key=_sort_key)[0]


def _sort_key(item: dict[str, Any]) -> tuple[float, float, float, str]:
    return (
        -float(item["has_promotion_evidence"]),
        -_numeric_delta(item["score_delta"].get("dev")),
        -_promotion_score(item),
        str(item["proposal_id"] or ""),
    )


def _should_continue(item: dict[str, Any]) -> bool:
    return (
        item["promote_to_default"]
        or item["continue_branch"]
        or item["recommended_next_action"] == "promote_candidate_if_canary_confirmed"
        or not item["has_promotion_evidence"]
    )


def _continue_summary(item: dict[str, Any]) -> dict[str, Any]:
    if item["promote_to_default"] or item["recommended_next_action"] == "promote_candidate_if_canary_confirmed":
        reason = "promoted_candidate"
    elif item["has_promotion_evidence"] and item["continue_branch"]:
        reason = "continue_branch_requested"
    else:
        reason = "needs_canary_or_holdout_confirmation"
    return {
        "proposal_id": item["proposal_id"],
        "proposal_family": item["proposal_family"],
        "parent_proposal_id": item["parent_proposal_id"],
        "reason": reason,
    }


def _frontier_summary(item: dict[str, Any]) -> dict[str, Any]:
    if item["promote_to_default"]:
        recommendation = "promote_to_default"
    elif item["has_promotion_evidence"]:
        recommendation = "continue_branch"
    else:
        recommendation = "candidate_needs_confirmation"
    return {
        "proposal_id": item["proposal_id"],
        "proposal_family": item["proposal_family"],
        "parent_proposal_id": item["parent_proposal_id"],
        "score_delta": item["score_delta"],
        "recommendation": recommendation,
    }


def _rollback_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": item["proposal_id"],
        "proposal_family": item["proposal_family"],
        "parent_proposal_id": item["parent_proposal_id"],
        "failure_labels": item["failure_labels"],
        "rollback_reason": item["rollback_reason"],
    }


def _numeric_delta(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0
