"""Dependency-free smoke test for the local research memory store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.research_memory import ResearchMemoryStore, extract_fasttext_release_memory_cards


PAPER_ID = "arxiv:1607.01759"
DATASET = "AG News"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--json", action="store_true", help="Print JSON payload")
    return parser


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_synthetic_fasttext_release_artifacts(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    release_manifest = output_dir / "release-proof-manifest.json"
    multi_round_report = output_dir / "multi-round-report.json"
    review_checklist = output_dir / "release-review-checklist.md"
    _write_json(
        release_manifest,
        {
            "official_scores_claimed": False,
            "bundle_sha256": "synthetic-smoke",
            "stage": "p5_fasttext_release_proof_bundle",
        },
    )
    _write_json(
        multi_round_report,
        {
            "paper_id": PAPER_ID,
            "baseline_p_at_1": 0.914,
            "best_metric": 0.916,
            "best_source": "round-001-wordngrams-2",
            "failure_count": 1,
            "rollback_summary": {"rollback_events": 1},
        },
    )
    review_checklist.write_text("approved_with_limitations\n", encoding="utf-8")
    return {
        "release_manifest": release_manifest,
        "multi_round_report": multi_round_report,
        "review_checklist": review_checklist,
    }


def run_smoke(output_dir: Path) -> dict[str, object]:
    artifacts = _write_synthetic_fasttext_release_artifacts(output_dir)
    store_path = output_dir / "memory.jsonl"
    if store_path.exists():
        store_path.unlink()
    store = ResearchMemoryStore(store_path)
    cards = extract_fasttext_release_memory_cards(
        release_manifest=artifacts["release_manifest"],
        multi_round_report=artifacts["multi_round_report"],
        review_checklist=artifacts["review_checklist"],
    )
    for card in cards:
        store.append(card)
    matches = store.search(
        query=f"{DATASET} fastText",
        paper_id=PAPER_ID,
        dataset=DATASET,
        limit=5,
    )
    return {
        "status": "passed" if matches else "failed",
        "store": str(store_path),
        "match_count": len(matches),
        "official_scores_claimed": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_smoke(args.output_dir)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
