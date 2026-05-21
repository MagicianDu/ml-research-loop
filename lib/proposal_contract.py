from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "2026-05-21.proposal-contract.v1"
DEFAULT_CHANGE_SURFACES = [
    "prompt_profile",
    "routing",
    "decoding",
    "data",
    "training_recipe",
    "code_patch",
    "model_choice",
]
REQUIRED_PROPOSAL_FIELDS = [
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


def build_proposal_context(
    *,
    objective: str,
    output_dir: str | Path,
    baseline_report: str | Path | None = None,
    current_report: str | Path | None = None,
    dev_report: str | Path | None = None,
    canary_report: str | Path | None = None,
    category_deltas: str | Path | None = None,
    failure_samples: str | Path | None = None,
    rollback_summary: str | Path | None = None,
    previous_proposals: str | Path | None = None,
    memory_cards: str | Path | None = None,
    resource_constraints: dict[str, Any] | None = None,
    allowed_change_surfaces: list[str] | None = None,
    max_proposals: int = 3,
    overwrite: bool = False,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    allowed = allowed_change_surfaces or ["prompt_profile", "routing", "decoding"]
    payload: dict[str, Any] = {
        "status": "ready_for_client_proposal",
        "contract_version": CONTRACT_VERSION,
        "objective": objective,
        "allowed_change_surfaces": allowed,
        "max_proposals": max_proposals,
        "inputs": {
            "baseline_report": _artifact_payload(baseline_report),
            "current_report": _artifact_payload(current_report),
            "dev_report": _artifact_payload(dev_report),
            "canary_report": _artifact_payload(canary_report),
            "category_deltas": _artifact_payload(category_deltas),
            "failure_samples": _artifact_payload(failure_samples),
            "rollback_summary": _artifact_payload(rollback_summary),
            "previous_proposals": _artifact_payload(previous_proposals),
            "memory_cards": _artifact_payload(memory_cards),
            "resource_constraints": _inline_payload(resource_constraints),
        },
        "contract": proposal_contract_schema(allowed_change_surfaces=allowed),
        "prompt_markdown": "",
        "executes_tool": False,
        "official_scores_claimed": False,
        "claim_boundary": "client-side proposal planning only; MCP/evaluator must decide success",
    }
    payload["prompt_markdown"] = render_proposal_prompt(payload)
    return _write_context_payload(payload, output, overwrite=overwrite)


def write_proposal_context(**kwargs: Any) -> dict[str, Any]:
    return build_proposal_context(**kwargs)


def proposal_contract_schema(
    *,
    allowed_change_surfaces: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "version": CONTRACT_VERSION,
        "required_fields": list(REQUIRED_PROPOSAL_FIELDS),
        "allowed_change_surfaces": allowed_change_surfaces or list(DEFAULT_CHANGE_SURFACES),
        "rules": [
            "one primary variable per proposal",
            "do not claim official scores",
            "dev improvements require canary/holdout confirmation before promotion",
            "failed proposals and rollback reasons must be preserved",
        ],
    }


def validate_client_proposal(
    proposal: dict[str, Any],
    *,
    allowed_change_surfaces: list[str] | None = None,
) -> dict[str, Any]:
    allowed = allowed_change_surfaces or list(DEFAULT_CHANGE_SURFACES)
    missing = [field for field in REQUIRED_PROPOSAL_FIELDS if field not in proposal]
    labels: list[str] = []
    if missing:
        labels.append("missing_required_fields")
    if proposal.get("change_surface") not in allowed:
        labels.append("change_surface_not_allowed")
    if not _non_empty_string(proposal.get("proposal_id")):
        labels.append("invalid_proposal_id")
    if not _non_empty_string(proposal.get("hypothesis")):
        labels.append("invalid_hypothesis")
    if not _valid_evidence_used(proposal.get("evidence_used")):
        labels.append("invalid_evidence_used")
    change_spec = proposal.get("change_spec")
    if not isinstance(change_spec, dict) or change_spec.get("single_primary_variable") is not True:
        labels.append("not_single_primary_variable")
    if not _valid_expected_effect(proposal.get("expected_effect")):
        labels.append("invalid_expected_effect")
    validation_plan = proposal.get("validation_plan")
    if not _non_empty_dict(validation_plan):
        labels.append("invalid_validation_plan")
    else:
        if not _non_empty_string(validation_plan.get("first_split")):
            labels.append("validation_plan_missing_first_split")
        if not _promotion_gate(validation_plan):
            labels.append("validation_plan_missing_promotion_gate")
        if not _non_empty_list(validation_plan.get("rollback_if")):
            labels.append("validation_plan_missing_rollback")
    if not _valid_risk_assessment(proposal.get("risk_assessment")):
        labels.append("invalid_risk_assessment")
    if not _non_empty_string(proposal.get("next_if_success")):
        labels.append("invalid_next_if_success")
    if not _non_empty_string(proposal.get("next_if_failure")):
        labels.append("invalid_next_if_failure")
    claim_boundary = proposal.get("claim_boundary")
    if not _non_empty_string(claim_boundary):
        labels.append("invalid_claim_boundary")
    elif _forbidden_claim_boundary(str(claim_boundary)):
        labels.append("claim_boundary_forbidden")
    if proposal.get("official_scores_claimed") not in (None, False):
        labels.append("official_score_claim_forbidden")
    status = "accepted" if not labels else "rejected"
    return {
        "status": status,
        "contract_version": CONTRACT_VERSION,
        "failure_labels": labels,
        "missing_required_fields": missing,
        "allowed_change_surfaces": allowed,
        "normalized_proposal": dict(proposal),
        "executes_tool": False,
        "official_scores_claimed": False,
    }


def build_proposal_reflection(
    *,
    proposal: dict[str, Any],
    evaluation: dict[str, Any],
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    proposal_validation = validate_client_proposal(proposal)
    failure_labels = _failure_labels(evaluation)
    if proposal_validation["status"] != "accepted":
        failure_labels = list(proposal_validation["failure_labels"])
        status = "invalid_proposal"
        next_action = "revise_proposal_before_execution"
    elif not _has_evaluation_evidence(evaluation):
        failure_labels = ["missing_evaluation_evidence"]
        status = "insufficient_evidence"
        next_action = "collect_evaluator_feedback"
    elif failure_labels:
        status = "needs_rollback_or_more_evidence"
        next_action = "rollback_or_keep_as_candidate"
    elif not _has_promotion_gate(evaluation):
        failure_labels = ["promotion_gate_missing"]
        status = "needs_promotion_evidence"
        next_action = "run_canary_or_holdout_before_promotion"
    else:
        status = "candidate_supported"
        next_action = "promote_candidate_if_canary_confirmed"
    payload = {
        "status": status,
        "contract_version": CONTRACT_VERSION,
        "proposal_id": proposal.get("proposal_id"),
        "proposal": proposal,
        "proposal_validation": proposal_validation,
        "evaluation": evaluation,
        "failure_labels": failure_labels,
        "recommended_next_action": next_action,
        "memory_update_recommended": True,
        "executes_tool": False,
        "official_scores_claimed": False,
        "claim_boundary": "proposal reflection only; not an official score claim",
    }
    json_path = output / "proposal-reflection.json"
    md_path = output / "proposal-reflection.md"
    _assert_can_write(json_path, overwrite=overwrite)
    _assert_can_write(md_path, overwrite=overwrite)
    payload["reflection_file"] = str(json_path)
    payload["markdown_file"] = str(md_path)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(_reflection_markdown(payload), encoding="utf-8")
    return payload


def render_proposal_prompt(payload: dict[str, Any]) -> str:
    contract = payload["contract"]
    required = "\n".join(f"- {field}" for field in contract["required_fields"])
    surfaces = ", ".join(payload["allowed_change_surfaces"])
    provided_inputs = ", ".join(
        name
        for name, item in payload["inputs"].items()
        if isinstance(item, dict) and item.get("provided")
    ) or "none"
    return (
        "# Client Proposal Prompt\n\n"
        "You are Codex/Claude acting as a client-side research planner. "
        "Generate JSON proposals only; do not execute tools, call LLMs, run experiments, "
        "or claim official scores.\n\n"
        f"Objective: {payload['objective']}\n\n"
        f"Allowed change surfaces: {surfaces}\n\n"
        f"Maximum proposals: {payload['max_proposals']}\n\n"
        f"Provided artifacts: {provided_inputs}\n\n"
        "Required proposal fields:\n"
        f"{required}\n\n"
        "Each proposal must isolate one primary variable, cite the artifacts it used, "
        "define dev validation plus canary/holdout promotion logic, and preserve a "
        "local diagnostic claim boundary."
    )


def _artifact_payload(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {"provided": False, "path": None, "metrics": {}}
    artifact_path = Path(path)
    raw_text = artifact_path.read_text(encoding="utf-8")
    data = json.loads(raw_text)
    metrics = data.get("metrics", data) if isinstance(data, dict) else {}
    return {
        "provided": True,
        "path": str(artifact_path),
        "metrics": metrics if isinstance(metrics, dict) else {},
        "raw": data,
    }


def _inline_payload(data: dict[str, Any] | None) -> dict[str, Any]:
    if data is None:
        return {"provided": False, "path": None, "metrics": {}, "raw": {}}
    return {"provided": True, "path": None, "metrics": {}, "raw": dict(data)}


def _write_context_payload(
    payload: dict[str, Any],
    output: Path,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    json_path = output / "proposal-context.json"
    prompt_path = output / "proposal-prompt.md"
    _assert_can_write(json_path, overwrite=overwrite)
    _assert_can_write(prompt_path, overwrite=overwrite)
    payload["context_file"] = str(json_path)
    payload["prompt_file"] = str(prompt_path)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    prompt_path.write_text(payload["prompt_markdown"], encoding="utf-8")
    return payload


def _failure_labels(evaluation: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    rollback_reasons = evaluation.get("rollback_reasons", [])
    if isinstance(rollback_reasons, list):
        labels.extend(str(reason) for reason in rollback_reasons)
    if not labels:
        canary_delta = evaluation.get("canary_delta")
        if isinstance(canary_delta, dict) and canary_delta.get("SHIFT", 0) < 0:
            labels.append("canary_not_confirmed")
    if not labels:
        dev_delta = evaluation.get("dev_delta")
        if isinstance(dev_delta, dict) and dev_delta.get("SHIFT", 0) < 0:
            labels.append("metric_regression")
    return labels


def _has_evaluation_evidence(evaluation: dict[str, Any]) -> bool:
    return any(
        _non_empty_dict(evaluation.get(key))
        for key in ("dev_delta", "canary_delta", "holdout_delta", "external_delta", "metric_delta")
    ) or _non_empty_list(evaluation.get("rollback_reasons"))


def _has_promotion_gate(evaluation: dict[str, Any]) -> bool:
    if evaluation.get("promotion_gate_passed") is True:
        return True
    return any(
        _valid_metric_delta(evaluation.get(key))
        for key in ("canary_delta", "holdout_delta", "external_delta")
    )


def _assert_can_write(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(str(path))


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _non_empty_dict(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _valid_evidence_used(value: Any) -> bool:
    if not _non_empty_list(value):
        return False
    return all(
        isinstance(item, dict)
        and _non_empty_string(item.get("artifact"))
        and _non_empty_string(item.get("observation"))
        for item in value
    )


def _valid_expected_effect(value: Any) -> bool:
    if not _non_empty_dict(value):
        return False
    return _non_empty_string(value.get("primary_metric")) and _non_empty_string(
        value.get("expected_direction")
    )


def _valid_risk_assessment(value: Any) -> bool:
    if not _non_empty_dict(value):
        return False
    return any(_non_empty_string(item) for item in value.values())


def _valid_metric_delta(value: Any) -> bool:
    if not isinstance(value, dict) or not value:
        return False
    return any(isinstance(metric_value, (int, float)) for metric_value in value.values())


def _promotion_gate(validation_plan: dict[str, Any]) -> bool:
    return _non_empty_string(validation_plan.get("promotion_split")) or _non_empty_string(
        validation_plan.get("holdout_split")
    )


def _forbidden_claim_boundary(value: str) -> bool:
    lowered = value.lower()
    negated = any(
        marker in lowered
        for marker in (
            "no official",
            "not official",
            "not an official",
            "non-official",
            "without claiming official",
            "official_scores_claimed=false",
        )
    )
    if negated:
        return False
    return any(
        phrase in lowered
        for phrase in (
            "official score",
            "official leaderboard",
            "leaderboard score",
            "stable release",
            "release claim",
            "production ready",
        )
    )


def _reflection_markdown(payload: dict[str, Any]) -> str:
    labels = ", ".join(payload["failure_labels"]) or "none"
    return (
        "# Proposal Reflection\n\n"
        f"- Status: {payload['status']}\n"
        f"- Proposal ID: {payload.get('proposal_id')}\n"
        f"- Failure labels: {labels}\n"
        f"- Recommended next action: {payload['recommended_next_action']}\n"
        f"- Claim boundary: {payload['claim_boundary']}\n"
    )
