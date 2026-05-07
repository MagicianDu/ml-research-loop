from __future__ import annotations

import json
from pathlib import Path

from lib.benchmarks import (
    build_proof_publication_bundle,
    render_proof_publication_markdown,
    write_proof_publication_bundle,
)


def _write_required_artifacts(root: Path) -> dict[str, str]:
    paths = {
        "command_lines": "commands.txt",
        "resolved_config": "config.json",
        "environment_manifest": "environment.json",
        "raw_logs": "logs/run.log",
        "raw_reports": "reports/report.json",
        "limitations_note": "LIMITATIONS.md",
    }
    for relative in paths.values():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"artifact: {relative}\n", encoding="utf-8")
    return paths


def test_proof_publication_bundle_is_publishable_with_limitations(tmp_path: Path) -> None:
    artifacts = _write_required_artifacts(tmp_path)
    manifest = {
        "benchmark_name": "mle_bench",
        "run_mode": "official_debug",
        "official_scores_claimed": False,
        "limitations": ["debug split only", "no leaderboard score claimed"],
        "artifacts": artifacts,
    }

    bundle = build_proof_publication_bundle(manifest, tmp_path)

    assert bundle["status"] == "publishable_with_limitations"
    assert bundle["read_only"] is True
    assert bundle["official_scores_claimed"] is False
    assert bundle["missing_artifacts"] == []
    assert "official leaderboard score" in bundle["blocked_public_claims"]
    assert "debug proof-run artifacts are available" in bundle["allowed_public_claims"]
    assert bundle["claim_policy"]["score_claim"] == "not_allowed"


def test_proof_publication_bundle_blocks_missing_artifacts(tmp_path: Path) -> None:
    artifacts = _write_required_artifacts(tmp_path)
    (tmp_path / artifacts["raw_reports"]).unlink()
    manifest = {
        "benchmark_name": "paperbench",
        "run_mode": "official_debug",
        "official_scores_claimed": False,
        "artifacts": artifacts,
    }

    bundle = build_proof_publication_bundle(manifest, tmp_path)

    assert bundle["status"] == "blocked"
    assert "raw_reports" in bundle["missing_artifacts"]
    assert "artifact completeness" in bundle["blocked_public_claims"]


def test_proof_publication_bundle_blocks_artifacts_outside_root(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifacts = _write_required_artifacts(artifact_root)
    outside_file = tmp_path / "outside-report.json"
    outside_file.write_text("{}\n", encoding="utf-8")
    artifacts["raw_reports"] = "../outside-report.json"
    manifest = {
        "benchmark_name": "mle_bench",
        "run_mode": "official_debug",
        "official_scores_claimed": False,
        "artifacts": artifacts,
    }

    bundle = build_proof_publication_bundle(manifest, artifact_root)

    assert bundle["status"] == "blocked"
    assert "raw_reports" in bundle["missing_artifacts"]
    assert "raw_reports" in bundle["invalid_artifact_paths"]


def test_proof_publication_bundle_blocks_extra_artifacts_outside_root(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifacts = _write_required_artifacts(artifact_root)
    outside_file = tmp_path / "outside.patch"
    outside_file.write_text("--- a/solve.py\n", encoding="utf-8")
    artifacts["patch_diff"] = "../outside.patch"
    manifest = {
        "benchmark_name": "mle_bench",
        "run_mode": "official_debug_patch_round",
        "official_scores_claimed": False,
        "artifacts": artifacts,
    }

    bundle = build_proof_publication_bundle(manifest, artifact_root)

    assert bundle["status"] == "blocked"
    assert "patch_diff" in bundle["invalid_artifact_paths"]
    assert "artifact path confinement" in bundle["blocked_public_claims"]


def test_proof_publication_bundle_blocks_unbacked_score_claim(tmp_path: Path) -> None:
    artifacts = _write_required_artifacts(tmp_path)
    manifest = {
        "benchmark_name": "mle_bench",
        "run_mode": "official_debug",
        "official_scores_claimed": True,
        "score_evidence_path": "reports/missing-official-score.json",
        "artifacts": artifacts,
    }

    bundle = build_proof_publication_bundle(manifest, tmp_path)

    assert bundle["status"] == "blocked"
    assert bundle["claim_policy"]["score_claim"] == "blocked_missing_evidence"
    assert "official score claim" in bundle["blocked_public_claims"]


def test_write_proof_publication_bundle_writes_json_and_markdown(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifacts = _write_required_artifacts(artifact_root)
    bundle = build_proof_publication_bundle(
        {
            "benchmark_name": "paperbench",
            "run_mode": "official_debug",
            "official_scores_claimed": False,
            "limitations": ["dummy judge only"],
            "artifacts": artifacts,
        },
        artifact_root,
    )

    output = write_proof_publication_bundle(bundle, tmp_path / "publication")

    assert output["status"] == "written"
    assert Path(output["json_path"]).exists()
    assert Path(output["markdown_path"]).exists()
    written = json.loads(Path(output["json_path"]).read_text(encoding="utf-8"))
    assert written["status"] == "publishable_with_limitations"
    markdown = Path(output["markdown_path"]).read_text(encoding="utf-8")
    assert render_proof_publication_markdown(bundle) == markdown
    assert "not an official leaderboard score" in markdown
