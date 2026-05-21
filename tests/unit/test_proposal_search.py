from __future__ import annotations

from lib.proposal_search import build_proposal_search


def test_proposal_search_keeps_failed_items_out_of_frontier() -> None:
    items = [
        {
            "proposal_id": "p1",
            "proposal_family": "routing",
            "score_delta": {"dev": 0.4, "canary": 0.2},
            "promote_to_default": True,
            "continue_branch": True,
        },
        {
            "proposal_id": "p2",
            "parent_proposal_id": "p1",
            "proposal_family": "routing",
            "score_delta": {"dev": 0.7, "canary": -0.1},
            "failure_labels": ["canary_not_confirmed"],
            "rollback_reason": "canary regression",
        },
        {
            "proposal_id": "p3",
            "proposal_family": "prompt",
            "score_delta": {"dev": 0.3, "holdout": 0.1},
            "continue_branch": True,
        },
    ]

    result = build_proposal_search(items)

    assert result["status"] == "supported_candidate_found"
    assert result["best_proposal_id"] == "p1"
    assert result["pareto_frontier"] == [
        {
            "proposal_id": "p1",
            "proposal_family": "routing",
            "parent_proposal_id": None,
            "score_delta": {"dev": 0.4, "canary": 0.2},
            "recommendation": "promote_to_default",
        },
        {
            "proposal_id": "p3",
            "proposal_family": "prompt",
            "parent_proposal_id": None,
            "score_delta": {"dev": 0.3, "holdout": 0.1},
            "recommendation": "continue_branch",
        },
    ]
    assert result["rollback_proposals"] == [
        {
            "proposal_id": "p2",
            "proposal_family": "routing",
            "parent_proposal_id": "p1",
            "failure_labels": ["canary_not_confirmed"],
            "rollback_reason": "canary regression",
        }
    ]
    assert result["continue_branches"] == [
        {
            "proposal_id": "p1",
            "proposal_family": "routing",
            "parent_proposal_id": None,
            "reason": "promoted_candidate",
        },
        {
            "proposal_id": "p3",
            "proposal_family": "prompt",
            "parent_proposal_id": None,
            "reason": "continue_branch_requested",
        },
    ]
    assert result["official_scores_claimed"] is False
    assert "not an official score claim" in result["claim_boundary"]


def test_dev_gain_without_promotion_evidence_needs_confirmation() -> None:
    result = build_proposal_search(
        [
            {
                "proposal_id": "p-dev",
                "proposal_family": "prompt",
                "score_delta": {"dev": 1.2},
                "continue_branch": True,
            }
        ]
    )

    assert result["status"] == "candidate_needs_confirmation"
    assert result["best_proposal_id"] == "p-dev"
    assert result["pareto_frontier"] == [
        {
            "proposal_id": "p-dev",
            "proposal_family": "prompt",
            "parent_proposal_id": None,
            "score_delta": {"dev": 1.2},
            "recommendation": "candidate_needs_confirmation",
        }
    ]
    assert result["continue_branches"] == [
        {
            "proposal_id": "p-dev",
            "proposal_family": "prompt",
            "parent_proposal_id": None,
            "reason": "needs_canary_or_holdout_confirmation",
        }
    ]


def test_supported_candidate_beats_larger_dev_only_delta() -> None:
    result = build_proposal_search(
        [
            {
                "proposal_id": "p-dev-only",
                "proposal_family": "prompt",
                "score_delta": {"dev": 1.0},
            },
            {
                "proposal_id": "p-canary",
                "proposal_family": "prompt",
                "score_delta": {"dev": 0.4, "canary": 0.2},
                "continue_branch": True,
            },
        ]
    )

    assert result["status"] == "supported_candidate_found"
    assert result["best_proposal_id"] == "p-canary"


def test_negative_promotion_delta_is_marked_for_rollback() -> None:
    result = build_proposal_search(
        [
            {
                "proposal_id": "p-negative-canary",
                "proposal_family": "prompt",
                "score_delta": {"dev": 0.9, "canary": -0.1},
            }
        ]
    )

    assert result["status"] == "rollback_or_revise"
    assert result["best_proposal_id"] is None
    assert result["pareto_frontier"] == []
    assert result["rollback_proposals"] == [
        {
            "proposal_id": "p-negative-canary",
            "proposal_family": "prompt",
            "parent_proposal_id": None,
            "failure_labels": ["canary_regression"],
            "rollback_reason": "canary_delta_lt_0",
        }
    ]
    assert result["continue_branches"] == []


def test_boolean_metric_values_do_not_count_as_numeric_gains() -> None:
    result = build_proposal_search(
        [
            {
                "proposal_id": "p-bool",
                "proposal_family": "prompt",
                "score_delta": {"dev": True, "canary": True},
            }
        ]
    )

    assert result["status"] == "rollback_or_revise"
    assert result["best_proposal_id"] is None
    assert result["selected_next_nodes"] == []


def test_reflection_and_evaluation_shapes_are_normalized() -> None:
    result = build_proposal_search(
        [
            {
                "proposal_id": "p-reflect",
                "proposal": {
                    "proposal_id": "p-reflect",
                    "parent_proposal_id": "p-root",
                    "proposal_family": "decoding",
                },
                "evaluation": {"dev_delta": {"SHIFT": 0.2}, "canary_delta": {"SHIFT": 0.1}},
                "status": "candidate_supported",
                "recommended_next_action": "promote_candidate_if_canary_confirmed",
            },
            {
                "proposal_id": "p-eval",
                "parent_proposal_id": "p-root",
                "proposal_family": "prompt",
                "dev_delta": {"SHIFT": 0.5},
                "holdout_delta": {"SHIFT": 0.05},
                "continue_branch": True,
            },
        ]
    )

    assert result["status"] == "supported_candidate_found"
    assert result["best_proposal_id"] == "p-eval"
    assert [item["proposal_id"] for item in result["pareto_frontier"]] == [
        "p-eval",
        "p-reflect",
    ]


def test_tree_search_selects_diverse_next_nodes_under_branch_budget() -> None:
    result = build_proposal_search(
        [
            {
                "proposal_id": "root-routing",
                "proposal_family": "routing",
                "score_delta": {"dev": 0.2, "canary": 0.05},
            },
            {
                "proposal_id": "routing-child-a",
                "parent_proposal_id": "root-routing",
                "proposal_family": "routing",
                "score_delta": {"dev": 0.8},
            },
            {
                "proposal_id": "routing-child-b",
                "parent_proposal_id": "root-routing",
                "proposal_family": "routing",
                "score_delta": {"dev": 0.7, "canary": 0.1},
            },
            {
                "proposal_id": "prompt-child",
                "parent_proposal_id": "root-prompt",
                "proposal_family": "prompt",
                "score_delta": {"dev": 0.45, "holdout": 0.08},
            },
        ],
        branch_budget=2,
        diversity_constraint={"max_per_family": 1},
    )

    assert result["best_so_far"] == {
        "proposal_id": "routing-child-b",
        "proposal_family": "routing",
        "parent_proposal_id": "root-routing",
        "score_delta": {"dev": 0.7, "canary": 0.1},
        "recommendation": "continue_branch",
    }
    assert result["proposal_tree"]["nodes"] == [
        {
            "proposal_id": "root-routing",
            "proposal_family": "routing",
            "parent_proposal_id": None,
            "child_proposal_ids": ["routing-child-a", "routing-child-b"],
            "depth": 0,
        },
        {
            "proposal_id": "routing-child-a",
            "proposal_family": "routing",
            "parent_proposal_id": "root-routing",
            "child_proposal_ids": [],
            "depth": 1,
        },
        {
            "proposal_id": "routing-child-b",
            "proposal_family": "routing",
            "parent_proposal_id": "root-routing",
            "child_proposal_ids": [],
            "depth": 1,
        },
        {
            "proposal_id": "prompt-child",
            "proposal_family": "prompt",
            "parent_proposal_id": "root-prompt",
            "child_proposal_ids": [],
            "depth": 1,
        },
    ]
    assert [node["proposal_id"] for node in result["selected_next_nodes"]] == [
        "routing-child-b",
        "prompt-child",
    ]
    assert all(node["promotion_gate"] == "passed" for node in result["selected_next_nodes"])
    assert result["stop_reason"] == "branch_budget_exhausted"
    assert result["official_scores_claimed"] is False


def test_tree_search_keeps_dev_only_candidate_below_promotion_gate() -> None:
    result = build_proposal_search(
        [
            {
                "proposal_id": "dev-only",
                "proposal_family": "prompt",
                "score_delta": {"dev": 0.9},
            },
            {
                "proposal_id": "confirmed",
                "proposal_family": "decoding",
                "score_delta": {"dev": 0.3, "canary": 0.05},
            },
        ],
        branch_budget=3,
    )

    assert result["best_so_far"]["proposal_id"] == "confirmed"
    assert result["selected_next_nodes"] == [
        {
            "proposal_id": "confirmed",
            "proposal_family": "decoding",
            "parent_proposal_id": None,
            "score_delta": {"dev": 0.3, "canary": 0.05},
            "selection_reason": "promotion_gate_passed",
            "promotion_gate": "passed",
        },
        {
            "proposal_id": "dev-only",
            "proposal_family": "prompt",
            "parent_proposal_id": None,
            "score_delta": {"dev": 0.9},
            "selection_reason": "needs_canary_or_holdout_confirmation",
            "promotion_gate": "pending",
        },
    ]
    assert result["stop_reason"] == "frontier_open"
