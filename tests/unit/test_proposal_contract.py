from __future__ import annotations

from pathlib import Path

import pytest

from lib.proposal_contract import (
    build_proposal_context,
    build_context_artifact_manifest,
    build_proposal_reflection,
    proposal_execution_plan,
    proposal_contract_schema,
    validate_client_proposal,
    write_proposal_context,
)
from lib.research_memory import (
    MemoryArtifactRef,
    MemoryEvidenceRef,
    ResearchMemoryCard,
    ResearchMemoryStore,
)


def _valid_proposal(proposal_id: str = "round-valid") -> dict:
    return {
        "proposal_id": proposal_id,
        "hypothesis": "A bounded prompt change can improve local diagnostic SHIFT.",
        "evidence_used": [{"artifact": "dev_report", "observation": "SHIFT has headroom"}],
        "change_surface": "prompt_profile",
        "change_spec": {
            "single_primary_variable": True,
            "target": "confidence_calibration_prompt",
        },
        "expected_effect": {"primary_metric": "SHIFT", "expected_direction": "increase"},
        "validation_plan": {
            "first_split": "dev",
            "promotion_split": "canary",
            "rollback_if": ["SHIFT_delta_lt_0"],
        },
        "risk_assessment": {"overfit_risk": "low"},
        "next_if_success": "promote_candidate_profile",
        "next_if_failure": "rollback_candidate",
        "claim_boundary": "local diagnostic proposal only",
    }


def test_build_proposal_context_writes_non_executing_contract(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    failure_samples = tmp_path / "failure-samples.json"
    baseline.write_text('{"SHIFT": 80.0, "H": 90.0, "failure_count": 12}', encoding="utf-8")
    current.write_text('{"SHIFT": 81.2, "H": 90.5, "failure_count": 10}', encoding="utf-8")
    failure_samples.write_text('[{"id": "case-1", "label": "overconfident"}]', encoding="utf-8")

    payload = build_proposal_context(
        objective="Improve local diagnostic SHIFT without hurting H.",
        output_dir=tmp_path / "proposal-context",
        baseline_report=baseline,
        current_report=current,
        failure_samples=failure_samples,
        resource_constraints={"max_rounds": 5, "local_model": "qwen3-8b"},
        allowed_change_surfaces=["prompt_profile", "routing"],
        max_proposals=3,
    )

    assert payload["status"] == "ready_for_client_proposal"
    assert payload["executes_tool"] is False
    assert payload["official_scores_claimed"] is False
    assert payload["contract"]["required_fields"] == [
        "proposal_id",
        "hypothesis",
        "evidence_used",
        "change_surface",
        "change_spec",
        "expected_effect",
        "validation_plan",
        "risk_assessment",
        "next_if_success",
        "next_if_failure",
        "claim_boundary",
    ]
    assert payload["inputs"]["baseline_report"]["metrics"]["SHIFT"] == 80.0
    assert payload["inputs"]["baseline_report"]["sha256"]
    assert payload["inputs"]["current_report"]["metrics"]["SHIFT"] == 81.2
    assert payload["inputs"]["failure_samples"]["raw"][0]["id"] == "case-1"
    assert payload["inputs"]["resource_constraints"]["raw"]["max_rounds"] == 5
    assert payload["artifact_manifest"]["provided_inputs"] == [
        "baseline_report",
        "current_report",
        "failure_samples",
        "resource_constraints",
    ]
    assert payload["artifact_manifest"]["artifacts"]["baseline_report"]["sha256"]
    assert payload["artifact_manifest"]["complete_for_p1"] is False
    assert payload["execution_plan"]["surface_tools"]["prompt_profile"] == [
        "run_smol_worldcup_proposal_round"
    ]
    assert "Codex/Claude" in payload["prompt_markdown"]
    assert "Missing artifacts to account for" in payload["prompt_markdown"]
    assert Path(payload["context_file"]).exists()
    assert Path(payload["prompt_file"]).exists()


def test_build_proposal_context_injects_memory_search_results(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "memory-artifact.json"
    artifact.write_text('{"stage": "proposal-reflection"}', encoding="utf-8")
    store = ResearchMemoryStore(tmp_path / "research-memory.jsonl")
    store.append(
        ResearchMemoryCard(
            card_id="proposal-reflection-fasttext-agnews",
            memory_type="patch",
            task_family="proposal-reflection",
            summary="fastText AG News prompt proposal improved local P@1.",
            paper_ids=["arxiv:1607.01759"],
            datasets=["AG News"],
            model_family="fastText",
            metric_name="P@1",
            metric_before=0.912,
            metric_after=0.921,
            patch_type="prompt_profile",
            config={"proposal_id": "round-fasttext"},
            evidence_refs=[
                MemoryEvidenceRef(
                    source_id="proposal_reflection:round-fasttext",
                    artifact_path=str(artifact),
                )
            ],
            artifact_refs=[MemoryArtifactRef.from_path("reflection", artifact)],
            claim_boundary="local proposal reflection memory only",
            official_scores_claimed=False,
            tags=["proposal-reflection", "fasttext"],
        )
    )

    payload = build_proposal_context(
        objective="Plan next fastText AG News proposal.",
        output_dir=tmp_path / "proposal-context",
        memory_store=store,
        memory_query={
            "query": "fastText proposal",
            "paper_id": "arxiv:1607.01759",
            "dataset": "AG News",
            "metric_name": "P@1",
            "patch_type": "prompt_profile",
        },
        memory_limit=1,
    )

    memory_input = payload["inputs"]["memory_cards"]
    assert memory_input["provided"] is True
    assert memory_input["path"] == str(store.path)
    assert memory_input["metrics"] == {"retrieved_count": 1}
    assert memory_input["raw"][0]["card"]["card_id"] == "proposal-reflection-fasttext-agnews"
    assert memory_input["raw"][0]["card"]["metric_before"] == 0.912
    assert memory_input["raw"][0]["card"]["metric_after"] == 0.921
    assert memory_input["raw"][0]["score"] > 0
    assert "memory_cards" in payload["prompt_markdown"]


def test_write_proposal_context_delegates_to_context_builder(tmp_path: Path) -> None:
    payload = write_proposal_context(
        objective="Build proposal only.",
        output_dir=tmp_path / "proposal-context",
        allowed_change_surfaces=["prompt_profile"],
    )

    assert payload["status"] == "ready_for_client_proposal"
    assert payload["allowed_change_surfaces"] == ["prompt_profile"]
    assert Path(payload["context_file"]).exists()


def test_proposal_contract_schema_lists_required_fields_and_rules() -> None:
    schema = proposal_contract_schema(allowed_change_surfaces=["prompt_profile"])

    assert schema["allowed_change_surfaces"] == ["prompt_profile"]
    assert schema["required_fields"][0] == "proposal_id"
    assert "do not claim official scores" in schema["rules"]
    assert "MCP validates" in schema["execution_boundary"]


def test_proposal_execution_plan_maps_allowed_surfaces_to_guarded_tools() -> None:
    plan = proposal_execution_plan(allowed_change_surfaces=["code_patch", "training_recipe"])

    assert plan["status"] == "ready"
    assert plan["surface_tools"]["code_patch"] == [
        "apply_client_code_patch",
        "run_client_patch_experiment",
    ]
    assert plan["surface_tools"]["training_recipe"] == [
        "run_client_patch_experiment",
        "run_next_experiment_from_review",
    ]
    assert "validate_client_proposal_contract" in plan["required_sequence"]
    assert plan["official_scores_claimed"] is False


def test_context_artifact_manifest_marks_complete_bundle() -> None:
    inputs = {
        name: {"provided": True, "path": None, "sha256": f"sha-{name}", "metrics": {"m": 1}}
        for name in (
            "baseline_report",
            "current_report",
            "dev_report",
            "canary_report",
            "category_deltas",
            "failure_samples",
            "rollback_summary",
            "previous_proposals",
            "memory_cards",
            "resource_constraints",
        )
    }

    manifest = build_context_artifact_manifest(inputs)

    assert manifest["complete_for_p1"] is True
    assert manifest["missing_inputs"] == []
    assert manifest["artifacts"]["dev_report"]["metric_keys"] == ["m"]


def test_validate_client_proposal_accepts_single_variable_contract() -> None:
    proposal = {
        "proposal_id": "round-005-confidence-v1",
        "hypothesis": "Tighter confidence wording will reduce overconfident wrong answers.",
        "evidence_used": [{"artifact": "current_report", "observation": "confidence errors"}],
        "change_surface": "prompt_profile",
        "change_spec": {
            "single_primary_variable": True,
            "target": "confidence_calibration_prompt",
            "allowed_scope": "one prompt block",
        },
        "expected_effect": {
            "primary_metric": "SHIFT",
            "target_categories": ["confidence_calibration"],
            "expected_direction": "increase",
        },
        "validation_plan": {
            "first_split": "dev",
            "promotion_split": "canary",
            "rollback_if": ["H_drop_gt_1", "SHIFT_delta_lt_0"],
        },
        "risk_assessment": {"overfit_risk": "medium", "leakage_risk": "low"},
        "next_if_success": "promote_candidate_profile",
        "next_if_failure": "rollback_candidate",
        "claim_boundary": "local diagnostic proposal only",
    }

    result = validate_client_proposal(
        proposal,
        allowed_change_surfaces=["prompt_profile", "routing"],
    )

    assert result["status"] == "accepted"
    assert result["executes_tool"] is False
    assert result["normalized_proposal"]["proposal_id"] == "round-005-confidence-v1"


def test_validate_client_proposal_rejects_weak_boundary_and_missing_gate() -> None:
    proposal = {
        "proposal_id": "round-005-bad",
        "hypothesis": "",
        "evidence_used": [],
        "change_surface": "prompt_profile",
        "change_spec": {"single_primary_variable": True},
        "expected_effect": {},
        "validation_plan": {"first_split": "dev"},
        "risk_assessment": {},
        "next_if_success": "ship",
        "next_if_failure": "ignore",
        "claim_boundary": "official leaderboard improvement",
        "official_scores_claimed": "true",
    }

    result = validate_client_proposal(
        proposal,
        allowed_change_surfaces=["prompt_profile"],
    )

    assert result["status"] == "rejected"
    assert "invalid_hypothesis" in result["failure_labels"]
    assert "invalid_evidence_used" in result["failure_labels"]
    assert "invalid_expected_effect" in result["failure_labels"]
    assert "validation_plan_missing_promotion_gate" in result["failure_labels"]
    assert "claim_boundary_forbidden" in result["failure_labels"]
    assert "official_score_claim_forbidden" in result["failure_labels"]


def test_validate_client_proposal_rejects_weak_structural_fields() -> None:
    proposal = {
        "proposal_id": "round-005-weak",
        "hypothesis": "Weak structure should fail.",
        "evidence_used": ["not an evidence object"],
        "change_surface": "prompt_profile",
        "change_spec": {"single_primary_variable": True},
        "expected_effect": {"primary_metric": ""},
        "validation_plan": {
            "promotion_split": "canary",
            "rollback_if": [],
            "max_rounds": 0,
        },
        "risk_assessment": {"overfit_risk": ""},
        "next_if_success": "",
        "next_if_failure": None,
        "claim_boundary": "local diagnostic proposal only",
    }

    result = validate_client_proposal(
        proposal,
        allowed_change_surfaces=["prompt_profile"],
    )

    assert result["status"] == "rejected"
    assert "invalid_evidence_used" in result["failure_labels"]
    assert "invalid_expected_effect" in result["failure_labels"]
    assert "validation_plan_missing_first_split" in result["failure_labels"]
    assert "validation_plan_missing_rollback" in result["failure_labels"]
    assert "invalid_max_rounds" in result["failure_labels"]
    assert "invalid_risk_assessment" in result["failure_labels"]
    assert "invalid_next_if_success" in result["failure_labels"]
    assert "invalid_next_if_failure" in result["failure_labels"]


def test_validate_client_proposal_rejects_boolean_max_rounds() -> None:
    proposal = _valid_proposal("round-bool-max-rounds")
    proposal["validation_plan"]["max_rounds"] = True

    result = validate_client_proposal(
        proposal,
        allowed_change_surfaces=["prompt_profile"],
    )

    assert result["status"] == "rejected"
    assert "invalid_max_rounds" in result["failure_labels"]


def test_validate_client_proposal_rejects_missing_fields_and_broad_change() -> None:
    result = validate_client_proposal(
        {
            "proposal_id": "bad",
            "hypothesis": "Change many things.",
            "change_surface": "training_recipe",
            "change_spec": {"single_primary_variable": False},
        },
        allowed_change_surfaces=["prompt_profile"],
    )

    assert result["status"] == "rejected"
    assert "missing_required_fields" in result["failure_labels"]
    assert "change_surface_not_allowed" in result["failure_labels"]
    assert "not_single_primary_variable" in result["failure_labels"]


def test_build_proposal_reflection_requires_evaluator_evidence(tmp_path: Path) -> None:
    reflection = build_proposal_reflection(
        proposal=_valid_proposal("round-empty"),
        evaluation={},
        output_dir=tmp_path / "reflection",
    )

    assert reflection["status"] == "insufficient_evidence"
    assert reflection["failure_labels"] == ["missing_evaluation_evidence"]
    assert reflection["recommended_next_action"] == "collect_evaluator_feedback"


def test_build_proposal_reflection_requires_promotion_gate_for_support(
    tmp_path: Path,
) -> None:
    reflection = build_proposal_reflection(
        proposal=_valid_proposal("round-dev-only"),
        evaluation={"dev_delta": {"SHIFT": 1.0, "H": 0.0, "failure_count": 0}},
        output_dir=tmp_path / "reflection",
    )

    assert reflection["status"] == "needs_promotion_evidence"
    assert reflection["failure_labels"] == ["promotion_gate_missing"]
    assert reflection["recommended_next_action"] == "run_canary_or_holdout_before_promotion"


def test_build_proposal_reflection_rejects_empty_promotion_delta(
    tmp_path: Path,
) -> None:
    reflection = build_proposal_reflection(
        proposal=_valid_proposal("round-empty-canary"),
        evaluation={"canary_delta": {}},
        output_dir=tmp_path / "reflection",
    )

    assert reflection["status"] == "insufficient_evidence"
    assert reflection["failure_labels"] == ["missing_evaluation_evidence"]


def test_build_proposal_reflection_rejects_invalid_proposal_claims(
    tmp_path: Path,
) -> None:
    proposal = {
        "proposal_id": "round-bad-claim",
        "hypothesis": "Bad claim.",
        "evidence_used": [{"artifact": "dev", "observation": "delta"}],
        "change_surface": "prompt_profile",
        "change_spec": {"single_primary_variable": True},
        "expected_effect": {"primary_metric": "SHIFT", "expected_direction": "increase"},
        "validation_plan": {
            "first_split": "dev",
            "promotion_split": "canary",
            "rollback_if": ["SHIFT_delta_lt_0"],
        },
        "risk_assessment": {"overfit_risk": "low"},
        "next_if_success": "promote_candidate_profile",
        "next_if_failure": "rollback_candidate",
        "claim_boundary": "official leaderboard improvement",
    }

    reflection = build_proposal_reflection(
        proposal=proposal,
        evaluation={"canary_delta": {"SHIFT": 0.2}},
        output_dir=tmp_path / "reflection",
    )

    assert reflection["status"] == "invalid_proposal"
    assert "claim_boundary_forbidden" in reflection["failure_labels"]
    assert reflection["recommended_next_action"] == "revise_proposal_before_execution"


def test_build_proposal_reflection_labels_canary_failure(tmp_path: Path) -> None:
    proposal = _valid_proposal("round-006-semantic-v2")
    evaluation = {
        "dev_delta": {"SHIFT": 0.9, "H": 0.0, "failure_count": 1},
        "canary_delta": {"SHIFT": -0.3, "H": 0.0, "failure_count": -1},
        "rollback_reasons": ["canary_not_confirmed"],
    }

    reflection = build_proposal_reflection(
        proposal=proposal,
        evaluation=evaluation,
        output_dir=tmp_path / "reflection",
    )

    assert reflection["status"] == "needs_rollback_or_more_evidence"
    assert reflection["failure_labels"] == ["canary_not_confirmed"]
    assert reflection["recommended_next_action"] == "rollback_or_keep_as_candidate"
    assert reflection["memory_update_recommended"] is True
    assert Path(reflection["reflection_file"]).exists()


def test_proposal_artifacts_refuse_to_overwrite_by_default(tmp_path: Path) -> None:
    output_dir = tmp_path / "proposal-context"
    build_proposal_context(
        objective="First context",
        output_dir=output_dir,
    )

    with pytest.raises(FileExistsError):
        build_proposal_context(
            objective="Second context",
            output_dir=output_dir,
        )
