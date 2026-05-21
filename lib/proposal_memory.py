from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.research_memory import (
    MemoryArtifactRef,
    MemoryEvidenceRef,
    ResearchMemoryCard,
    ResearchMemoryStore,
)


SUPPORTED_REFLECTION_STATUSES = {
    "candidate_supported",
    "needs_promotion_evidence",
    "needs_rollback_or_more_evidence",
    "insufficient_evidence",
    "invalid_proposal",
}


def proposal_reflection_to_memory_card(
    reflection: dict[str, Any] | str | Path,
) -> ResearchMemoryCard:
    payload = _load_reflection_payload(reflection)
    status = _require_supported_status(payload)
    proposal = _dict_value(payload.get("proposal"))
    proposal_id = _string_value(payload.get("proposal_id")) or _string_value(
        proposal.get("proposal_id")
    )
    if not proposal_id:
        raise ValueError("proposal reflection requires proposal_id")

    failure_labels = _string_list(payload.get("failure_labels"))
    change_surface = _string_value(proposal.get("change_surface")) or "unknown"
    hypothesis = _string_value(proposal.get("hypothesis")) or "No hypothesis recorded."
    recommended_next_action = (
        _string_value(payload.get("recommended_next_action")) or "review_reflection"
    )
    artifact_refs = _artifact_refs(payload)
    retrieval_fields = _retrieval_fields(payload, proposal)

    return ResearchMemoryCard(
        card_id=f"proposal-reflection-{proposal_id}",
        memory_type="patch" if status == "candidate_supported" else "failure",
        task_family="proposal-reflection",
        summary=_summary(
            status=status,
            proposal_id=proposal_id,
            hypothesis=hypothesis,
            change_surface=change_surface,
            failure_labels=failure_labels,
            recommended_next_action=recommended_next_action,
        ),
        patch_type=change_surface,
        failure_category=failure_labels[0] if failure_labels else None,
        config={
            "proposal_id": proposal_id,
            "hypothesis": hypothesis,
            "change_surface": change_surface,
            "change_spec": _dict_value(proposal.get("change_spec")),
            "failure_labels": failure_labels,
            "recommended_next_action": recommended_next_action,
            "status": status,
            "evaluation": _dict_value(payload.get("evaluation")),
            "retrieval_fields": retrieval_fields,
        },
        paper_ids=retrieval_fields["paper_ids"],
        datasets=retrieval_fields["datasets"],
        model_family=retrieval_fields["model_family"],
        metric_name=retrieval_fields["metric_name"],
        metric_before=retrieval_fields["metric_before"],
        metric_after=retrieval_fields["metric_after"],
        evidence_refs=[
            MemoryEvidenceRef(
                source_id=f"proposal_reflection:{proposal_id}",
                artifact_path=_string_value(payload.get("reflection_file")),
                quote=f"{status}; next_action={recommended_next_action}",
                strength="proposal_reflection",
            )
        ],
        artifact_refs=artifact_refs,
        claim_boundary=(
            "local proposal reflection memory only; "
            "not public proof; official_scores_claimed=false"
        ),
        official_scores_claimed=False,
        promoted=status == "candidate_supported",
        tags=[
            "proposal-reflection",
            status,
            change_surface,
            recommended_next_action,
            *failure_labels,
        ],
    )


def sync_proposal_reflection_to_store(
    reflection: dict[str, Any] | str | Path,
    store: ResearchMemoryStore,
) -> dict[str, Any]:
    card = proposal_reflection_to_memory_card(reflection)
    store.append(card)
    return {
        "status": "synced",
        "card_id": card.card_id,
        "store": str(store.path),
        "executes_tool": False,
        "official_scores_claimed": False,
    }


def proposal_reflection_to_memory_payload(
    reflection: dict[str, Any] | str | Path,
) -> dict[str, Any]:
    return proposal_reflection_to_memory_card(reflection).to_dict()


def _load_reflection_payload(reflection: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(reflection, dict):
        return reflection
    path = Path(reflection)
    return json.loads(path.read_text(encoding="utf-8"))


def _require_supported_status(payload: dict[str, Any]) -> str:
    status = _string_value(payload.get("status"))
    if status not in SUPPORTED_REFLECTION_STATUSES:
        raise ValueError(f"unsupported proposal reflection status: {status}")
    if payload.get("official_scores_claimed") is not False:
        raise ValueError("proposal reflection memory requires official_scores_claimed=false")
    return status


def _artifact_refs(payload: dict[str, Any]) -> list[MemoryArtifactRef]:
    refs: list[MemoryArtifactRef] = []
    for name, key in (
        ("proposal_reflection_json", "reflection_file"),
        ("proposal_reflection_markdown", "markdown_file"),
    ):
        path = _string_value(payload.get(key))
        if path:
            refs.append(
                MemoryArtifactRef.from_path(
                    name,
                    path,
                    artifact_type="proposal_reflection",
                )
            )
    if not refs:
        raise ValueError("proposal reflection memory requires reflection artifact refs")
    return refs


def _summary(
    *,
    status: str,
    proposal_id: str,
    hypothesis: str,
    change_surface: str,
    failure_labels: list[str],
    recommended_next_action: str,
) -> str:
    labels = ", ".join(failure_labels) if failure_labels else "none"
    return (
        f"Proposal {proposal_id} reflection status={status}; "
        f"surface={change_surface}; hypothesis={hypothesis}; "
        f"failure_labels={labels}; next_action={recommended_next_action}."
    )


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _retrieval_fields(
    payload: dict[str, Any],
    proposal: dict[str, Any],
) -> dict[str, Any]:
    expected_effect = _dict_value(proposal.get("expected_effect"))
    evaluation = _dict_value(payload.get("evaluation"))
    metric_before = _float_value(payload.get("metric_before"))
    if metric_before is None:
        metric_before = _float_value(evaluation.get("metric_before"))
    metric_after = _float_value(payload.get("metric_after"))
    if metric_after is None:
        metric_after = _float_value(evaluation.get("metric_after"))
    return {
        "paper_ids": _string_list(payload.get("paper_ids"))
        or _string_list(proposal.get("paper_ids")),
        "datasets": _string_list(payload.get("datasets"))
        or _string_list(proposal.get("datasets")),
        "model_family": _string_value(payload.get("model_family"))
        or _string_value(proposal.get("model_family")),
        "metric_name": _string_value(payload.get("metric_name"))
        or _string_value(expected_effect.get("primary_metric"))
        or _string_value(evaluation.get("metric_name")),
        "metric_before": metric_before,
        "metric_after": metric_after,
    }


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _float_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None
