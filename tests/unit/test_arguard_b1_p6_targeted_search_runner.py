from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_runner_module():
    script = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "hf-evaluation"
        / "arguard-b1-p6-targeted-memory-guided-search"
        / "run_arguard_b1_p6_targeted_search.py"
    )
    spec = importlib.util.spec_from_file_location("arguard_b1_p6_runner", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_arguard_b1_p6_runner_builds_targeted_method_search_inputs():
    runner = _load_runner_module()
    payload = {
        "official_result": {
            "submission_id": "819950",
            "score": 0.93,
            "visible_rank": 3,
            "leaderboard_entry_count": 6,
            "top_visible_score": 0.94,
        },
        "current_candidate": {
            "trial_id": "p1-current-word-char-logreg",
            "score": 0.9287139293764408,
            "evaluation": {
                "unsafe_predicted_safe_count": 69,
                "safe_predicted_unsafe_count": 42,
            },
        },
        "p5_best_direction": {
            "candidate_id": "p5-memory-guided-family-ensemble",
            "operator_id": "combine.memory_guided_model_family_views",
            "submission_ready": False,
        },
        "candidate_rounds": [
            {
                "round_number": 1,
                "proposal": {
                    "trial_id": "p6-family-weight-frontier",
                    "operator": "combine.memory_guided_weight_frontier",
                    "source": "targeted_probability_ensemble",
                    "change_surface": "family weights",
                    "score": 0.9297,
                    "direction_score": 0.0015,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 65,
                        "safe_predicted_unsafe_count": 44,
                    },
                    "params": {"weights": {"char25_c4": 1.0}},
                },
                "gate_result": {
                    "proposal_id": "p6-family-weight-frontier",
                    "operator_id": "combine.memory_guided_weight_frontier",
                    "status": "near_pass",
                    "score": 0.9297,
                    "hard_blockers": [],
                    "official_scores_claimed": False,
                },
            },
            {
                "round_number": 2,
                "proposal": {
                    "trial_id": "p6-threshold-tightening",
                    "operator": "refine.memory_guided_threshold_tightening",
                    "source": "targeted_threshold_grid",
                    "change_surface": "threshold and safe budget",
                    "score": 0.9291,
                    "direction_score": 0.0008,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 66,
                        "safe_predicted_unsafe_count": 43,
                    },
                    "params": {"safe_fp_budget_delta": 5},
                },
                "gate_result": {
                    "proposal_id": "p6-threshold-tightening",
                    "operator_id": "refine.memory_guided_threshold_tightening",
                    "status": "blocked",
                    "score": 0.9291,
                    "hard_blockers": ["insufficient_local_score_delta"],
                    "official_scores_claimed": False,
                },
            },
            {
                "round_number": 3,
                "proposal": {
                    "trial_id": "p6-member-regularization-frontier",
                    "operator": "tune.memory_guided_member_regularization",
                    "source": "targeted_member_regularization",
                    "change_surface": "member regularization",
                    "score": 0.9298,
                    "direction_score": 0.0016,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 64,
                        "safe_predicted_unsafe_count": 45,
                    },
                    "params": {"member": "norm_c3"},
                },
                "gate_result": {
                    "proposal_id": "p6-member-regularization-frontier",
                    "operator_id": "tune.memory_guided_member_regularization",
                    "status": "near_pass",
                    "score": 0.9298,
                    "hard_blockers": [],
                    "official_scores_claimed": False,
                },
            },
            {
                "round_number": 4,
                "proposal": {
                    "trial_id": "p6-cv-stability-audit",
                    "operator": "audit.memory_guided_cv_stability",
                    "source": "targeted_cv_stability_audit",
                    "change_surface": "multi-seed CV",
                    "score": 0.9297,
                    "direction_score": 0.0014,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 65,
                        "safe_predicted_unsafe_count": 44,
                    },
                    "params": {"cv_seeds": [20260630, 20260701]},
                },
                "gate_result": {
                    "proposal_id": "p6-cv-stability-audit",
                    "operator_id": "audit.memory_guided_cv_stability",
                    "status": "near_pass",
                    "score": 0.9297,
                    "hard_blockers": [],
                    "official_scores_claimed": False,
                },
            },
            {
                "round_number": 5,
                "proposal": {
                    "trial_id": "p6-relaxed-risk-boundary",
                    "operator": "audit.memory_guided_relaxed_risk_boundary",
                    "source": "targeted_relaxed_risk_audit",
                    "change_surface": "risk boundary",
                    "score": 0.9302,
                    "direction_score": -0.002,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 45,
                        "safe_predicted_unsafe_count": 63,
                    },
                    "params": {"safe_fp_budget_delta": 30},
                },
                "gate_result": {
                    "proposal_id": "p6-relaxed-risk-boundary",
                    "operator_id": "audit.memory_guided_relaxed_risk_boundary",
                    "status": "blocked",
                    "score": 0.9302,
                    "hard_blockers": ["safe_false_positive_regression"],
                    "official_scores_claimed": False,
                },
            },
        ],
        "best_direction": {
            "candidate_id": "p6-family-weight-frontier",
            "operator_id": "combine.memory_guided_weight_frontier",
            "submission_ready": False,
        },
    }

    inputs = runner.build_method_search_inputs(payload)

    assert inputs["context"]["search_focus"] == "p5-memory-guided-family-ensemble"
    assert inputs["context"]["official_scores_claimed"] is False
    assert inputs["context"]["best_direction"]["submission_ready"] is False
    assert len(inputs["round_proposals"]) == 5
    assert len(inputs["round_gate_results"]) == 5
    assert inputs["operators"] == [
        "combine.memory_guided_weight_frontier",
        "refine.memory_guided_threshold_tightening",
        "tune.memory_guided_member_regularization",
        "audit.memory_guided_cv_stability",
        "audit.memory_guided_relaxed_risk_boundary",
    ]
    first_proposal = inputs["round_proposals"][0]["proposals"][0]
    for field in runner.REQUIRED_PROPOSAL_FIELDS:
        assert field in first_proposal
