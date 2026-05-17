from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.publish_release_evidence import (
    ReleaseEvidenceEntry,
    publish_benchmark_archive,
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
