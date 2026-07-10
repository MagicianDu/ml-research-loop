from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_runner_module():
    script = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "hf-evaluation"
        / "arguard-b1-p4-official-guided-method-search"
        / "run_arguard_b1_p4_official_guided_search.py"
    )
    spec = importlib.util.spec_from_file_location("arguard_b1_p4_runner", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_arguard_b1_p4_runner_builds_official_guided_method_search_inputs():
    runner = _load_runner_module()
    p4_payload = {
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
                    "proposal_id": "p4-threshold-safe-budget",
                    "operator_id": "refine.official_anchor_threshold",
                    "source": "official_guided_threshold_search",
                    "score": 0.929,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 50,
                        "safe_predicted_unsafe_count": 50,
                    },
                },
                "gate_result": {
                    "proposal_id": "p4-threshold-safe-budget",
                    "operator_id": "refine.official_anchor_threshold",
                    "status": "near_pass",
                    "score": 0.929,
                    "hard_blockers": [],
                },
            },
            {
                "round_number": 2,
                "proposal": {
                    "proposal_id": "p4-regularization-safe-budget",
                    "operator_id": "tune.official_anchor_regularization",
                    "source": "official_guided_logreg_search",
                    "score": 0.927,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 72,
                        "safe_predicted_unsafe_count": 40,
                    },
                },
                "gate_result": {
                    "proposal_id": "p4-regularization-safe-budget",
                    "operator_id": "tune.official_anchor_regularization",
                    "status": "blocked",
                    "score": 0.927,
                    "hard_blockers": ["local_score_regression"],
                },
            },
            {
                "round_number": 3,
                "proposal": {
                    "proposal_id": "p4-conservative-ensemble",
                    "operator_id": "combine.conservative_model_family_views",
                    "source": "official_guided_conservative_ensemble",
                    "score": 0.9305,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 48,
                        "safe_predicted_unsafe_count": 51,
                    },
                },
                "gate_result": {
                    "proposal_id": "p4-conservative-ensemble",
                    "operator_id": "combine.conservative_model_family_views",
                    "status": "passed",
                    "score": 0.9305,
                    "hard_blockers": [],
                },
            },
        ],
    }

    inputs = runner.build_method_search_inputs(p4_payload)

    assert inputs["context"]["official_result"]["submission_id"] == "819950"
    assert inputs["context"]["official_result"]["score"] == 0.93
    assert inputs["context"]["official_scores_claimed"] is False
    assert inputs["operators"] == [
        "refine.official_anchor_threshold",
        "tune.official_anchor_regularization",
        "combine.conservative_model_family_views",
    ]
    assert len(inputs["round_proposals"]) == 3
    assert len(inputs["round_gate_results"]) == 3
    first_proposal = inputs["round_proposals"][0]["proposals"][0]
    for field in runner.REQUIRED_PROPOSAL_FIELDS:
        assert field in first_proposal
    assert inputs["round_gate_results"][2]["gate_results"][0]["status"] == "passed"


def test_arguard_b1_p4_runner_accepts_raw_candidate_round_shape():
    runner = _load_runner_module()
    p4_payload = {
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
                    "trial_id": "p4-threshold-safe-budget",
                    "operator": "refine.official_anchor_threshold",
                    "source": "official_guided_threshold_search",
                    "change_surface": "P1 threshold",
                    "score": 0.929,
                    "threshold": 0.55,
                    "evaluation": {
                        "unsafe_predicted_safe_count": 50,
                        "safe_predicted_unsafe_count": 50,
                    },
                    "params": {"base_model": "p1-current-word-char-logreg"},
                },
                "gate_result": {
                    "proposal_id": "p4-threshold-safe-budget",
                    "operator_id": "refine.official_anchor_threshold",
                    "status": "near_pass",
                    "score": 0.929,
                    "hard_blockers": [],
                },
            }
        ],
    }

    inputs = runner.build_method_search_inputs(p4_payload)

    assert inputs["operators"] == ["refine.official_anchor_threshold"]
    proposal = inputs["round_proposals"][0]["proposals"][0]
    assert proposal["proposal_id"] == "p4-threshold-safe-budget"
    assert proposal["params"]["base_model"] == "p1-current-word-char-logreg"
