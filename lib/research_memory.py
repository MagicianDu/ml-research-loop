from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


MemoryType = Literal["evidence", "experiment", "patch", "failure", "procedure"]
REDACTED = "[REDACTED]"
REDACTED_PRIVATE_SUMMARY = "[REDACTED PRIVATE MEMORY]"


def _now() -> float:
    return time.time()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class MemoryEvidenceRef:
    source_id: str
    artifact_path: str | None = None
    quote: str | None = None
    strength: str = "runtime_artifact"
    url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> MemoryEvidenceRef:
        return cls(**payload)


@dataclass(frozen=True)
class MemoryArtifactRef:
    name: str
    path: str
    sha256: str
    artifact_type: str = "runtime_artifact"

    @classmethod
    def from_path(
        cls,
        name: str,
        path: str | Path,
        artifact_type: str = "runtime_artifact",
    ) -> MemoryArtifactRef:
        resolved = Path(path)
        return cls(
            name=name,
            path=str(resolved),
            sha256=_sha256(resolved),
            artifact_type=artifact_type,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> MemoryArtifactRef:
        return cls(**payload)


@dataclass(frozen=True)
class ResearchMemoryCard:
    card_id: str
    memory_type: MemoryType
    task_family: str
    summary: str
    paper_ids: list[str] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    model_family: str | None = None
    metric_name: str | None = None
    metric_before: float | None = None
    metric_after: float | None = None
    patch_type: str | None = None
    failure_category: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[MemoryEvidenceRef] = field(default_factory=list)
    artifact_refs: list[MemoryArtifactRef] = field(default_factory=list)
    claim_boundary: str = "local memory only; not public proof"
    official_scores_claimed: bool = False
    privacy_scope: str = "public"
    allow_private_ingestion: bool = False
    promoted: bool = False
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=_now)

    def __post_init__(self) -> None:
        if self.privacy_scope != "public" and not self.allow_private_ingestion:
            raise ValueError("private memory ingestion requires explicit opt-in")
        if self.official_scores_claimed:
            raise ValueError("memory cards must not claim official scores")
        if not self.artifact_refs and self.memory_type != "procedure":
            raise ValueError("non-procedure memory cards require artifact_refs")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_refs"] = [item.to_dict() for item in self.evidence_refs]
        payload["artifact_refs"] = [item.to_dict() for item in self.artifact_refs]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ResearchMemoryCard:
        data = dict(payload)
        data["evidence_refs"] = [
            MemoryEvidenceRef.from_dict(item) for item in data.get("evidence_refs", [])
        ]
        data["artifact_refs"] = [
            MemoryArtifactRef.from_dict(item) for item in data.get("artifact_refs", [])
        ]
        return cls(**data)


@dataclass(frozen=True)
class MemorySearchResult:
    card: ResearchMemoryCard
    score: float
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "card": self.card.to_dict(),
            "score": self.score,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class MemorySuggestion:
    suggestion_id: str
    summary: str
    recommended_mcp_tool: str | None
    recommended_human_action: str | None
    confidence: float
    provenance: list[dict[str, Any]]
    known_failures: list[str]
    claim_boundary: str
    executes_tool: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryTrace:
    trace_id: str
    cards: list[ResearchMemoryCard]
    artifact_refs: list[MemoryArtifactRef]
    claim_boundaries: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "cards": [card.to_dict() for card in self.cards],
            "artifact_refs": [artifact.to_dict() for artifact in self.artifact_refs],
            "claim_boundaries": list(self.claim_boundaries),
        }


class ResearchMemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, card: ResearchMemoryCard) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(card.to_dict(), ensure_ascii=False, sort_keys=True) + "\n"
            )

    def list_cards(self) -> list[ResearchMemoryCard]:
        if not self.path.exists():
            return []
        cards: list[ResearchMemoryCard] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cards.append(ResearchMemoryCard.from_dict(json.loads(line)))
        return cards

    def export_cards(
        self,
        output_path: str | Path,
        *,
        include_private: bool = False,
    ) -> dict[str, Any]:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        redacted_count = 0
        exported_payloads: list[dict[str, Any]] = []
        for card in self.list_cards():
            if card.privacy_scope != "public" and not include_private:
                redacted_count += 1
                exported_payloads.append(redact_memory_card(card))
            else:
                exported_payloads.append(card.to_dict())
        with output.open("w", encoding="utf-8") as handle:
            for payload in exported_payloads:
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return {
            "status": "exported",
            "path": str(output),
            "exported_count": len(exported_payloads),
            "redacted_count": redacted_count,
            "include_private": include_private,
        }

    def import_cards(
        self,
        input_path: str | Path,
        *,
        allow_private: bool = False,
    ) -> dict[str, Any]:
        source = Path(input_path)
        imported_count = 0
        for line in source.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload.get("privacy_scope") != "public" and not allow_private:
                raise ValueError("private memory import requires allow_private=True")
            card = ResearchMemoryCard.from_dict(payload)
            self.append(card)
            imported_count += 1
        return {
            "status": "imported",
            "path": str(source),
            "imported_count": imported_count,
            "allow_private": allow_private,
        }

    def search(
        self,
        *,
        query: str | None = None,
        paper_id: str | None = None,
        dataset: str | None = None,
        metric_name: str | None = None,
        patch_type: str | None = None,
        failure_category: str | None = None,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        results: list[MemorySearchResult] = []
        query_terms = {term.lower() for term in (query or "").split() if term.strip()}
        for card in self.list_cards():
            score = 0.0
            reasons: list[str] = []
            haystack = " ".join(
                [
                    card.summary,
                    card.task_family,
                    card.model_family or "",
                    " ".join(card.paper_ids),
                    " ".join(card.datasets),
                    " ".join(card.tags),
                ]
            ).lower()
            if query_terms:
                overlap = sum(1 for term in query_terms if term in haystack)
                if overlap:
                    score += overlap
                    reasons.append("query")
            if paper_id and paper_id in card.paper_ids:
                score += 3
                reasons.append("paper_id")
            if dataset and dataset in card.datasets:
                score += 2
                reasons.append("dataset")
            if metric_name and metric_name == card.metric_name:
                score += 1.5
                reasons.append("metric_name")
            if patch_type and patch_type == card.patch_type:
                score += 1
                reasons.append("patch_type")
            if failure_category and failure_category == card.failure_category:
                score += 1
                reasons.append("failure_category")
            if score > 0:
                results.append(
                    MemorySearchResult(card=card, score=score, reasons=reasons)
                )
        return sorted(results, key=lambda item: item.score, reverse=True)[:limit]

    def suggest(
        self,
        *,
        query: str,
        paper_id: str | None = None,
        dataset: str | None = None,
        limit: int = 5,
    ) -> list[MemorySuggestion]:
        suggestions: list[MemorySuggestion] = []
        for result in self.search(
            query=query,
            paper_id=paper_id,
            dataset=dataset,
            limit=limit,
        ):
            card = result.card
            recommended_tool = None
            if card.memory_type == "patch":
                recommended_tool = "run_client_patch_experiment"
            elif card.memory_type == "failure":
                recommended_tool = "get_experiment_logs"
            confidence = min(0.95, 0.35 + result.score / 10)
            suggestions.append(
                MemorySuggestion(
                    suggestion_id=f"suggest-{card.card_id}",
                    summary=card.summary,
                    recommended_mcp_tool=recommended_tool,
                    recommended_human_action=(
                        None if recommended_tool else "review_memory_card"
                    ),
                    confidence=confidence,
                    provenance=[{"card_id": card.card_id, "reasons": result.reasons}],
                    known_failures=[card.failure_category]
                    if card.failure_category
                    else [],
                    claim_boundary=card.claim_boundary,
                    executes_tool=False,
                )
            )
        return suggestions

    def audit_trace(self, card_ids: list[str]) -> MemoryTrace:
        cards_by_id = {card.card_id: card for card in self.list_cards()}
        cards = [cards_by_id[card_id] for card_id in card_ids if card_id in cards_by_id]
        artifact_refs: list[MemoryArtifactRef] = []
        claim_boundaries: list[str] = []
        for card in cards:
            artifact_refs.extend(card.artifact_refs)
            claim_boundaries.append(card.claim_boundary)
        return MemoryTrace(
            trace_id=f"trace-{len(cards)}",
            cards=cards,
            artifact_refs=artifact_refs,
            claim_boundaries=claim_boundaries,
        )


def redact_memory_card(card: ResearchMemoryCard) -> dict[str, Any]:
    payload = card.to_dict()
    payload["summary"] = REDACTED_PRIVATE_SUMMARY
    payload["privacy_scope"] = "public"
    payload["allow_private_ingestion"] = False
    payload["config"] = {}
    payload["evidence_refs"] = [
        {
            **item,
            "artifact_path": REDACTED if item.get("artifact_path") else None,
            "quote": REDACTED if item.get("quote") else None,
            "url": REDACTED if item.get("url") else None,
        }
        for item in payload.get("evidence_refs", [])
    ]
    payload["artifact_refs"] = [
        {
            **item,
            "path": REDACTED,
            "sha256": REDACTED,
        }
        for item in payload.get("artifact_refs", [])
    ]
    tags = set(payload.get("tags", []))
    tags.add("redacted_private")
    payload["tags"] = sorted(tags)
    payload["claim_boundary"] = (
        f"{card.claim_boundary}; private details redacted for export"
    )
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_fasttext_release_manifest(
    manifest: dict[str, Any],
    review_text: str,
) -> None:
    stage = manifest.get("stage")
    if stage != "p5_fasttext_release_proof_bundle":
        raise ValueError(
            "fastText memory extraction requires "
            "stage=p5_fasttext_release_proof_bundle"
        )
    if manifest.get("status") != "completed":
        raise ValueError("fastText memory extraction requires completed release status")
    if manifest.get("official_scores_claimed") is not False:
        raise ValueError("fastText memory extraction requires official_scores_claimed=false")
    p4_summary = manifest.get("p4_summary")
    review_status = (
        p4_summary.get("review_status") if isinstance(p4_summary, dict) else None
    )
    if review_status != "approved_with_limitations":
        raise ValueError(
            "fastText memory extraction requires "
            "p4_summary.review_status=approved_with_limitations"
        )
    if "approved_with_limitations" not in review_text:
        raise ValueError(
            "fastText memory extraction requires review checklist "
            "to contain approved_with_limitations"
        )


def _require_fasttext_multi_round_report(multi_round: dict[str, Any]) -> None:
    if multi_round.get("stage") != "p5_fasttext_multi_proposal_loop":
        raise ValueError(
            "fastText memory extraction requires "
            "stage=p5_fasttext_multi_proposal_loop"
        )
    if multi_round.get("official_scores_claimed") is not False:
        raise ValueError("fastText memory extraction requires official_scores_claimed=false")


def _nested_value(payload: dict[str, Any], *keys: str) -> Any | None:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first_float(field_name: str, *values: Any) -> float:
    for value in values:
        if value is not None:
            return float(value)
    raise ValueError(f"fastText memory extraction requires {field_name}")


def _first_value(*values: Any) -> Any | None:
    for value in values:
        if value is not None:
            return value
    return None


def extract_fasttext_release_memory_cards(
    *,
    release_manifest: str | Path,
    multi_round_report: str | Path,
    review_checklist: str | Path,
) -> list[ResearchMemoryCard]:
    manifest_path = Path(release_manifest)
    multi_round_path = Path(multi_round_report)
    review_path = Path(review_checklist)
    manifest = _read_json(manifest_path)
    multi_round = _read_json(multi_round_path)
    review_text = review_path.read_text(encoding="utf-8")
    _require_fasttext_release_manifest(manifest, review_text)
    _require_fasttext_multi_round_report(multi_round)
    paper_id = str(
        _first_value(
            multi_round.get("paper_id"),
            _nested_value(multi_round, "paper_reference", "paper_id"),
            "arxiv:1607.01759",
        )
    )
    baseline = _first_float(
        "baseline_p_at_1",
        multi_round.get("baseline_p_at_1"),
        _nested_value(multi_round, "baseline", "p_at_1"),
        _nested_value(manifest, "p4_summary", "metric_summary", "baseline_p_at_1"),
    )
    best = _first_float(
        "best_metric",
        multi_round.get("best_metric"),
        _nested_value(multi_round, "summary", "best_metric"),
        _nested_value(multi_round, "rollback_summary", "best_metric"),
        _nested_value(manifest, "multi_round_summary", "best_metric"),
    )
    if best <= baseline:
        raise ValueError(
            "fastText memory extraction requires best_metric > baseline_p_at_1"
        )
    best_source = _first_value(
        multi_round.get("best_source"),
        _nested_value(multi_round, "summary", "best_source"),
        _nested_value(multi_round, "rollback_summary", "best_source"),
        _nested_value(manifest, "multi_round_summary", "best_source"),
    )
    failure_count = _first_value(
        multi_round.get("failure_count"),
        _nested_value(multi_round, "summary", "failure_count"),
        _nested_value(manifest, "multi_round_summary", "failure_count"),
        0,
    )
    common_artifacts = [
        MemoryArtifactRef.from_path("release_manifest", manifest_path),
        MemoryArtifactRef.from_path("multi_round_report", multi_round_path),
        MemoryArtifactRef.from_path("review_checklist", review_path),
    ]
    safe_paper_id = paper_id.replace(":", "-")
    patch_card = ResearchMemoryCard(
        card_id=f"mem-fasttext-{safe_paper_id}-best-patch",
        memory_type="patch",
        task_family="text-classification",
        summary="fastText AG News bounded client proposal improved local P@1.",
        paper_ids=[paper_id],
        datasets=["AG News"],
        model_family="fastText",
        metric_name="P@1",
        metric_before=baseline,
        metric_after=best,
        patch_type="hyperparameter",
        config={"best_source": best_source},
        evidence_refs=[
            MemoryEvidenceRef(
                source_id="fasttext-release-proof",
                artifact_path=str(manifest_path),
                quote="Local release proof bundle; not a leaderboard score.",
            )
        ],
        artifact_refs=common_artifacts,
        claim_boundary="local fastText proof only; official_scores_claimed=false",
        official_scores_claimed=False,
        tags=["fasttext", "ag-news", "patch", "proof"],
    )
    failure_card = ResearchMemoryCard(
        card_id=f"mem-fasttext-{safe_paper_id}-failed-proposals",
        memory_type="failure",
        task_family="text-classification",
        summary=(
            "fastText multi-proposal loop preserved failed or rejected proposals "
            "and rollback state."
        ),
        paper_ids=[paper_id],
        datasets=["AG News"],
        model_family="fastText",
        metric_name="P@1",
        failure_category="invalid_or_failed_proposal",
        config={
            "failure_count": failure_count,
            "rollback_summary": multi_round.get("rollback_summary", {}),
        },
        evidence_refs=[
            MemoryEvidenceRef(
                source_id="fasttext-multi-round-report",
                artifact_path=str(multi_round_path),
                quote="Failed proposal records are audit evidence.",
            )
        ],
        artifact_refs=common_artifacts,
        claim_boundary="failure/rollback audit memory only",
        official_scores_claimed=False,
        tags=["fasttext", "ag-news", "failure", "rollback"],
    )
    return [patch_card, failure_card]
