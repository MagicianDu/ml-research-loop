from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_runner_module():
    script = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "hf-evaluation"
        / "arguard-b1-p5-expanded-exploration"
        / "run_arguard_b1_p5_expanded_exploration.py"
    )
    spec = importlib.util.spec_from_file_location("arguard_b1_p5_runner", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_arguard_b1_p5_runner_builds_five_round_method_search_inputs():
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
        "candidate_rounds": [
            {
                "round_number": 1,
                "proposal": {
                    "trial_id": "p5-cv-stable-regularization",
                    "operator": "tune.cv_stable_regularization",
                    "source": "expanded_logreg_grid",
                    "change_surface": "regularization",
                    "score": 0.9288,
                    "direction_score": 0.002,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 69,
                        "safe_predicted_unsafe_count": 42,
                    },
                    "params": {"C": 2.5},
                },
                "gate_result": {
                    "proposal_id": "p5-cv-stable-regularization",
                    "operator_id": "tune.cv_stable_regularization",
                    "status": "near_pass",
                    "score": 0.9288,
                    "hard_blockers": [],
                    "official_scores_claimed": False,
                },
            },
            {
                "round_number": 2,
                "proposal": {
                    "trial_id": "p5-safe-recall-frontier",
                    "operator": "refine.safe_recall_frontier",
                    "source": "expanded_threshold_grid",
                    "change_surface": "threshold",
                    "score": 0.9291,
                    "direction_score": 0.001,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 67,
                        "safe_predicted_unsafe_count": 55,
                    },
                    "params": {"safe_fp_budget_delta": 20},
                },
                "gate_result": {
                    "proposal_id": "p5-safe-recall-frontier",
                    "operator_id": "refine.safe_recall_frontier",
                    "status": "blocked",
                    "score": 0.9291,
                    "hard_blockers": ["safe_false_positive_regression"],
                    "official_scores_claimed": False,
                },
            },
            {
                "round_number": 3,
                "proposal": {
                    "trial_id": "p5-arabic-normalization-surface",
                    "operator": "adapt.arabic_normalization_surface",
                    "source": "expanded_normalization_grid",
                    "change_surface": "normalization",
                    "score": 0.9289,
                    "direction_score": 0.0015,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 68,
                        "safe_predicted_unsafe_count": 48,
                    },
                    "params": {"selector": "norm_ar"},
                },
                "gate_result": {
                    "proposal_id": "p5-arabic-normalization-surface",
                    "operator_id": "adapt.arabic_normalization_surface",
                    "status": "near_pass",
                    "score": 0.9289,
                    "hard_blockers": [],
                    "official_scores_claimed": False,
                },
            },
            {
                "round_number": 4,
                "proposal": {
                    "trial_id": "p5-memory-guided-family-ensemble",
                    "operator": "combine.memory_guided_model_family_views",
                    "source": "memory_guided_probability_ensemble",
                    "change_surface": "ensemble",
                    "score": 0.9292,
                    "direction_score": 0.0012,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 68,
                        "safe_predicted_unsafe_count": 50,
                    },
                    "params": {"base_weight": 0.5},
                },
                "gate_result": {
                    "proposal_id": "p5-memory-guided-family-ensemble",
                    "operator_id": "combine.memory_guided_model_family_views",
                    "status": "blocked",
                    "score": 0.9292,
                    "hard_blockers": ["safe_false_positive_regression"],
                    "official_scores_claimed": False,
                },
            },
            {
                "round_number": 5,
                "proposal": {
                    "trial_id": "p5-high-dev-risk-audit",
                    "operator": "audit.high_dev_score_risk",
                    "source": "expanded_risk_audit",
                    "change_surface": "risky local winner audit",
                    "score": 0.9311,
                    "direction_score": -0.01,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 50,
                        "safe_predicted_unsafe_count": 74,
                    },
                    "params": {"includes_fasttext": True},
                },
                "gate_result": {
                    "proposal_id": "p5-high-dev-risk-audit",
                    "operator_id": "audit.high_dev_score_risk",
                    "status": "blocked",
                    "score": 0.9311,
                    "hard_blockers": ["cv_regression", "safe_false_positive_regression"],
                    "official_scores_claimed": False,
                },
            },
        ],
        "best_direction": {
            "candidate_id": "p5-cv-stable-regularization",
            "operator_id": "tune.cv_stable_regularization",
            "submission_ready": False,
        },
    }

    inputs = runner.build_method_search_inputs(payload)

    assert inputs["context"]["official_result"]["submission_id"] == "819950"
    assert inputs["context"]["official_scores_claimed"] is False
    assert len(inputs["round_proposals"]) == 5
    assert len(inputs["round_gate_results"]) == 5
    assert inputs["operators"] == [
        "tune.cv_stable_regularization",
        "refine.safe_recall_frontier",
        "adapt.arabic_normalization_surface",
        "combine.memory_guided_model_family_views",
        "audit.high_dev_score_risk",
    ]
    assert inputs["context"]["best_direction"]["submission_ready"] is False
    first_proposal = inputs["round_proposals"][0]["proposals"][0]
    for field in runner.REQUIRED_PROPOSAL_FIELDS:
        assert field in first_proposal
