from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_runner_module():
    script = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "hf-evaluation"
        / "arguard-b1-p3-method-search-trajectory"
        / "run_arguard_b1_method_search_trajectory.py"
    )
    spec = importlib.util.spec_from_file_location("arguard_b1_p3_runner", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_arguard_b1_p3_runner_builds_three_round_method_search_inputs():
    runner = _load_runner_module()
    p2_payload = {
        "current_candidate": {
            "trial_id": "p1-current-word-char-logreg",
            "source": "p1_sklearn_logreg",
            "score": 0.9287139293764408,
            "evaluation": {
                "unsafe_predicted_safe_count": 69,
                "safe_predicted_unsafe_count": 42,
            },
        },
        "candidates": [
            {
                "trial_id": "p2-char25-c4-threshold",
                "source": "manual_sklearn_logreg",
                "operator": "adapt.character_robustness",
                "score": 0.9291814101165821,
                "evaluation": {
                    "unsafe_predicted_safe_count": 23,
                    "safe_predicted_unsafe_count": 80,
                },
            },
            {
                "trial_id": "p2-ensemble-char25-norm-cwnone",
                "source": "manual_probability_ensemble",
                "operator": "combine.model_family_views",
                "score": 0.929675891287558,
                "evaluation": {
                    "unsafe_predicted_safe_count": 65,
                    "safe_predicted_unsafe_count": 44,
                },
            },
            {
                "trial_id": "p2-ensemble-fasttext-char25-norm",
                "source": "manual_probability_ensemble",
                "operator": "combine.fasttext_and_linear_views",
                "score": 0.9311497862399345,
                "evaluation": {
                    "unsafe_predicted_safe_count": 27,
                    "safe_predicted_unsafe_count": 74,
                },
            },
        ],
        "cv_result": {
            "baseline_cv": {"macro_f1": 0.9207966793222916},
            "candidate_cv": {"macro_f1": 0.9124820844192818},
        },
        "submission_recommendation_gate": {
            "decision": "HOLD",
            "reasons": [
                "insufficient_local_score_delta",
                "cv_regression",
                "safe_false_positive_regression",
            ],
        },
    }

    inputs = runner.build_method_search_inputs(p2_payload)

    assert len(inputs["round_proposals"]) == 3
    assert len(inputs["round_gate_results"]) == 3
    assert inputs["round_gate_results"][0]["gate_results"][0]["status"] == "blocked"
    assert inputs["round_gate_results"][1]["gate_results"][0]["status"] == "near_pass"
    assert inputs["round_gate_results"][2]["gate_results"][0]["status"] == "blocked"
    assert inputs["round_gate_results"][2]["gate_results"][0]["hard_blockers"] == [
        "insufficient_local_score_delta",
        "cv_regression",
        "safe_false_positive_regression",
    ]
    assert inputs["operators"] == [
        "adapt.character_robustness",
        "combine.model_family_views",
        "combine.fasttext_and_linear_views",
    ]
    assert inputs["context"]["official_scores_claimed"] is False


def test_arguard_b1_p3_runner_renders_missing_winner_as_no_gate_winner():
    runner = _load_runner_module()

    assert runner.format_winner_id({"winner": None}) == "no_gate_winner"
