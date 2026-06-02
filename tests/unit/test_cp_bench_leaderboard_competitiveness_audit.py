from __future__ import annotations

from pathlib import Path

from scripts.cp_bench_leaderboard_competitiveness_audit import (
    build_leaderboard_competitiveness_audit,
)


def test_competitiveness_audit_computes_expected_rank_from_public_snapshot(
    tmp_path: Path,
) -> None:
    payload = build_leaderboard_competitiveness_audit(
        output_dir=tmp_path / "competitiveness",
        candidate_round={
            "status": "improved",
            "after_summary": {
                "submitted_models": 62,
                "runtime_success": "62/62",
                "coverage_percent": 98.41,
                "final_solution_accuracy_percent": 96.83,
            },
            "failure_summary": {
                "passed": 61,
                "failed": 1,
                "failed_problem_ids": ["csplib__csplib_021_crossfigures"],
            },
            "official_scores_claimed": False,
            "external_submission_status": "not_submitted",
        },
        public_watch={
            "public_verified_leaderboard_snapshot": {
                "entry_count": 3,
                "entries": [
                    {"name": "top", "final_solution_accuracy_percent": 100.0},
                    {"name": "second", "final_solution_accuracy_percent": 95.24},
                    {"name": "third", "final_solution_accuracy_percent": 93.65},
                ],
            }
        },
        source_label="CP-Bench P18 local candidate",
    )

    assert payload["status"] == "locally_competitive_for_manual_submission_review"
    assert payload["local_candidate"]["final_solution_accuracy_percent"] == 96.83
    assert payload["public_verified_leaderboard_snapshot"]["local_candidate_would_rank"] == 2
    assert payload["public_verified_leaderboard_snapshot"]["would_beat_public_entries"] == 2
    assert payload["decision"] == "prepare_manual_submission_gate"
    assert payload["official_scores_claimed"] is False
    assert payload["external_submission_status"] == "not_submitted"
    assert (tmp_path / "competitiveness" / "leaderboard-competitiveness-audit.json").exists()
