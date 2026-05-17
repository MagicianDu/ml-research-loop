from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path

from scripts.publish_release_evidence import (
    ReleaseEvidenceEntry,
    publish_benchmark_archive,
    publish_fasttext_release_archive,
    publish_real_paper_archive,
)


def test_publish_real_paper_archive_writes_sanitized_complete_archive(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime" / "proof"
    artifact = source / "artifacts" / "run-log.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("local real paper proof log\n", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = source / "proof-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "paper_id": "arxiv:2605.03312",
                "claim": "intent-driven routing improves bounded selection",
                "official_scores_claimed": False,
                "artifacts": [
                    {
                        "role": "run_log",
                        "archive_path": "artifacts/run-log.txt",
                        "sha256": digest,
                        "size_bytes": artifact.stat().st_size,
                    }
                ],
                "metric_summary": {
                    "metric_name": "selection_accuracy",
                    "metric_before": 0.25,
                    "metric_after": 1.0,
                },
                "limitations": ["local public mini-slice only"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = publish_real_paper_archive(
        ReleaseEvidenceEntry(
            name="memflow-real-paper",
            path=manifest,
            description="MemFlow bounded real-paper pilot",
        ),
        tmp_path / "published",
    )

    archive_root = Path(result["archive_dir"])
    assert result["status"] == "published"
    assert result["artifact_count"] == 1
    assert (archive_root / "proof-archive.json").is_file()
    assert (archive_root / "artifact-index.json").is_file()
    assert (archive_root / "publication" / "proof-publication.json").is_file()
    assert (archive_root / "artifacts" / "run-log.txt").read_text(
        encoding="utf-8"
    ) == "local real paper proof log\n"

    archive_text = (archive_root / "proof-archive.json").read_text(encoding="utf-8")
    publication_text = (
        archive_root / "publication" / "proof-publication.json"
    ).read_text(encoding="utf-8")
    assert str(tmp_path) not in archive_text
    assert str(tmp_path) not in publication_text
    assert "official_scores_claimed" in archive_text
    assert "selection_accuracy" in archive_text


def test_publish_benchmark_archive_copies_artifacts_and_redacts_local_paths(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime" / "archive"
    artifact = source / "artifacts" / "commands.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("python mlebench grade-sample\n", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (source / "proof-archive.json").write_text(
        json.dumps(
            {
                "status": "archivable",
                "official_scores_claimed": False,
                "benchmark_name": "mle_bench",
                "run_mode": "official_debug_patch_round",
                "source_artifact_root": str(tmp_path / "runtime" / "private"),
                "artifact_count": 1,
                "artifact_manifest": {
                    "judge_type": "official_scorer",
                    "metric": "log_loss",
                    "limitations": ["local grade-sample feedback only"],
                },
                "publication_guard": {
                    "artifact_root": str(tmp_path / "runtime" / "private"),
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (source / "artifact-index.json").write_text(
        json.dumps(
            {
                "artifact_count": 1,
                "artifacts": [
                    {
                        "role": "command_lines",
                        "archive_relative_path": "artifacts/commands.txt",
                        "size_bytes": artifact.stat().st_size,
                        "sha256": digest,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    publication = source / "publication"
    publication.mkdir()
    (publication / "proof-publication.json").write_text(
        json.dumps(
            {
                "status": "publishable_with_limitations",
                "official_scores_claimed": False,
                "artifact_root": str(tmp_path / "runtime" / "private"),
                "claim_policy": {
                    "score_claim": "not_allowed",
                    "requires_limitations": True,
                },
                "allowed_public_claims": ["debug proof-run artifacts are available"],
                "blocked_public_claims": [
                    "official leaderboard score",
                    "deterministic local fixture score as official benchmark performance",
                ],
                "limitations": ["local grade-sample feedback only"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = publish_benchmark_archive(
        ReleaseEvidenceEntry(
            name="mle-official-debug",
            path=source / "proof-archive.json",
            description="MLE-bench official-debug proof",
        ),
        tmp_path / "published",
    )

    archive_root = Path(result["archive_dir"])
    archive_text = (archive_root / "proof-archive.json").read_text(encoding="utf-8")
    publication_text = (
        archive_root / "publication" / "proof-publication.json"
    ).read_text(encoding="utf-8")
    assert result["status"] == "published"
    assert (archive_root / "artifacts" / "commands.txt").read_text(
        encoding="utf-8"
    ) == "python mlebench grade-sample\n"
    assert str(tmp_path) not in archive_text
    assert str(tmp_path) not in publication_text
    assert "redacted_local_runtime_root" in archive_text
    assert "official_debug_patch_round" in archive_text


def test_publish_fasttext_release_archive_repacks_sanitized_public_bundle(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime" / "fasttext-release"
    package = source / "review-package" / "p4-proof"
    package.mkdir(parents=True)
    local_path = tmp_path / "runtime" / "private" / "improvement-report.json"
    (package / "proof-manifest.json").write_text(
        json.dumps(
            {
                "source_patch_round_report": str(local_path),
                "artifacts": [
                    {
                        "role": "improvement_report",
                        "source_path": str(local_path),
                        "archive_relative_path": "artifacts/improvement-report.json",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (package / "proof-summary.md").write_text(
        f"source: {local_path}\n",
        encoding="utf-8",
    )
    source_bundle = source / "release-proof-bundle.tar.gz"
    with tarfile.open(source_bundle, "w:gz") as archive:
        archive.add(source / "review-package", arcname="ml-research-loop-fasttext-proof")
    source_sha = hashlib.sha256(source_bundle.read_bytes()).hexdigest()
    checksum = source / "release-proof-bundle.sha256"
    checksum.write_text(f"{source_sha}  release-proof-bundle.tar.gz\n", encoding="utf-8")
    checklist = source / "release-review-checklist.md"
    checklist.write_text(
        f"# Review\n\nsource path: {local_path}\n",
        encoding="utf-8",
    )
    multi_round = source / "multi-round-report.json"
    multi_round.write_text(
        json.dumps(
            {
                "stage": "p5_fasttext_multi_proposal_loop",
                "best_report": str(local_path),
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = source / "release-proof-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "2026-05-14.fasttext-release-proof-bundle.v1",
                "status": "completed",
                "stage": "p5_fasttext_release_proof_bundle",
                "source_multi_round_report": str(multi_round),
                "p4_summary": {
                    "review_status": "approved_with_limitations",
                    "artifact_count": 2,
                    "metric_summary": {
                        "name": "accuracy",
                        "baseline_p_at_1": 0.914,
                        "p_at_1": 0.916,
                        "delta": 0.002,
                        "improved": True,
                    },
                },
                "multi_round_summary": {
                    "included": True,
                    "failure_count": 1,
                    "rollback_events": 1,
                    "best_metric": 0.916,
                },
                "download_artifact": {
                    "path": str(source_bundle),
                    "sha256": source_sha,
                    "checksum_file": str(checksum),
                    "format": "tar.gz",
                },
                "blocked_public_claims": [
                    "official_benchmark_or_sota",
                    "full_paper_all_tables_reproduced",
                ],
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = publish_fasttext_release_archive(
        ReleaseEvidenceEntry(
            name="fasttext-ag-news-full-reproduction",
            path=manifest,
            description="fastText AG News full reproduction proof",
        ),
        tmp_path / "published",
    )

    archive_root = Path(result["archive_dir"])
    archive_text = (archive_root / "proof-archive.json").read_text(encoding="utf-8")
    publication_text = (
        archive_root / "publication" / "proof-publication.json"
    ).read_text(encoding="utf-8")
    public_bundle = archive_root / "artifacts" / "release-proof-bundle.tar.gz"
    public_checksum = archive_root / "artifacts" / "release-proof-bundle.sha256"
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    with tarfile.open(public_bundle, "r:gz") as archive:
        archive.extractall(extracted, filter="data")
    extracted_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in extracted.rglob("*")
        if path.is_file()
    )

    assert result["status"] == "published"
    assert result["artifact_count"] == 5
    assert "full_reproduction_fasttext" in archive_text
    assert "baseline_p_at_1" in archive_text
    assert "0.916" in archive_text
    assert "rollback_events" in archive_text
    assert "redacted_local_runtime_root" in archive_text
    assert str(tmp_path) not in archive_text
    assert str(tmp_path) not in publication_text
    assert str(tmp_path) not in extracted_text
    assert "redacted_local_runtime_root" in extracted_text
    assert public_bundle.name in public_checksum.read_text(encoding="utf-8")
