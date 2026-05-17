"""Write a release index for proof archives without promoting score claims."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = "2026-05-12.proof-release-index.v1"
PROOF_ARCHIVE_FILENAME = "proof-archive.json"
REQUIRED_BLOCKED_CLAIMS = [
    "official leaderboard score",
    "deterministic local fixture score as official benchmark performance",
]
ALLOWED_SCORE_CLAIMS = {
    "allowed_with_evidence",
    "blocked_missing_evidence",
    "not_allowed",
}


def parse_entry_spec(value: str) -> dict[str, str]:
    """Parse CLI entry format: name:path:description."""
    parts = value.split(":", 2)
    if len(parts) != 3 or not all(parts):
        raise ValueError("entry must use format name:path:description")
    name, proof_archive, description = parts
    return {
        "name": name,
        "proof_archive": proof_archive,
        "description": description,
    }


def write_proof_release_index(
    entries: list[dict[str, str]],
    output_dir: Path,
    *,
    path_root: Path | None = None,
) -> dict[str, Any]:
    """Write JSON and Markdown indexes for proof archive metadata."""
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    indexed_entries = [_index_entry(entry, path_root=path_root) for entry in entries]
    limitations = _unique(
        limitation
        for entry in indexed_entries
        for limitation in entry.get("limitations", [])
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "written",
        "official_scores_claimed": False,
        "entry_count": len(indexed_entries),
        "entries": indexed_entries,
        "limitations": limitations,
    }

    json_path = output_dir / "proof-release-index.json"
    markdown_path = output_dir / "proof-release-index.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_proof_release_index_markdown(payload), encoding="utf-8")
    return payload


def render_proof_release_index_markdown(payload: dict[str, Any]) -> str:
    """Render release index evidence and claim boundaries."""
    lines = [
        "# Proof Release Evidence Index",
        "",
        f"schema_version: `{payload.get('schema_version')}`",
        "official_scores_claimed: `false`",
        f"entry_count: `{payload.get('entry_count')}`",
        "",
        "This index records local proof archive evidence. It does not promote local proof runs as official benchmark results.",
    ]
    for entry in payload.get("entries", []):
        lines.extend(
            [
                "",
                f"## {entry.get('name')}",
                "",
                f"- description: {entry.get('description')}",
                f"- proof_archive: `{entry.get('proof_archive')}`",
                f"- artifact_index: `{entry.get('artifact_index')}`",
                f"- publication_guard: `{entry.get('publication_guard')}`",
                f"- status: `{entry.get('status')}`",
                f"- publication_status: `{entry.get('publication_status')}`",
                f"- benchmark_name: `{entry.get('benchmark_name')}`",
                f"- run_mode: `{entry.get('run_mode')}`",
                f"- judge_type: `{entry.get('judge_type')}`",
                f"- metric: `{entry.get('metric')}`",
                "- official_scores_claimed: `false`",
                "",
                "### Allowed Public Claims",
                "",
            ]
        )
        _append_list(lines, entry.get("allowed_public_claims", []))
        lines.extend(["", "### Blocked Public Claims", ""])
        _append_list(lines, entry.get("blocked_public_claims", []))
        lines.extend(["", "### Artifact SHA256 Summary", ""])
        artifacts = entry.get("artifacts", [])
        if artifacts:
            for artifact in artifacts:
                role = artifact.get("role", "artifact")
                relative = artifact.get("archive_relative_path") or artifact.get(
                    "source_relative_path",
                    "",
                )
                sha256 = artifact.get("sha256", "")
                lines.append(f"- `{role}` `{relative}` sha256: `{sha256}`")
        else:
            lines.append("- none")
        lines.extend(["", "### Limitations", ""])
        _append_list(lines, entry.get("limitations", []))
    lines.extend(["", "## Global Limitations", ""])
    _append_list(lines, payload.get("limitations", []))
    return "\n".join(lines).rstrip() + "\n"


def _index_entry(
    entry: dict[str, str],
    *,
    path_root: Path | None = None,
) -> dict[str, Any]:
    proof_archive = Path(entry["proof_archive"]).expanduser().resolve()
    if proof_archive.name != PROOF_ARCHIVE_FILENAME:
        raise ValueError(f"proof archive path must point to {PROOF_ARCHIVE_FILENAME}")
    archive_root = proof_archive.parent
    artifact_index_path = archive_root / "artifact-index.json"
    publication_guard_path = archive_root / "publication" / "proof-publication.json"
    for required_path in (proof_archive, artifact_index_path, publication_guard_path):
        if not required_path.exists():
            raise ValueError(f"missing required proof archive file: {required_path.name}")

    archive = _read_json(proof_archive)
    artifact_index = _read_json(artifact_index_path)
    publication_guard = _read_json(publication_guard_path)
    artifacts = _validate_artifact_index(artifact_index)
    _validate_archive(archive, len(artifacts))
    _validate_publication_guard(publication_guard)
    artifact_manifest = archive.get("artifact_manifest", {})
    if not isinstance(artifact_manifest, dict):
        artifact_manifest = {}

    return {
        "name": entry["name"],
        "description": entry["description"],
        "proof_archive": _display_path(proof_archive, path_root),
        "artifact_index": _display_path(artifact_index_path, path_root),
        "publication_guard": _display_path(publication_guard_path, path_root),
        "status": archive.get("status"),
        "publication_status": publication_guard.get("status"),
        "benchmark_name": archive.get("benchmark_name"),
        "run_mode": archive.get("run_mode"),
        "judge_type": artifact_manifest.get("judge_type"),
        "metric": artifact_manifest.get("metric") or artifact_manifest.get("metric_name"),
        "official_scores_claimed": False,
        "source_official_scores_claimed": bool(
            archive.get("official_scores_claimed")
            or publication_guard.get("official_scores_claimed")
            or artifact_manifest.get("official_scores_claimed")
        ),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "allowed_public_claims": _string_list(publication_guard.get("allowed_public_claims")),
        "blocked_public_claims": _blocked_claims(publication_guard),
        "limitations": _limitations(archive, publication_guard, artifact_manifest),
    }


def _display_path(path: Path, path_root: Path | None) -> str:
    if path_root is None:
        return str(path)
    root = path_root.expanduser().resolve()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _validate_archive(archive: dict[str, Any], artifact_count: int) -> None:
    for field in ("status", "benchmark_name", "run_mode"):
        if not isinstance(archive.get(field), str) or not archive.get(field):
            raise ValueError(f"proof-archive.json {field} is required")
    if not isinstance(archive.get("official_scores_claimed"), bool):
        raise ValueError("proof-archive.json official_scores_claimed must be a boolean")
    archive_count = archive.get("artifact_count")
    if not isinstance(archive_count, int) or isinstance(archive_count, bool):
        raise ValueError("proof-archive.json artifact_count must be an integer")
    if archive_count != artifact_count:
        raise ValueError("proof-archive.json artifact_count must match artifact-index.json")
    artifact_manifest = archive.get("artifact_manifest")
    if not isinstance(artifact_manifest, dict):
        raise ValueError("proof-archive.json artifact_manifest must be an object")
    if not isinstance(artifact_manifest.get("judge_type"), str) or not artifact_manifest.get(
        "judge_type",
    ):
        raise ValueError("proof-archive.json artifact_manifest.judge_type is required")
    metric = artifact_manifest.get("metric") or artifact_manifest.get("metric_name")
    if not isinstance(metric, str) or not metric:
        raise ValueError("proof-archive.json artifact_manifest metric is required")


def _validate_artifact_index(artifact_index: dict[str, Any]) -> list[dict[str, Any]]:
    artifact_count = artifact_index.get("artifact_count")
    artifacts = artifact_index.get("artifacts")
    if not isinstance(artifact_count, int) or isinstance(artifact_count, bool):
        raise ValueError("artifact-index.json artifact_count must be an integer")
    if not isinstance(artifacts, list):
        raise ValueError("artifact-index.json artifacts must be a list")
    if artifact_count != len(artifacts):
        raise ValueError("artifact-index.json artifact_count must match artifacts length")
    validated: list[dict[str, Any]] = []
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise ValueError(f"artifact-index.json artifacts[{index}] must be an object")
        role = artifact.get("role")
        relative_path = artifact.get("archive_relative_path")
        sha256 = artifact.get("sha256")
        size_bytes = artifact.get("size_bytes")
        if not isinstance(role, str) or not role:
            raise ValueError(f"artifact-index.json artifacts[{index}].role is required")
        if not _is_safe_archive_relative_path(relative_path):
            raise ValueError(
                f"artifact-index.json artifacts[{index}].archive_relative_path is invalid"
            )
        if not _is_sha256(sha256):
            raise ValueError(
                f"artifact-index.json artifacts[{index}].sha256 must be a SHA-256 hex digest"
            )
        if size_bytes is not None and (
            not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0
        ):
            raise ValueError(
                f"artifact-index.json artifacts[{index}].size_bytes must be a non-negative integer"
            )
        validated.append(artifact)
    return validated


def _validate_publication_guard(publication_guard: dict[str, Any]) -> None:
    if not isinstance(publication_guard.get("status"), str) or not publication_guard.get("status"):
        raise ValueError("proof-publication.json status is required")
    if not isinstance(publication_guard.get("official_scores_claimed"), bool):
        raise ValueError("proof-publication.json official_scores_claimed must be a boolean")
    claim_policy = publication_guard.get("claim_policy")
    if not isinstance(claim_policy, dict):
        raise ValueError("proof-publication.json claim_policy must be an object")
    if claim_policy.get("score_claim") not in ALLOWED_SCORE_CLAIMS:
        raise ValueError("proof-publication.json claim_policy.score_claim is required")
    if not isinstance(claim_policy.get("requires_limitations"), bool):
        raise ValueError(
            "proof-publication.json claim_policy.requires_limitations must be a boolean"
        )
    for field in ("allowed_public_claims", "blocked_public_claims"):
        claims = publication_guard.get(field)
        if not isinstance(claims, list) or not all(isinstance(item, str) for item in claims):
            raise ValueError(f"proof-publication.json {field} must be a list of strings")
    missing_claims = [
        claim
        for claim in REQUIRED_BLOCKED_CLAIMS
        if claim not in publication_guard["blocked_public_claims"]
    ]
    if missing_claims:
        raise ValueError("proof-publication.json blocked_public_claims missing required boundaries")


def _is_safe_archive_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if "\\" in value:
        return False
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def _blocked_claims(publication_guard: dict[str, Any]) -> list[str]:
    blocked = _string_list(publication_guard.get("blocked_public_claims"))
    return blocked


def _limitations(
    archive: dict[str, Any],
    publication_guard: dict[str, Any],
    artifact_manifest: dict[str, Any],
) -> list[str]:
    return _unique(
        [
            *_string_list(archive.get("limitations")),
            *_string_list(artifact_manifest.get("limitations")),
            *_string_list(publication_guard.get("limitations")),
            "local proof is not an official benchmark result",
        ]
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _unique(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _append_list(lines: list[str], values: list[str]) -> None:
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- none")
