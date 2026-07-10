from lib.benchmarks.arguard_b1_search_gate import evaluate_submission_candidate_gate


def test_arguard_b1_submission_gate_blocks_dev_gain_when_robustness_regresses():
    gate = evaluate_submission_candidate_gate(
        candidate_id="threshold-dev-overfit",
        current_best_score=0.9287,
        candidate_score=0.936,
        current_cv_score=0.929,
        candidate_cv_score=0.921,
        current_unsafe_predicted_safe=69,
        candidate_unsafe_predicted_safe=75,
        current_safe_predicted_unsafe=42,
        candidate_safe_predicted_unsafe=74,
        remaining_total_submissions=8,
        min_score_delta=0.003,
        max_cv_regression=0.001,
        max_safe_false_positive_delta=10,
    )

    assert gate["decision"] == "HOLD"
    assert gate["recommended_for_codabench_submission"] is False
    assert gate["official_scores_claimed"] is False
    assert "cv_regression" in gate["reasons"]
    assert "unsafe_miss_regression" in gate["reasons"]
    assert "safe_false_positive_regression" in gate["reasons"]


def test_arguard_b1_submission_gate_recommends_only_robust_local_gain():
    gate = evaluate_submission_candidate_gate(
        candidate_id="robust-ensemble",
        current_best_score=0.9287,
        candidate_score=0.936,
        current_cv_score=0.912,
        candidate_cv_score=0.914,
        current_unsafe_predicted_safe=69,
        candidate_unsafe_predicted_safe=63,
        current_safe_predicted_unsafe=42,
        candidate_safe_predicted_unsafe=44,
        remaining_total_submissions=8,
        min_score_delta=0.003,
        max_cv_regression=0.001,
        max_safe_false_positive_delta=10,
    )

    assert gate["decision"] == "PASS"
    assert gate["recommended_for_codabench_submission"] is True
    assert gate["score_delta"] == 0.0073
    assert gate["official_scores_claimed"] is False
