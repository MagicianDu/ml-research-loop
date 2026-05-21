from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.proposal_memory import (
    proposal_reflection_to_memory_card,
    sync_proposal_reflection_to_store,
)
from lib.research_memory import ResearchMemoryStore


def _reflection_payload(
    tmp_path: Path,
    *,
    status: str,
    failure_labels: list[str] | None = None,
    recommended_next_action: str = "promote_candidate_if_canary_confirmed",
) -> dict:
    reflection_file = tmp_path / f"{status}-proposal-reflection.json"
    markdown_file = tmp_path / f"{status}-proposal-reflection.md"
    reflection_file.write_text("{}", encoding="utf-8")
    markdown_file.write_text("# Reflection\n", encoding="utf-8")
    return {
        "status": status,
        "proposal_id": f"round-{status}",
        "proposal": {
            "proposal_id": f"round-{status}",
            "hypothesis": "A bounded prompt profile change improves local SHIFT.",
            "change_surface": "prompt_profile",
            "change_spec": {
                "single_primary_variable": True,
                "target": "confidence_calibration_prompt",
            },
            "claim_boundary": "local diagnostic proposal only",
        },
        "evaluation": {
            "dev_delta": {"SHIFT": 0.7, "H": 0.0},
            "canary_delta": {"SHIFT": 0.2, "H": 0.0},
        },
        "failure_labels": failure_labels or [],
        "recommended_next_action": recommended_next_action,
        "memory_update_recommended": True,
        "reflection_file": str(reflection_file),
        "markdown_file": str(markdown_file),
        "official_scores_claimed": False,
        "claim_boundary": "proposal reflection only; not an official score claim",
    }


def test_candidate_supported_reflection_becomes_promoted_patch_card(
    tmp_path: Path,
) -> None:
    reflection = _reflection_payload(tmp_path, status="candidate_supported")

    card = proposal_reflection_to_memory_card(reflection)

    assert card.card_id == "proposal-reflection-round-candidate_supported"
    assert card.memory_type == "patch"
    assert card.promoted is True
    assert card.patch_type == "prompt_profile"
    assert card.failure_category is None
    assert card.official_scores_claimed is False
    assert "official_scores_claimed=false" in card.claim_boundary
    assert card.config["proposal_id"] == "round-candidate_supported"
    assert card.config["hypothesis"] == "A bounded prompt profile change improves local SHIFT."
    assert card.config["change_surface"] == "prompt_profile"
    assert card.config["failure_labels"] == []
    assert card.config["recommended_next_action"] == "promote_candidate_if_canary_confirmed"
    assert {artifact.name for artifact in card.artifact_refs} == {
        "proposal_reflection_json",
        "proposal_reflection_markdown",
    }


def test_reflection_memory_card_preserves_retrieval_fields(tmp_path: Path) -> None:
    reflection = _reflection_payload(tmp_path, status="candidate_supported")
    reflection.update(
        {
            "paper_ids": ["arxiv:1607.01759"],
            "datasets": ["AG News"],
            "model_family": "fastText",
            "metric_name": "P@1",
            "metric_before": 0.912,
            "metric_after": 0.921,
        }
    )

    card = proposal_reflection_to_memory_card(reflection)

    assert card.paper_ids == ["arxiv:1607.01759"]
    assert card.datasets == ["AG News"]
    assert card.model_family == "fastText"
    assert card.metric_name == "P@1"
    assert card.metric_before == 0.912
    assert card.metric_after == 0.921
    assert card.config["retrieval_fields"] == {
        "paper_ids": ["arxiv:1607.01759"],
        "datasets": ["AG News"],
        "model_family": "fastText",
        "metric_name": "P@1",
        "metric_before": 0.912,
        "metric_after": 0.921,
    }


def test_rollback_or_more_evidence_reflection_becomes_failure_card(
    tmp_path: Path,
) -> None:
    reflection = _reflection_payload(
        tmp_path,
        status="needs_rollback_or_more_evidence",
        failure_labels=["canary_not_confirmed", "regression_on_H"],
        recommended_next_action="rollback_or_keep_as_candidate",
    )

    card = proposal_reflection_to_memory_card(reflection)

    assert card.memory_type == "failure"
    assert card.promoted is False
    assert card.failure_category == "canary_not_confirmed"
    assert "needs_rollback_or_more_evidence" in card.tags
    assert "regression_on_H" in card.summary
    assert card.config["recommended_next_action"] == "rollback_or_keep_as_candidate"


def test_invalid_reflection_becomes_failure_card_without_executing_adapters(
    tmp_path: Path,
) -> None:
    reflection = _reflection_payload(
        tmp_path,
        status="invalid_proposal",
        failure_labels=["claim_boundary_forbidden"],
        recommended_next_action="revise_proposal_before_execution",
    )

    card = proposal_reflection_to_memory_card(reflection)

    assert card.memory_type == "failure"
    assert card.failure_category == "claim_boundary_forbidden"
    assert card.config["proposal_id"] == "round-invalid_proposal"
    assert card.config["change_spec"]["target"] == "confidence_calibration_prompt"
    assert card.config["evaluation"]["dev_delta"]["SHIFT"] == 0.7
    assert card.evidence_refs[0].source_id == "proposal_reflection:round-invalid_proposal"


def test_needs_promotion_evidence_reflection_becomes_candidate_memory(
    tmp_path: Path,
) -> None:
    reflection = _reflection_payload(
        tmp_path,
        status="needs_promotion_evidence",
        failure_labels=["promotion_gate_missing"],
        recommended_next_action="run_canary_or_holdout_before_promotion",
    )

    card = proposal_reflection_to_memory_card(reflection)

    assert card.memory_type == "failure"
    assert card.failure_category == "promotion_gate_missing"
    assert card.config["status"] == "needs_promotion_evidence"
    assert card.config["recommended_next_action"] == (
        "run_canary_or_holdout_before_promotion"
    )
    assert "needs_promotion_evidence" in card.tags


def test_sync_helper_appends_local_store_card_only(tmp_path: Path) -> None:
    reflection = _reflection_payload(tmp_path, status="candidate_supported")
    store = ResearchMemoryStore(tmp_path / "research-memory.jsonl")

    result = sync_proposal_reflection_to_store(reflection, store)

    cards = store.list_cards()
    assert result["status"] == "synced"
    assert result["card_id"] == "proposal-reflection-round-candidate_supported"
    assert result["executes_tool"] is False
    assert result["official_scores_claimed"] is False
    assert len(cards) == 1
    assert cards[0].config["proposal_id"] == "round-candidate_supported"


def test_reflection_file_path_can_be_loaded_before_card_conversion(
    tmp_path: Path,
) -> None:
    reflection = _reflection_payload(tmp_path, status="candidate_supported")
    reflection_path = tmp_path / "proposal-reflection.json"
    reflection_path.write_text(
        json.dumps(reflection, ensure_ascii=False),
        encoding="utf-8",
    )

    card = proposal_reflection_to_memory_card(reflection_path)

    assert card.config["proposal_id"] == "round-candidate_supported"


def test_unsupported_reflection_status_is_rejected(tmp_path: Path) -> None:
    reflection = _reflection_payload(tmp_path, status="unknown_status")

    with pytest.raises(ValueError, match="unsupported proposal reflection status"):
        proposal_reflection_to_memory_card(reflection)
