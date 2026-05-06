from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lib.benchmarks import build_proof_archive_bundle, write_proof_archive_bundle


def _write_required_artifacts(root: Path) -> dict[str, str]:
    paths = {
        "command_lines": "commands.txt",
        "resolved_config": "config.json",
        "environment_manifest": "environment.json",
        "raw_logs": "logs/run.log",
        "raw_reports": "reports/report.json",
        "limitations_note": "LIMITATIONS.md",
    }
    for role, relative in paths.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{role}: {relative}\n", encoding="utf-8")
    return paths


def test_proof_archive_bundle_indexes_required_artifacts_with_hashes(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifacts = _write_required_artifacts(artifact_root)
    manifest = {
        "benchmark_name": "mle_bench",
        "run_mode": "official_debug",
        "official_scores_claimed": False,
        "limitations": ["debug proof only"],
        "artifacts": artifacts,
    }

    bundle = build_proof_archive_bundle(manifest, artifact_root)

    assert bundle["status"] == "archivable"
    assert bundle["artifact_count"] == 6
    assert bundle["total_size_bytes"] > 0
    assert bundle["publication_guard"]["status"] == "publishable_with_limitations"
    by_role = {entry["role"]: entry for entry in bundle["artifact_index"]}
    assert by_role["raw_logs"]["source_relative_path"] == "logs/run.log"
    expected_hash = hashlib.sha256((artifact_root / "logs" / "run.log").read_bytes()).hexdigest()
    assert by_role["raw_logs"]["sha256"] == expected_hash
    assert by_role["raw_logs"]["archive_relative_path"] == "artifacts/logs/run.log"


def test_proof_archive_bundle_blocks_outside_root_artifacts(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifacts = _write_required_artifacts(artifact_root)
    outside = tmp_path / "outside-report.json"
    outside.write_text("{}\n", encoding="utf-8")
    artifacts["raw_reports"] = "../outside-report.json"
    manifest = {
        "benchmark_name": "paperbench",
        "run_mode": "official_debug",
        "official_scores_claimed": False,
        "artifacts": artifacts,
    }

    bundle = build_proof_archive_bundle(manifest, artifact_root)

    assert bundle["status"] == "blocked"
    assert "raw_reports" in bundle["invalid_artifact_paths"]
    assert all(entry["role"] != "raw_reports" for entry in bundle["artifact_index"])


def test_proof_archive_bundle_includes_score_evidence_when_claimed(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifacts = _write_required_artifacts(artifact_root)
    score_evidence = artifact_root / "reports" / "official-score.json"
    score_evidence.write_text('{"official_score": 0.42}\n', encoding="utf-8")
    manifest = {
        "benchmark_name": "mle_bench",
        "run_mode": "official_debug",
        "official_scores_claimed": True,
        "score_evidence_path": "reports/official-score.json",
        "artifacts": artifacts,
    }

    bundle = build_proof_archive_bundle(manifest, artifact_root)

    assert bundle["status"] == "archivable"
    by_role = {entry["role"]: entry for entry in bundle["artifact_index"]}
    assert by_role["score_evidence"]["source_relative_path"] == "reports/official-score.json"
    assert by_role["score_evidence"]["archive_relative_path"] == (
        "artifacts/reports/official-score.json"
    )


def test_write_proof_archive_bundle_copies_score_evidence_when_claimed(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifacts = _write_required_artifacts(artifact_root)
    (artifact_root / "reports" / "official-score.json").write_text(
        '{"official_score": 0.42}\n',
        encoding="utf-8",
    )
    bundle = build_proof_archive_bundle(
        {
            "benchmark_name": "mle_bench",
            "run_mode": "official_debug",
            "official_scores_claimed": True,
            "score_evidence_path": "reports/official-score.json",
            "artifacts": artifacts,
        },
        artifact_root,
    )

    output = write_proof_archive_bundle(bundle, artifact_root, tmp_path / "archive")

    assert output["status"] == "written"
    assert (tmp_path / "archive" / "artifacts" / "reports" / "official-score.json").exists()


def test_write_proof_archive_bundle_copies_artifacts_and_publication_guard(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    artifacts = _write_required_artifacts(artifact_root)
    bundle = build_proof_archive_bundle(
        {
            "benchmark_name": "mle_bench",
            "run_mode": "official_debug",
            "official_scores_claimed": False,
            "limitations": ["debug proof only"],
            "artifacts": artifacts,
        },
        artifact_root,
    )

    output = write_proof_archive_bundle(bundle, artifact_root, tmp_path / "archive")

    assert output["status"] == "written"
    assert Path(output["json_path"]).exists()
    assert Path(output["index_path"]).exists()
    assert Path(output["publication_json_path"]).exists()
    assert (tmp_path / "archive" / "artifacts" / "logs" / "run.log").exists()
    written = json.loads(Path(output["json_path"]).read_text(encoding="utf-8"))
    index = json.loads(Path(output["index_path"]).read_text(encoding="utf-8"))
    assert written["status"] == "archivable"
    assert index["artifact_count"] == 6
    assert index["artifacts"][0]["sha256"]
