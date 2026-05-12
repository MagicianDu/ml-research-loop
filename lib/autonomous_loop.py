"""Autonomous research loop policy decisions."""

from __future__ import annotations

from typing import Any


def decide_next_autonomous_action(
    case_summary: dict,
    budget: dict,
    latest_review: dict,
) -> dict[str, Any]:
    """Decide the next bounded autonomous research action.

    The policy is intentionally deterministic and side-effect free. It turns the
    latest case state, budget, and review into a next action for an outer runner.
    """

    completed_rounds = int(budget.get("completed_rounds", 0))
    max_rounds = int(budget.get("max_rounds", 0))
    failed_milestone_count = int(case_summary.get("failed_milestone_count", 0))
    supported_claim_count = int(case_summary.get("supported_claim_count", 0))
    review_decision = (
        latest_review.get("loop_decision", {}).get("decision")
        if isinstance(latest_review.get("loop_decision"), dict)
        else None
    )

    if completed_rounds >= max_rounds:
        action = "stop"
        reason_category = "budget_exhausted"
        requires_human_confirmation = False
    elif failed_milestone_count > 0:
        action = "debug_failures"
        reason_category = "needs_failure_debugging"
        requires_human_confirmation = False
    elif supported_claim_count == 0:
        action = "collect_evidence"
        reason_category = "needs_more_evidence"
        requires_human_confirmation = False
    elif review_decision == "stop":
        action = "write_proof_archive"
        reason_category = "ready_for_proof_archive"
        requires_human_confirmation = True
    else:
        action = "continue_experiment"
        reason_category = "continue_experiment"
        requires_human_confirmation = False

    decision: dict[str, Any] = {
        "action": action,
        "reason_category": reason_category,
        "requires_human_confirmation": requires_human_confirmation,
        "official_scores_claimed": False,
        "completed_rounds": completed_rounds,
        "max_rounds": max_rounds,
    }
    if "case_id" in case_summary:
        decision["case_id"] = case_summary["case_id"]
    return decision
