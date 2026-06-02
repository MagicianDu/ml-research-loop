from __future__ import annotations

import json
from pathlib import Path

from scripts.hf_promotion_path_audit import build_promotion_path_audit


def test_promotion_path_audit_keeps_unsubmitted_paths_unclaimable(tmp_path: Path) -> None:
    payload = build_promotion_path_audit(
        output_dir=tmp_path / "promotion-path",
        cp_readiness=_cp_readiness(),
        cp_public_watch=_cp_public_watch(target_result_exists=False),
        cp_competitiveness=_cp_competitiveness(),
        dcp_local_eval=_dcp_local_eval(),
        dcp_external_probe=_dcp_external_probe(),
    )

    assert payload["status"] == "not_promotable_yet"
    assert payload["real_leaderboard_result_claimable"] is False
    assert payload["official_scores_claimed"] is False
    assert payload["external_submission_status"] == "not_submitted"
    assert payload["recommended_next_action"] == (
        "request_explicit_human_approval_for_cp_bench_space_upload"
    )
    assert payload["paths"]["cp_bench"]["route_state"] == (
        "ready_for_explicit_upload_approval_not_uploaded"
    )
    assert payload["paths"]["cp_bench"]["promotional_strength"] == "entry_level_public_rank"
    assert payload["paths"]["dcp_bench_open"]["route_state"] == (
        "strong_local_eval_no_public_leaderboard_route"
    )
    assert payload["paths"]["dcp_bench_open"]["live_hf_public_entries"] == {
        "models": 0,
        "datasets": 0,
        "spaces": 0,
    }
    readme_text = (tmp_path / "promotion-path" / "README.md").read_text(encoding="utf-8")
    assert "不得宣传为官方榜单结果" in readme_text
    assert "request_explicit_human_approval_for_cp_bench_space_upload" in readme_text


def test_promotion_path_audit_routes_public_result_to_claim_review(tmp_path: Path) -> None:
    payload = build_promotion_path_audit(
        output_dir=tmp_path / "promotion-path",
        cp_readiness=_cp_readiness(),
        cp_public_watch=_cp_public_watch(target_result_exists=True),
        cp_competitiveness=_cp_competitiveness(),
        dcp_local_eval=_dcp_local_eval(),
        dcp_external_probe=_dcp_external_probe(),
    )

    assert payload["status"] == "public_result_available_for_claim_review"
    assert payload["real_leaderboard_result_claimable"] is True
    assert payload["recommended_next_action"] == (
        "verify_public_summary_and_prepare_bounded_promotional_claim"
    )
    assert payload["paths"]["cp_bench"]["route_state"] == "public_result_available"


def test_promotion_path_audit_writes_manifest_without_absolute_paths(tmp_path: Path) -> None:
    output_dir = tmp_path / "promotion-path"

    build_promotion_path_audit(
        output_dir=output_dir,
        cp_readiness=_cp_readiness(),
        cp_public_watch=_cp_public_watch(target_result_exists=False),
        cp_competitiveness=_cp_competitiveness(),
        dcp_local_eval=_dcp_local_eval(),
        dcp_external_probe=_dcp_external_probe(),
    )

    payload_text = (output_dir / "promotion-path-audit.json").read_text(encoding="utf-8")
    manifest = json.loads((output_dir / "artifact-manifest.json").read_text(encoding="utf-8"))

    assert str(tmp_path) not in payload_text
    assert manifest["official_scores_claimed"] is False
    assert manifest["external_submission_status"] == "not_submitted"
    assert (output_dir / "SHA256SUMS").exists()


def _cp_readiness() -> dict[str, object]:
    return {
        "status": "ready_for_explicit_public_upload_approval",
        "ready_for_public_upload_attempt": True,
        "claimable_public_result": False,
        "blockers": [],
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
    }


def _cp_public_watch(*, target_result_exists: bool) -> dict[str, object]:
    return {
        "status": "public_result_available" if target_result_exists else "waiting_for_public_result",
        "target_result_exists": target_result_exists,
        "claimable_public_result": target_result_exists,
        "external_submission_status": "submitted" if target_result_exists else "not_submitted",
        "official_scores_claimed": False,
        "target_result_path": "results/v1_verified/ml_research_loop_p17/summary.txt",
        "target_public_result": (
            {
                "public_rank": 17,
                "final_solution_accuracy_percent": 52.38,
                "summary_path": "results/v1_verified/ml_research_loop_p17/summary.txt",
            }
            if target_result_exists
            else None
        ),
        "public_verified_leaderboard_snapshot": {
            "entry_count": 17,
            "lowest_public_accuracy_percent": 46.03,
        },
    }


def _cp_competitiveness() -> dict[str, object]:
    return {
        "status": "locally_competitive_for_manual_submission_review",
        "target_is_archived_by_upstream": True,
        "upstream_successor": "DCP-Bench-Open",
        "local_candidate": {
            "final_solution_accuracy_percent": 52.38,
            "runtime_success": "34/34",
            "passed": 33,
            "failed": 1,
            "official_scores_claimed": False,
            "external_submission_status": "not_submitted",
        },
        "public_verified_leaderboard_snapshot": {
            "entry_count": 17,
            "local_candidate_would_rank": 17,
            "would_beat_public_entries": 1,
            "lowest_public_accuracy_percent": 46.03,
        },
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
    }


def _dcp_local_eval() -> dict[str, object]:
    return {
        "status": "written",
        "benchmark": "DCP-Bench-Open",
        "dcp_release": "v0.1.0",
        "dcp_problem_count": 164,
        "total_submitted_models": 128,
        "models_ran_successfully": 128,
        "models_ran_successfully_denominator": 128,
        "final_solution_accuracy_percent": 76.22,
        "submitted_solution_accuracy_percent": 97.66,
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
        "leaderboard_claimed": False,
    }


def _dcp_external_probe() -> dict[str, object]:
    return {
        "source_url": "https://huggingface.co/DCP-Bench-Open",
        "public_models": 0,
        "public_datasets": 0,
        "public_spaces": 0,
        "checked_at": "2026-06-02",
    }
