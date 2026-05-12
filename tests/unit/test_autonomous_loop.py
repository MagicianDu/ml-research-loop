from __future__ import annotations

from lib.autonomous_loop import decide_next_autonomous_action


def test_loop_stops_when_budget_exhausted() -> None:
    decision = decide_next_autonomous_action(
        case_summary={
            "case_id": "case-budget",
            "supported_claim_count": 1,
            "failed_milestone_count": 0,
        },
        budget={"max_rounds": 3, "completed_rounds": 3},
        latest_review={"loop_decision": {"decision": "continue"}},
    )

    assert decision["action"] == "stop"
    assert decision["reason_category"] == "budget_exhausted"
    assert decision["requires_human_confirmation"] is False
    assert decision["official_scores_claimed"] is False
    assert decision["case_id"] == "case-budget"
    assert decision["completed_rounds"] == 3
    assert decision["max_rounds"] == 3


def test_loop_debugs_failed_milestones_before_collecting_more_evidence() -> None:
    decision = decide_next_autonomous_action(
        case_summary={"supported_claim_count": 0, "failed_milestone_count": 1},
        budget={"max_rounds": 3, "completed_rounds": 1},
        latest_review={"loop_decision": {"decision": "stop"}},
    )

    assert decision["action"] == "debug_failures"
    assert decision["reason_category"] == "needs_failure_debugging"
    assert decision["requires_human_confirmation"] is False


def test_loop_collects_evidence_when_no_claim_is_supported() -> None:
    decision = decide_next_autonomous_action(
        case_summary={"supported_claim_count": 0, "failed_milestone_count": 0},
        budget={"max_rounds": 3, "completed_rounds": 1},
        latest_review={"loop_decision": {"decision": "continue"}},
    )

    assert decision["action"] == "collect_evidence"
    assert decision["reason_category"] == "needs_more_evidence"
    assert decision["requires_human_confirmation"] is False


def test_loop_writes_proof_archive_when_review_stops() -> None:
    decision = decide_next_autonomous_action(
        case_summary={"supported_claim_count": 1, "failed_milestone_count": 0},
        budget={"max_rounds": 3, "completed_rounds": 1},
        latest_review={"loop_decision": {"decision": "stop"}},
    )

    assert decision["action"] == "write_proof_archive"
    assert decision["reason_category"] == "ready_for_proof_archive"
    assert decision["requires_human_confirmation"] is True


def test_loop_continues_experiment_by_default() -> None:
    decision = decide_next_autonomous_action(
        case_summary={"supported_claim_count": 1, "failed_milestone_count": 0},
        budget={"max_rounds": 3, "completed_rounds": 1},
        latest_review={"loop_decision": {"decision": "continue"}},
    )

    assert decision["action"] == "continue_experiment"
    assert decision["reason_category"] == "continue_experiment"
    assert decision["requires_human_confirmation"] is False
