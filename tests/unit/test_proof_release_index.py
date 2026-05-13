from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lib.proof_release_index import parse_entry_spec, write_proof_release_index


def _write_minimal_proof_archive(root: Path) -> Path:
    root.mkdir()
    archive = root / "proof-archive.json"
    artifact_bytes = b"local proof log\n"
    artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
    archive.write_text(
        json.dumps(
            {
                "status": "archivable",
                "official_scores_claimed": True,
                "benchmark_name": "memflow",
                "run_mode": "local_debug",
                "artifact_count": 1,
                "artifact_index": [
                    {
                        "role": "raw_logs",
                        "archive_relative_path": "artifacts/logs/run.log",
                        "sha256": artifact_hash,
                    }
                ],
                "artifact_manifest": {
                    "judge_type": "deterministic-local",
                    "metric": "answer_accuracy",
                    "limitations": ["local subset proof only"],
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "artifact-index.json").write_text(
        json.dumps(
            {
                "artifact_count": 1,
                "artifacts": [
                    {
                        "role": "raw_logs",
                        "archive_relative_path": "artifacts/logs/run.log",
                        "sha256": artifact_hash,
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    publication_dir = root / "publication"
    publication_dir.mkdir()
    (publication_dir / "proof-publication.json").write_text(
        json.dumps(
            {
                "status": "publishable_with_limitations",
                "official_scores_claimed": True,
                "claim_policy": {
                    "score_claim": "blocked_missing_evidence",
                    "requires_limitations": True,
                },
                "allowed_public_claims": ["local proof-run artifacts are available"],
                "blocked_public_claims": [
                    "official leaderboard score",
                    "deterministic local fixture score as official benchmark performance",
                ],
                "limitations": ["not an official benchmark result"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return archive


def test_write_proof_release_index_writes_json_and_markdown(tmp_path: Path) -> None:
    archive_path = _write_minimal_proof_archive(tmp_path / "archive")

    payload = write_proof_release_index(
        [
            {
                "name": "memflow-local-proof",
                "proof_archive": str(archive_path),
                "description": "Local MemFlow subset proof archive",
            }
        ],
        tmp_path / "release-index",
    )

    json_path = tmp_path / "release-index" / "proof-release-index.json"
    markdown_path = tmp_path / "release-index" / "proof-release-index.md"
    assert payload["status"] == "written"
    assert payload["official_scores_claimed"] is False
    assert payload["entry_count"] == 1
    assert json_path.exists()
    assert markdown_path.exists()

    written = json.loads(json_path.read_text(encoding="utf-8"))
    entry = written["entries"][0]
    assert entry["name"] == "memflow-local-proof"
    assert entry["official_scores_claimed"] is False
    assert entry["source_official_scores_claimed"] is True
    assert entry["artifact_count"] == 1
    assert entry["artifacts"][0]["sha256"]
    assert "official leaderboard score" in entry["blocked_public_claims"]
    assert "local subset proof only" in entry["limitations"]
    assert entry["proof_archive"] == str(archive_path.resolve())
    assert entry["artifact_index"] == str((tmp_path / "archive" / "artifact-index.json").resolve())
    assert entry["publication_guard"] == str(
        (tmp_path / "archive" / "publication" / "proof-publication.json").resolve()
    )

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Proof Release Evidence Index" in markdown
    assert "official_scores_claimed: `false`" in markdown
    assert "official leaderboard score" in markdown
    assert "sha256" in markdown
    assert "not an official benchmark result" in markdown


def test_write_proof_release_index_rejects_missing_neighbor(tmp_path: Path) -> None:
    archive_path = tmp_path / "archive" / "proof-archive.json"
    archive_path.parent.mkdir()
    archive_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact-index.json"):
        write_proof_release_index(
            [
                {
                    "name": "incomplete-proof",
                    "proof_archive": str(archive_path),
                    "description": "Incomplete proof archive",
                }
            ],
            tmp_path / "release-index",
        )


def test_write_proof_release_index_rejects_wrong_archive_filename(tmp_path: Path) -> None:
    archive_path = tmp_path / "archive" / "not-proof-archive.json"
    archive_path.parent.mkdir()
    archive_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="proof-archive.json"):
        write_proof_release_index(
            [
                {
                    "name": "wrong-file",
                    "proof_archive": str(archive_path),
                    "description": "Wrong proof archive filename",
                }
            ],
            tmp_path / "release-index",
        )


def test_write_proof_release_index_rejects_missing_publication_guard(tmp_path: Path) -> None:
    archive_path = tmp_path / "archive" / "proof-archive.json"
    archive_path.parent.mkdir()
    archive_path.write_text("{}\n", encoding="utf-8")
    (archive_path.parent / "artifact-index.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="proof-publication.json"):
        write_proof_release_index(
            [
                {
                    "name": "incomplete-proof",
                    "proof_archive": str(archive_path),
                    "description": "Incomplete proof archive",
                }
            ],
            tmp_path / "release-index",
        )


def test_write_proof_release_index_rejects_malformed_artifact_index(tmp_path: Path) -> None:
    archive_path = _write_minimal_proof_archive(tmp_path / "archive")
    (archive_path.parent / "artifact-index.json").write_text(
        json.dumps(
            {
                "artifact_count": 1,
                "artifacts": [
                    {
                        "role": "raw_logs",
                        "archive_relative_path": "artifacts/logs/run.log",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="sha256"):
        write_proof_release_index(
            [
                {
                    "name": "malformed-index",
                    "proof_archive": str(archive_path),
                    "description": "Malformed artifact index",
                }
            ],
            tmp_path / "release-index",
        )


def test_write_proof_release_index_rejects_invalid_artifact_sha(tmp_path: Path) -> None:
    archive_path = _write_minimal_proof_archive(tmp_path / "archive")
    index_path = archive_path.parent / "artifact-index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    payload["artifacts"][0]["sha256"] = "not-a-sha"
    index_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256"):
        write_proof_release_index(
            [
                {
                    "name": "invalid-sha",
                    "proof_archive": str(archive_path),
                    "description": "Invalid artifact hash",
                }
            ],
            tmp_path / "release-index",
        )


def test_write_proof_release_index_rejects_unsafe_artifact_path(tmp_path: Path) -> None:
    archive_path = _write_minimal_proof_archive(tmp_path / "archive")
    index_path = archive_path.parent / "artifact-index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    payload["artifacts"][0]["archive_relative_path"] = "../run.log"
    index_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="archive_relative_path"):
        write_proof_release_index(
            [
                {
                    "name": "unsafe-path",
                    "proof_archive": str(archive_path),
                    "description": "Unsafe artifact path",
                }
            ],
            tmp_path / "release-index",
        )


def test_write_proof_release_index_rejects_invalid_artifact_size(tmp_path: Path) -> None:
    archive_path = _write_minimal_proof_archive(tmp_path / "archive")
    index_path = archive_path.parent / "artifact-index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    payload["artifacts"][0]["size_bytes"] = -1
    index_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="size_bytes"):
        write_proof_release_index(
            [
                {
                    "name": "invalid-size",
                    "proof_archive": str(archive_path),
                    "description": "Invalid artifact size",
                }
            ],
            tmp_path / "release-index",
        )


def test_write_proof_release_index_rejects_malformed_proof_archive(tmp_path: Path) -> None:
    archive_path = _write_minimal_proof_archive(tmp_path / "archive")
    payload = json.loads(archive_path.read_text(encoding="utf-8"))
    payload.pop("artifact_manifest")
    archive_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact_manifest"):
        write_proof_release_index(
            [
                {
                    "name": "malformed-archive",
                    "proof_archive": str(archive_path),
                    "description": "Malformed proof archive",
                }
            ],
            tmp_path / "release-index",
        )


def test_write_proof_release_index_rejects_artifact_count_mismatch(tmp_path: Path) -> None:
    archive_path = _write_minimal_proof_archive(tmp_path / "archive")
    index_path = archive_path.parent / "artifact-index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    payload["artifact_count"] = 2
    index_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact_count"):
        write_proof_release_index(
            [
                {
                    "name": "mismatch-index",
                    "proof_archive": str(archive_path),
                    "description": "Mismatched artifact index",
                }
            ],
            tmp_path / "release-index",
        )


def test_write_proof_release_index_rejects_malformed_publication_guard(tmp_path: Path) -> None:
    archive_path = _write_minimal_proof_archive(tmp_path / "archive")
    publication_path = archive_path.parent / "publication" / "proof-publication.json"
    payload = json.loads(publication_path.read_text(encoding="utf-8"))
    payload.pop("official_scores_claimed")
    publication_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="official_scores_claimed"):
        write_proof_release_index(
            [
                {
                    "name": "malformed-publication",
                    "proof_archive": str(archive_path),
                    "description": "Malformed publication guard",
                }
            ],
            tmp_path / "release-index",
        )


def test_write_proof_release_index_rejects_publication_guard_without_claim_policy(
    tmp_path: Path,
) -> None:
    archive_path = _write_minimal_proof_archive(tmp_path / "archive")
    publication_path = archive_path.parent / "publication" / "proof-publication.json"
    payload = json.loads(publication_path.read_text(encoding="utf-8"))
    payload.pop("claim_policy")
    publication_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="claim_policy"):
        write_proof_release_index(
            [
                {
                    "name": "malformed-publication",
                    "proof_archive": str(archive_path),
                    "description": "Malformed publication guard",
                }
            ],
            tmp_path / "release-index",
        )


def test_write_proof_release_index_rejects_publication_guard_missing_boundaries(
    tmp_path: Path,
) -> None:
    archive_path = _write_minimal_proof_archive(tmp_path / "archive")
    publication_path = archive_path.parent / "publication" / "proof-publication.json"
    payload = json.loads(publication_path.read_text(encoding="utf-8"))
    payload["blocked_public_claims"] = ["unrelated boundary"]
    publication_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="blocked_public_claims"):
        write_proof_release_index(
            [
                {
                    "name": "missing-boundary",
                    "proof_archive": str(archive_path),
                    "description": "Missing required blocked claims",
                }
            ],
            tmp_path / "release-index",
        )


def test_write_proof_release_index_rejects_unknown_score_policy(tmp_path: Path) -> None:
    archive_path = _write_minimal_proof_archive(tmp_path / "archive")
    publication_path = archive_path.parent / "publication" / "proof-publication.json"
    payload = json.loads(publication_path.read_text(encoding="utf-8"))
    payload["claim_policy"]["score_claim"] = "unknown-policy"
    publication_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="score_claim"):
        write_proof_release_index(
            [
                {
                    "name": "unknown-policy",
                    "proof_archive": str(archive_path),
                    "description": "Unknown score policy",
                }
            ],
            tmp_path / "release-index",
        )


def test_parse_entry_spec_reads_name_path_and_description() -> None:
    parsed = parse_entry_spec("name:/tmp/proof-archive.json:description with colon: detail")

    assert parsed == {
        "name": "name",
        "proof_archive": "/tmp/proof-archive.json",
        "description": "description with colon: detail",
    }
