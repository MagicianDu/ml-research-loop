"""Archive official benchmark proof-run artifacts with hash evidence."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.benchmarks.proof_publication import (
    REQUIRED_ARTIFACTS,
    build_proof_publication_bundle,
    write_proof_publication_bundle,
)


ARCHIVE_BUNDLE_VERSION = "2026-05-06.proof-archive.v1"


def build_proof_archive_bundle(
    artifact_manifest: dict[str, Any],
    artifact_root: Path,
) -> dict[str, Any]:
    """Return a deterministic archive plan for complete proof-run artifacts."""
    artifact_root = artifact_root.expanduser().resolve()
    publication_guard = build_proof_publication_bundle(artifact_manifest, artifact_root)
    artifact_index, invalid_artifact_paths = _build_artifact_index(
        artifact_manifest,
        artifact_root,
    )
    missing_artifacts = list(publication_guard.get("missing_artifacts", []))
    status = (
        "archivable"
        if publication_guard.get("status") == "publishable_with_limitations"
        and not invalid_artifact_paths
        and not missing_artifacts
        else "blocked"
    )
    return {
        "bundle_version": ARCHIVE_BUNDLE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "evaluation_runs_launched": False,
        "official_scores_claimed": bool(artifact_manifest.get("official_scores_claimed")),
        "benchmark_name": artifact_manifest.get("benchmark_name"),
        "run_mode": artifact_manifest.get("run_mode"),
        "source_artifact_root": str(artifact_root),
        "artifact_count": len(artifact_index),
        "total_size_bytes": sum(int(entry["size_bytes"]) for entry in artifact_index),
        "missing_artifacts": missing_artifacts,
        "invalid_artifact_paths": invalid_artifact_paths,
        "artifact_index": artifact_index,
        "publication_guard": publication_guard,
        "artifact_manifest": artifact_manifest,
        "write_targets": [
            "proof-archive.json",
            "artifact-index.json",
            "artifacts/",
            "publication/proof-publication.json",
            "publication/proof-publication.md",
        ],
    }


def write_proof_archive_bundle(
    bundle: dict[str, Any],
    artifact_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Write archive metadata, copied artifacts, and publication guard files."""
    artifact_root = artifact_root.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    archive_root = output_dir / "artifacts"
    if bundle.get("status") == "archivable":
        for entry in bundle.get("artifact_index", []):
            source = _resolve_inside_root(artifact_root, entry.get("source_relative_path"))
            if source is None:
                raise ValueError(f"artifact escapes artifact_root: {entry.get('role')}")
            destination = output_dir / str(entry["archive_relative_path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    else:
        archive_root.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "proof-archive.json"
    index_path = output_dir / "artifact-index.json"
    json_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    index_path.write_text(
        json.dumps(
            {
                "artifact_count": bundle.get("artifact_count", 0),
                "total_size_bytes": bundle.get("total_size_bytes", 0),
                "artifacts": bundle.get("artifact_index", []),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    publication_payload = write_proof_publication_bundle(
        bundle.get("publication_guard", {}),
        output_dir / "publication",
    )
    return {
        "status": "written" if bundle.get("status") == "archivable" else "blocked",
        "json_path": str(json_path),
        "index_path": str(index_path),
        "artifacts_dir": str(archive_root),
        "publication_json_path": publication_payload["json_path"],
        "publication_markdown_path": publication_payload["markdown_path"],
        "bundle": {
            "status": bundle.get("status"),
            "artifact_count": bundle.get("artifact_count"),
            "official_scores_claimed": bundle.get("official_scores_claimed"),
        },
    }


def _build_artifact_index(
    artifact_manifest: dict[str, Any],
    artifact_root: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    artifacts = artifact_manifest.get("artifacts", {})
    index: list[dict[str, Any]] = []
    invalid: list[str] = []
    artifact_roles = [(role, artifacts.get(role)) for role in REQUIRED_ARTIFACTS]
    if artifact_manifest.get("score_evidence_path"):
        artifact_roles.append(("score_evidence", artifact_manifest.get("score_evidence_path")))
    for role, relative in artifact_roles:
        path = _resolve_inside_root(artifact_root, relative)
        if path is None:
            if relative:
                invalid.append(role)
            continue
        if not path.exists():
            continue
        source_relative_path = path.relative_to(artifact_root).as_posix()
        index.append({
            "role": role,
            "source_relative_path": source_relative_path,
            "archive_relative_path": f"artifacts/{source_relative_path}",
            "size_bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    return index, invalid


def _resolve_inside_root(artifact_root: Path, relative: Any) -> Path | None:
    if not relative:
        return None
    candidate = (artifact_root / str(relative)).expanduser().resolve()
    try:
        candidate.relative_to(artifact_root)
    except ValueError:
        return None
    return candidate
