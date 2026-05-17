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


def _write_fasttext_release_artifacts(
    proof_dir: Path,
    *,
    release_stage: str = "p5_fasttext_release_proof_bundle",
    release_status: str = "completed",
    review_status: str = "approved_with_limitations",
    review_text: str = "Review status: `approved_with_limitations`",
    multi_round_stage: str = "p5_fasttext_multi_proposal_loop",
    baseline_p_at_1: float = 0.914,
    best_metric: float = 0.916,
) -> tuple[Path, Path, Path]:
    proof_dir.mkdir()
    manifest = proof_dir / "release-proof-manifest.json"
    review = proof_dir / "release-review-checklist.md"
    multi_round = proof_dir / "multi-round-report.json"
    manifest.write_text(
        json.dumps(
            {
                "official_scores_claimed": False,
                "bundle_sha256": "abc123",
                "stage": release_stage,
                "status": release_status,
                "p4_summary": {"review_status": review_status},
            }
        ),
        encoding="utf-8",
    )
    review.write_text(review_text, encoding="utf-8")
    multi_round.write_text(
        json.dumps(
            {
                "stage": multi_round_stage,
                "official_scores_claimed": False,
                "paper_reference": {"paper_id": "arxiv:1607.01759"},
                "baseline": {"p_at_1": baseline_p_at_1},
                "summary": {
                    "best_metric": best_metric,
                    "best_source": "round-001-wordngrams-2",
                    "failure_count": 1,
                },
                "rollback_summary": {"rollback_events": 1},
            }
        ),
        encoding="utf-8",
    )
    return manifest, multi_round, review


def _procedure_memory_card(
    tmp_path: Path,
    card_id: str,
    *,
    created_at: float,
    memory_type: str = "procedure",
    privacy_scope: str = "public",
) -> ResearchMemoryCard:
    artifact_refs = []
    if memory_type != "procedure":
        artifact = tmp_path / f"{card_id}.txt"
        artifact.write_text(f"{card_id} cleanup policy artifact.", encoding="utf-8")
        artifact_refs = [MemoryArtifactRef.from_path(f"{card_id}_artifact", artifact)]
    return ResearchMemoryCard(
        card_id=card_id,
        memory_type=memory_type,
        task_family="cleanup-policy",
        summary=f"{card_id} cleanup policy memory.",
        artifact_refs=artifact_refs,
        privacy_scope=privacy_scope,
        allow_private_ingestion=privacy_scope != "public",
        created_at=created_at,
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


def test_memory_store_exports_redacted_private_cards_by_default(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "private-log.txt"
    artifact.write_text("private user dataset path", encoding="utf-8")
    store = ResearchMemoryStore(tmp_path / "memory.jsonl")
    store.append(
        ResearchMemoryCard(
            card_id="mem-private-debug",
            memory_type="failure",
            task_family="private-task",
            summary="Private run failed on /secret/customer.csv.",
            failure_category="data_error",
            config={"private_path": "/secret/customer.csv"},
            evidence_refs=[
                MemoryEvidenceRef(
                    source_id="private-log",
                    artifact_path=str(artifact),
                    quote="customer-specific private error",
                    url="https://private.example.local/log",
                )
            ],
            artifact_refs=[MemoryArtifactRef.from_path("private_log", artifact)],
            privacy_scope="private",
            allow_private_ingestion=True,
            tags=["private-debug"],
        )
    )
    export_path = tmp_path / "redacted-export.jsonl"

    result = store.export_cards(export_path)
    payload = json.loads(export_path.read_text(encoding="utf-8").splitlines()[0])

    assert result["status"] == "exported"
    assert result["exported_count"] == 1
    assert result["redacted_count"] == 1
    assert payload["summary"] == "[REDACTED PRIVATE MEMORY]"
    assert payload["privacy_scope"] == "public"
    assert payload["config"] == {}
    assert payload["artifact_refs"][0]["path"] == "[REDACTED]"
    assert payload["artifact_refs"][0]["sha256"] == "[REDACTED]"
    assert payload["evidence_refs"][0]["artifact_path"] == "[REDACTED]"
    assert payload["evidence_refs"][0]["quote"] == "[REDACTED]"
    assert payload["evidence_refs"][0]["url"] == "[REDACTED]"
    assert "redacted_private" in payload["tags"]


def test_memory_store_import_rejects_private_cards_without_opt_in(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "private-log.txt"
    artifact.write_text("private user dataset path", encoding="utf-8")
    private_card = ResearchMemoryCard(
        card_id="mem-private-import",
        memory_type="failure",
        task_family="private-task",
        summary="Private import.",
        artifact_refs=[MemoryArtifactRef.from_path("private_log", artifact)],
        privacy_scope="private",
        allow_private_ingestion=True,
    )
    import_path = tmp_path / "private-import.jsonl"
    import_path.write_text(
        json.dumps(private_card.to_dict(), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    store = ResearchMemoryStore(tmp_path / "memory.jsonl")

    with pytest.raises(ValueError, match="private memory import"):
        store.import_cards(import_path)

    result = store.import_cards(import_path, allow_private=True)

    assert result["status"] == "imported"
    assert result["imported_count"] == 1
    assert store.list_cards()[0].card_id == "mem-private-import"


def test_memory_cleanup_dry_run_keeps_latest_matching_cards_without_rewriting(
    tmp_path: Path,
) -> None:
    store = ResearchMemoryStore(tmp_path / "memory.jsonl")
    cards = [
        _procedure_memory_card(tmp_path, "proc-old", created_at=10.0),
        _procedure_memory_card(
            tmp_path,
            "failure-old",
            memory_type="failure",
            created_at=5.0,
        ),
        _procedure_memory_card(tmp_path, "proc-new", created_at=30.0),
        _procedure_memory_card(tmp_path, "proc-middle", created_at=20.0),
        _procedure_memory_card(
            tmp_path,
            "proc-private-old",
            created_at=1.0,
            privacy_scope="private",
        ),
    ]
    for card in cards:
        store.append(card)
    before = store.path.read_text(encoding="utf-8")

    result = store.cleanup(memory_type="procedure", keep_last=2, dry_run=True)

    assert result["dry_run"] is True
    assert result["candidate_count"] == 1
    assert result["deleted_count"] == 0
    assert result["kept_count"] == 4
    assert [item["card_id"] for item in result["candidates"]] == ["proc-old"]
    assert store.path.read_text(encoding="utf-8") == before
    assert [card.card_id for card in store.list_cards()] == [
        "proc-old",
        "failure-old",
        "proc-new",
        "proc-middle",
        "proc-private-old",
    ]


def test_memory_cleanup_execute_excludes_private_by_default_and_keeps_jsonl_readable(
    tmp_path: Path,
) -> None:
    store = ResearchMemoryStore(tmp_path / "memory.jsonl")
    for card in [
        _procedure_memory_card(
            tmp_path,
            "failure-public-old",
            memory_type="failure",
            created_at=1.0,
        ),
        _procedure_memory_card(
            tmp_path,
            "failure-private-old",
            memory_type="failure",
            created_at=1.0,
            privacy_scope="private",
        ),
        _procedure_memory_card(
            tmp_path,
            "failure-public-new",
            memory_type="failure",
            created_at=4_000_000_000.0,
        ),
    ]:
        store.append(card)

    result = store.cleanup(memory_type="failure", older_than_days=1, dry_run=False)

    assert result["dry_run"] is False
    assert result["candidate_count"] == 1
    assert result["deleted_count"] == 1
    assert result["kept_count"] == 2
    assert [item["card_id"] for item in result["candidates"]] == [
        "failure-public-old"
    ]
    assert [card.card_id for card in store.list_cards()] == [
        "failure-private-old",
        "failure-public-new",
    ]


def test_memory_cleanup_include_private_allows_private_deletion(
    tmp_path: Path,
) -> None:
    store = ResearchMemoryStore(tmp_path / "memory.jsonl")
    for card in [
        _procedure_memory_card(
            tmp_path,
            "failure-public-old",
            memory_type="failure",
            created_at=1.0,
        ),
        _procedure_memory_card(
            tmp_path,
            "failure-private-old",
            memory_type="failure",
            created_at=1.0,
            privacy_scope="private",
        ),
    ]:
        store.append(card)

    result = store.cleanup(
        memory_type="failure",
        older_than_days=1,
        include_private=True,
    )

    assert result["candidate_count"] == 2
    assert result["deleted_count"] == 2
    assert [item["card_id"] for item in result["candidates"]] == [
        "failure-public-old",
        "failure-private-old",
    ]
    assert store.list_cards() == []


def test_memory_cleanup_keep_last_falls_back_to_file_order_without_timestamps(
    tmp_path: Path,
) -> None:
    store = ResearchMemoryStore(tmp_path / "memory.jsonl")
    payloads = [
        {
            "card_id": "proc-first",
            "memory_type": "procedure",
            "task_family": "cleanup-policy",
            "summary": "first procedure",
        },
        {
            "card_id": "proc-second",
            "memory_type": "procedure",
            "task_family": "cleanup-policy",
            "summary": "second procedure",
        },
        {
            "card_id": "proc-third",
            "memory_type": "procedure",
            "task_family": "cleanup-policy",
            "summary": "third procedure",
        },
    ]
    store.path.write_text(
        "\n".join(json.dumps(payload, ensure_ascii=False) for payload in payloads) + "\n",
        encoding="utf-8",
    )

    result = store.cleanup(memory_type="procedure", keep_last=1)

    assert result["candidate_count"] == 2
    assert result["deleted_count"] == 2
    assert [item["card_id"] for item in result["candidates"]] == [
        "proc-first",
        "proc-second",
    ]
    assert [card.card_id for card in store.list_cards()] == ["proc-third"]


def test_extract_fasttext_release_memory_cards(tmp_path: Path) -> None:
    manifest, multi_round, review = _write_fasttext_release_artifacts(
        tmp_path / "release-proof"
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
    assert cards[0].config["best_source"] == "round-001-wordngrams-2"
    assert cards[0].official_scores_claimed is False
    assert cards[1].failure_category == "invalid_or_failed_proposal"
    assert cards[1].config["failure_count"] == 1


def test_extract_fasttext_release_memory_cards_rejects_non_release_manifest(
    tmp_path: Path,
) -> None:
    manifest, multi_round, review = _write_fasttext_release_artifacts(
        tmp_path / "release-proof",
        release_stage="p4_fasttext_client_review",
    )

    from lib.research_memory import extract_fasttext_release_memory_cards

    with pytest.raises(ValueError, match="p5_fasttext_release_proof_bundle"):
        extract_fasttext_release_memory_cards(
            release_manifest=manifest,
            multi_round_report=multi_round,
            review_checklist=review,
        )


def test_extract_fasttext_release_memory_cards_rejects_unapproved_review(
    tmp_path: Path,
) -> None:
    manifest, multi_round, review = _write_fasttext_release_artifacts(
        tmp_path / "release-proof",
        review_status="needs_more_evidence",
        review_text="Review status: `needs_more_evidence`",
    )

    from lib.research_memory import extract_fasttext_release_memory_cards

    with pytest.raises(ValueError, match="approved_with_limitations"):
        extract_fasttext_release_memory_cards(
            release_manifest=manifest,
            multi_round_report=multi_round,
            review_checklist=review,
        )


def test_extract_fasttext_release_memory_cards_rejects_non_improving_best_metric(
    tmp_path: Path,
) -> None:
    manifest, multi_round, review = _write_fasttext_release_artifacts(
        tmp_path / "release-proof",
        baseline_p_at_1=0.916,
        best_metric=0.914,
    )

    from lib.research_memory import extract_fasttext_release_memory_cards

    with pytest.raises(ValueError, match="best_metric"):
        extract_fasttext_release_memory_cards(
            release_manifest=manifest,
            multi_round_report=multi_round,
            review_checklist=review,
        )


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
