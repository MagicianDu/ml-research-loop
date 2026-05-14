from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.research_memory import (
    MemoryArtifactRef,
    MemoryEvidenceRef,
    ResearchMemoryCard,
    ResearchMemoryStore,
)


def test_memory_card_round_trips_with_artifact_provenance(tmp_path: Path) -> None:
    artifact = tmp_path / "improvement-report.json"
    artifact.write_text('{"p_at_1": 0.916}', encoding="utf-8")
    card = ResearchMemoryCard(
        card_id="mem-fasttext-wordngrams-2",
        memory_type="patch",
        task_family="text-classification",
        summary="fastText AG News wordNgrams=2 improved local P@1.",
        paper_ids=["arxiv:1607.01759"],
        datasets=["AG News"],
        model_family="fastText",
        metric_name="P@1",
        metric_before=0.914,
        metric_after=0.916,
        patch_type="hyperparameter",
        config={"wordNgrams": 2},
        evidence_refs=[
            MemoryEvidenceRef(
                source_id="fasttext-p5-release",
                quote="Local proof only; not a leaderboard score.",
                strength="runtime_artifact",
            )
        ],
        artifact_refs=[MemoryArtifactRef.from_path("improvement_report", artifact)],
        claim_boundary="local proof only; official_scores_claimed=false",
        official_scores_claimed=False,
        tags=["fasttext", "ag-news", "patch"],
    )

    payload = card.to_dict()
    restored = ResearchMemoryCard.from_dict(payload)

    assert restored.card_id == "mem-fasttext-wordngrams-2"
    assert restored.artifact_refs[0].sha256
    assert restored.official_scores_claimed is False
    assert restored.metric_after == 0.916


def test_store_appends_and_searches_cards(tmp_path: Path) -> None:
    artifact = tmp_path / "proof-manifest.json"
    artifact.write_text(json.dumps({"official_scores_claimed": False}), encoding="utf-8")
    store = ResearchMemoryStore(tmp_path / "memory.jsonl")
    card = ResearchMemoryCard(
        card_id="mem-fasttext-proof",
        memory_type="evidence",
        task_family="text-classification",
        summary="fastText AG News release proof bundle was reviewed with limitations.",
        paper_ids=["arxiv:1607.01759"],
        datasets=["AG News"],
        model_family="fastText",
        metric_name="P@1",
        artifact_refs=[MemoryArtifactRef.from_path("proof_manifest", artifact)],
        claim_boundary="reviewed local release proof bundle only",
        official_scores_claimed=False,
        tags=["proof", "release", "ag-news"],
    )

    store.append(card)
    matches = store.search(query="AG News proof", paper_id="arxiv:1607.01759")

    assert [match.card.card_id for match in matches] == ["mem-fasttext-proof"]
    assert matches[0].score > 0
    assert "paper_id" in matches[0].reasons


def test_memory_card_rejects_private_material_without_opt_in(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "private-log.txt"
    artifact.write_text("private user dataset path", encoding="utf-8")

    with pytest.raises(ValueError, match="private"):
        ResearchMemoryCard(
            card_id="mem-private",
            memory_type="failure",
            task_family="private-task",
            summary="Private run failed.",
            artifact_refs=[MemoryArtifactRef.from_path("log", artifact)],
            privacy_scope="private",
            allow_private_ingestion=False,
        )


def test_extract_fasttext_release_memory_cards(tmp_path: Path) -> None:
    proof_dir = tmp_path / "release-proof"
    proof_dir.mkdir()
    manifest = proof_dir / "release-proof-manifest.json"
    review = proof_dir / "release-review-checklist.md"
    multi_round = proof_dir / "multi-round-report.json"
    manifest.write_text(
        json.dumps(
            {
                "official_scores_claimed": False,
                "bundle_sha256": "abc123",
                "stage": "p5_fasttext_release_proof_bundle",
            }
        ),
        encoding="utf-8",
    )
    review.write_text("approved_with_limitations", encoding="utf-8")
    multi_round.write_text(
        json.dumps(
            {
                "paper_id": "arxiv:1607.01759",
                "baseline_p_at_1": 0.914,
                "best_metric": 0.916,
                "best_source": "round-001-wordngrams-2",
                "failure_count": 1,
                "rollback_summary": {"rollback_events": 1},
            }
        ),
        encoding="utf-8",
    )

    from lib.research_memory import extract_fasttext_release_memory_cards

    cards = extract_fasttext_release_memory_cards(
        release_manifest=manifest,
        multi_round_report=multi_round,
        review_checklist=review,
    )

    assert [card.memory_type for card in cards] == ["patch", "failure"]
    assert cards[0].paper_ids == ["arxiv:1607.01759"]
    assert cards[0].datasets == ["AG News"]
    assert cards[0].metric_before == 0.914
    assert cards[0].metric_after == 0.916
    assert cards[0].official_scores_claimed is False
    assert cards[1].failure_category == "invalid_or_failed_proposal"


def test_suggest_from_memory_includes_provenance_and_no_execution(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "multi-round-report.json"
    artifact.write_text(json.dumps({"best_metric": 0.916}), encoding="utf-8")
    store = ResearchMemoryStore(tmp_path / "memory.jsonl")
    store.append(
        ResearchMemoryCard(
            card_id="mem-fasttext-wordngrams",
            memory_type="patch",
            task_family="text-classification",
            summary="wordNgrams=2 improved local fastText AG News P@1.",
            paper_ids=["arxiv:1607.01759"],
            datasets=["AG News"],
            model_family="fastText",
            metric_name="P@1",
            metric_before=0.914,
            metric_after=0.916,
            patch_type="hyperparameter",
            artifact_refs=[MemoryArtifactRef.from_path("multi_round_report", artifact)],
            claim_boundary="local proof only",
            tags=["wordNgrams"],
        )
    )

    suggestions = store.suggest(
        query="fastText AG News improve P@1",
        paper_id="arxiv:1607.01759",
        dataset="AG News",
    )

    assert suggestions[0].suggestion_id == "suggest-mem-fasttext-wordngrams"
    assert suggestions[0].recommended_mcp_tool == "run_client_patch_experiment"
    assert suggestions[0].executes_tool is False
    assert suggestions[0].provenance[0]["card_id"] == "mem-fasttext-wordngrams"
    assert suggestions[0].claim_boundary == "local proof only"


def test_audit_memory_trace_explains_supporting_cards(tmp_path: Path) -> None:
    artifact = tmp_path / "review.json"
    artifact.write_text("{}", encoding="utf-8")
    store = ResearchMemoryStore(tmp_path / "memory.jsonl")
    store.append(
        ResearchMemoryCard(
            card_id="mem-debug-timeout",
            memory_type="failure",
            task_family="text-classification",
            summary="Timeout was fixed by reducing candidate count.",
            failure_category="timeout",
            artifact_refs=[MemoryArtifactRef.from_path("review", artifact)],
            claim_boundary="debug memory only",
        )
    )

    trace = store.audit_trace(["mem-debug-timeout"])

    assert trace.trace_id == "trace-1"
    assert trace.cards[0].card_id == "mem-debug-timeout"
    assert trace.artifact_refs[0].name == "review"
    assert trace.claim_boundaries == ["debug memory only"]
