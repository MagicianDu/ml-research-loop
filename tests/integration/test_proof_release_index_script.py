from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _write_minimal_proof_archive(root: Path) -> Path:
    root.mkdir()
    archive = root / "proof-archive.json"
    artifact_hash = hashlib.sha256(b"local proof log\n").hexdigest()
    archive.write_text(
        json.dumps(
            {
                "status": "archivable",
                "official_scores_claimed": False,
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
                    "limitations": ["local proof is not official benchmark"],
                },
            }
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
            }
        )
        + "\n",
        encoding="utf-8",
    )
    publication = root / "publication"
    publication.mkdir()
    (publication / "proof-publication.json").write_text(
        json.dumps(
            {
                "status": "publishable_with_limitations",
                "official_scores_claimed": False,
                "claim_policy": {
                    "score_claim": "not_allowed",
                    "requires_limitations": True,
                },
                "allowed_public_claims": ["local proof-run artifacts are available"],
                "blocked_public_claims": [
                    "official leaderboard score",
                    "deterministic local fixture score as official benchmark performance",
                ],
                "limitations": ["local proof is not official benchmark"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return archive


def test_proof_release_index_script_writes_outputs(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    archive = _write_minimal_proof_archive(tmp_path / "archive")
    output_dir = tmp_path / "release-index"

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "proof_release_index.py"),
            "--entry",
            f"memflow:{archive}:Local proof archive",
            "--output-dir",
            str(output_dir),
            "--json",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "written"
    assert (output_dir / "proof-release-index.json").exists()
    assert (output_dir / "proof-release-index.md").exists()


def test_proof_release_index_script_returns_2_for_invalid_entry(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "proof_release_index.py"),
            "--entry",
            "invalid-entry",
            "--output-dir",
            str(tmp_path / "release-index"),
            "--json",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "name:path:description" in result.stderr
