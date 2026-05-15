from __future__ import annotations

import json
from pathlib import Path

from lib.research_memory import MemoryArtifactRef, ResearchMemoryCard, ResearchMemoryStore


def test_memory_guided_proposal_writes_advisory_handoff(tmp_path: Path, capsys) -> None:
    from scripts import memory_guided_proposal

    artifact = tmp_path / "multi-round-report.json"
    artifact.write_text('{"best_metric": 0.916}', encoding="utf-8")
    store_path = tmp_path / "memory.jsonl"
    ResearchMemoryStore(store_path).append(
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
    output_dir = tmp_path / "handoff"

    payload = memory_guided_proposal.build_memory_guided_proposal(
        store=store_path,
        query="fastText AG News improve P@1",
        output_dir=output_dir,
        paper_id="arxiv:1607.01759",
        dataset="AG News",
    )
    exit_code = memory_guided_proposal.main([
        "--store",
        str(store_path),
        "--query",
        "fastText AG News improve P@1",
        "--output-dir",
        str(output_dir),
        "--paper-id",
        "arxiv:1607.01759",
        "--dataset",
        "AG News",
        "--json",
    ])

    printed = json.loads(capsys.readouterr().out)
    handoff = json.loads(
        (output_dir / "memory-guided-proposal.json").read_text(encoding="utf-8")
    )
    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["executes_tool"] is False
    assert payload["recommended_next_step"]["mcp_tool"] == "run_client_patch_experiment"
    assert payload["memory_provenance"][0]["card_id"] == "mem-fasttext-wordngrams"
    assert handoff["memory_provenance"][0]["card_id"] == "mem-fasttext-wordngrams"
    assert printed["proposal_file"].endswith("memory-guided-proposal.json")


def test_memory_guided_proposal_reports_needs_memory_when_no_matches(
    tmp_path: Path,
) -> None:
    from scripts import memory_guided_proposal

    store_path = tmp_path / "empty-memory.jsonl"
    output_dir = tmp_path / "handoff"

    payload = memory_guided_proposal.build_memory_guided_proposal(
        store=store_path,
        query="no match",
        output_dir=output_dir,
    )

    assert payload["status"] == "needs_memory"
    assert payload["executes_tool"] is False
    assert payload["memory_provenance"] == []
