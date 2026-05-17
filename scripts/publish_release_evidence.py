#!/usr/bin/env python3
"""Publish stable release evidence from local proof artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.proof_release_index import write_proof_release_index  # noqa: E402


ARCHIVE_VERSION = "2026-05-17.release-evidence.v1"
REDACTED_ROOT = "redacted_local_runtime_root"
BLOCKED_PUBLIC_CLAIMS = [
    "official leaderboard score",
    "deterministic local fixture score as official benchmark performance",
    "arbitrary paper reproduction or automatic guaranteed improvement",
]


@dataclass(frozen=True)
class ReleaseEvidenceEntry:
    name: str
    path: Path
    description: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish release proof evidence")
    parser.add_argument(
        "--real-paper-manifest",
        action="append",
        default=[],
        help="Entry as name:path:description for real-paper proof-manifest.json",
    )
    parser.add_argument(
        "--benchmark-archive",
        action="append",
        default=[],
        help="Entry as name:path:description for benchmark proof-archive.json",
    )
    parser.add_argument(
        "--fasttext-release-manifest",
        action="append",
        default=[],
        help="Entry as name:path:description for fastText release-proof-manifest.json",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "docs" / "evidence" / "proof-archives",
    )
    parser.add_argument(
        "--index-output-dir",
        type=Path,
        default=ROOT / "docs" / "evidence" / "proof-release-index",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        real_paper_entries = [
            parse_entry_spec(value) for value in args.real_paper_manifest
        ]
        benchmark_entries = [parse_entry_spec(value) for value in args.benchmark_archive]
        fasttext_entries = [
            parse_entry_spec(value) for value in args.fasttext_release_manifest
        ]
        published = [
            *[
                publish_real_paper_archive(entry, args.output_root)
                for entry in real_paper_entries
            ],
            *[
                publish_benchmark_archive(entry, args.output_root)
                for entry in benchmark_entries
            ],
            *[
                publish_fasttext_release_archive(entry, args.output_root)
                for entry in fasttext_entries
            ],
        ]
        index_entries = [
            {
                "name": item["name"],
                "proof_archive": item["proof_archive"],
                "description": item["description"],
            }
            for item in published
        ]
        index_payload = (
            write_proof_release_index(index_entries, args.index_output_dir, path_root=ROOT)
            if index_entries
            else None
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = {
        "status": "published",
        "archive_count": len(published),
        "archives": published,
        "release_index": None
        if index_payload is None
        else {
            "status": index_payload["status"],
            "entry_count": index_payload["entry_count"],
            "path": str(args.index_output_dir / "proof-release-index.json"),
        },
        "official_scores_claimed": False,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def parse_entry_spec(value: str) -> ReleaseEvidenceEntry:
    parts = value.split(":", 2)
    if len(parts) != 3 or not all(parts):
        raise ValueError("entry must use format name:path:description")
    name, path, description = parts
    if not _is_safe_name(name):
        raise ValueError("entry name must use only letters, numbers, dot, dash, underscore")
    return ReleaseEvidenceEntry(
        name=name,
        path=Path(path).expanduser(),
        description=description,
    )


def publish_real_paper_archive(
    entry: ReleaseEvidenceEntry,
    output_root: Path,
) -> dict[str, Any]:
    manifest_path = entry.path.expanduser().resolve()
    manifest = _read_json(manifest_path)
    source_root = manifest_path.parent
    output_dir = _prepare_output_dir(output_root, entry.name)
    artifacts = _copy_manifest_artifacts(
        artifact_entries=_artifact_entries(manifest),
        source_root=source_root,
        output_dir=output_dir,
    )
    metric_summary = _dict_or_empty(manifest.get("metric_summary"))
    limitations = _string_list(manifest.get("limitations"))
    artifact_manifest = {
        "manifest_version": ARCHIVE_VERSION,
        "benchmark_name": "real_paper_pilot",
        "run_mode": str(manifest.get("claim_strength") or "local_public_mini_slice"),
        "paper_id": manifest.get("paper_id"),
        "case_id": manifest.get("case_id"),
        "claim": manifest.get("claim"),
        "judge_type": "operator_artifact_review",
        "metric": metric_summary.get("metric_name") or "bounded_local_metric",
        "metric_summary": metric_summary,
        "limitations": limitations,
        "official_scores_claimed": False,
    }
    archive = {
        "bundle_version": ARCHIVE_VERSION,
        "generated_at": _now(),
        "status": "archivable",
        "official_scores_claimed": False,
        "benchmark_name": "real_paper_pilot",
        "run_mode": artifact_manifest["run_mode"],
        "source_artifact_root": REDACTED_ROOT,
        "description": entry.description,
        "artifact_count": len(artifacts),
        "total_size_bytes": sum(int(item.get("size_bytes", 0)) for item in artifacts),
        "artifact_index": artifacts,
        "artifact_manifest": artifact_manifest,
        "limitations": limitations,
        "claim_boundary": (
            "local public-slice proof only; not a full paper reproduction, "
            "not an official score, and not arbitrary automatic improvement"
        ),
    }
    publication = _publication_guard(
        benchmark_name="real_paper_pilot",
        run_mode=str(artifact_manifest["run_mode"]),
        artifact_manifest=artifact_manifest,
        allowed_public_claims=[
            "local real-paper pilot proof artifacts are available",
            "bounded metric before/after, review status, and limitations are published",
        ],
        limitations=limitations,
    )
    _write_archive_files(output_dir, archive, artifacts, publication)
    return _result(entry, output_dir, artifacts)


def publish_benchmark_archive(
    entry: ReleaseEvidenceEntry,
    output_root: Path,
) -> dict[str, Any]:
    archive_path = entry.path.expanduser().resolve()
    source_root = archive_path.parent
    archive = _read_json(archive_path)
    artifact_index = _read_json(source_root / "artifact-index.json")
    publication = _read_json(source_root / "publication" / "proof-publication.json")
    artifacts = []
    output_dir = _prepare_output_dir(output_root, entry.name)
    for artifact in _artifact_entries(artifact_index):
        relative = artifact["archive_relative_path"]
        source = _resolve_relative(source_root, relative)
        _copy_artifact(source, output_dir / relative, str(artifact["sha256"]))
        artifacts.append({
            key: value
            for key, value in artifact.items()
            if key not in {"source_absolute_path"}
        })
    sanitized_archive = _sanitize_public_payload({
        **archive,
        "description": entry.description,
        "source_artifact_root": REDACTED_ROOT,
        "artifact_count": len(artifacts),
        "artifact_index": artifacts,
        "official_scores_claimed": False,
    })
    archive_manifest = _dict_or_empty(sanitized_archive.get("artifact_manifest"))
    archive_manifest.setdefault(
        "judge_type",
        _default_benchmark_judge_type(sanitized_archive),
    )
    archive_manifest.setdefault("metric", _default_benchmark_metric(sanitized_archive))
    archive_manifest.setdefault("official_scores_claimed", False)
    sanitized_archive["artifact_manifest"] = archive_manifest
    sanitized_publication = _sanitize_public_payload({
        **publication,
        "artifact_root": REDACTED_ROOT,
        "official_scores_claimed": False,
    })
    _write_archive_files(output_dir, sanitized_archive, artifacts, sanitized_publication)
    markdown_source = source_root / "publication" / "proof-publication.md"
    if markdown_source.is_file():
        markdown_text = _sanitize_text(markdown_source.read_text(encoding="utf-8"))
        (output_dir / "publication" / "proof-publication.md").write_text(
            markdown_text,
            encoding="utf-8",
        )
    return _result(entry, output_dir, artifacts)


def publish_fasttext_release_archive(
    entry: ReleaseEvidenceEntry,
    output_root: Path,
) -> dict[str, Any]:
    """Publish a sanitized fastText full-reproduction release proof archive."""
    manifest_path = entry.path.expanduser().resolve()
    manifest = _read_json(manifest_path)
    if manifest.get("stage") != "p5_fasttext_release_proof_bundle":
        raise ValueError("fastText release manifest must use stage p5_fasttext_release_proof_bundle")
    if manifest.get("official_scores_claimed") is not False:
        raise ValueError("fastText release manifest must preserve official_scores_claimed=false")

    source_root = manifest_path.parent
    output_dir = _prepare_output_dir(output_root, entry.name)
    artifacts_dir = output_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    download = _dict_or_empty(manifest.get("download_artifact"))
    source_bundle = _path_from_manifest_value(download.get("path"), source_root)
    source_checksum = _path_from_manifest_value(download.get("checksum_file"), source_root)
    expected_source_sha = str(download.get("sha256") or "").lower()
    if not _is_sha256(expected_source_sha):
        raise ValueError("fastText release manifest download_artifact.sha256 is invalid")
    if _sha256_file(source_bundle) != expected_source_sha:
        raise ValueError(f"sha256 mismatch for release bundle: {source_bundle}")
    checksum_text = source_checksum.read_text(encoding="utf-8")
    if expected_source_sha not in checksum_text:
        raise ValueError("release checksum file does not contain manifest sha256")

    public_bundle = artifacts_dir / "release-proof-bundle.tar.gz"
    _write_sanitized_tar(source_bundle, public_bundle)
    public_bundle_sha = _sha256_file(public_bundle)
    public_checksum = artifacts_dir / "release-proof-bundle.sha256"
    public_checksum.write_text(
        f"{public_bundle_sha}  {public_bundle.name}\n",
        encoding="utf-8",
    )

    sanitized_manifest = _sanitize_public_payload(manifest)
    sanitized_manifest["download_artifact"] = {
        "path": "artifacts/release-proof-bundle.tar.gz",
        "sha256": public_bundle_sha,
        "checksum_file": "artifacts/release-proof-bundle.sha256",
        "format": "tar.gz",
        "source_bundle_sha256": expected_source_sha,
    }
    public_manifest = artifacts_dir / "release-proof-manifest.json"
    public_manifest.write_text(
        json.dumps(sanitized_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    checklist_source = source_root / "release-review-checklist.md"
    public_checklist = artifacts_dir / "release-review-checklist.md"
    if checklist_source.is_file():
        public_checklist.write_text(
            _sanitize_text(checklist_source.read_text(encoding="utf-8")),
            encoding="utf-8",
        )

    public_multi_round: Path | None = None
    multi_round_source = _optional_path_from_manifest_value(
        manifest.get("source_multi_round_report"),
        source_root,
    )
    if multi_round_source is not None and multi_round_source.is_file():
        public_multi_round = artifacts_dir / "multi-round-report.json"
        public_multi_round.write_text(
            json.dumps(
                _sanitize_public_payload(_read_json(multi_round_source)),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    artifact_paths = [
        ("release_manifest", public_manifest),
        ("release_review_checklist", public_checklist),
        ("release_download_bundle", public_bundle),
        ("release_download_checksum", public_checksum),
    ]
    if public_multi_round is not None:
        artifact_paths.append(("multi_round_report", public_multi_round))
    artifacts = [
        _artifact_record(role, path, output_dir)
        for role, path in artifact_paths
        if path.is_file()
    ]

    p4_summary = _dict_or_empty(manifest.get("p4_summary"))
    metric_summary = _dict_or_empty(p4_summary.get("metric_summary"))
    multi_round_summary = _dict_or_empty(manifest.get("multi_round_summary"))
    limitations = [
        "full AG News fastText core experiment track only; not all paper tables",
        "local proof bundle with human review; not an official leaderboard score",
        "client proposal improvement is bounded to allowlisted fastText parameters",
        "automatic improvement is not guaranteed beyond the archived run",
    ]
    artifact_manifest = {
        "manifest_version": ARCHIVE_VERSION,
        "benchmark_name": "full_reproduction_fasttext",
        "run_mode": "local_full_ag_news_fasttext",
        "paper_id": "arxiv:1607.01759",
        "paper_title": "Bag of Tricks for Efficient Text Classification",
        "judge_type": "operator_artifact_review",
        "metric": metric_summary.get("name") or "accuracy",
        "metric_summary": metric_summary,
        "multi_round_summary": multi_round_summary,
        "download_artifact": sanitized_manifest["download_artifact"],
        "limitations": limitations,
        "official_scores_claimed": False,
    }
    archive = {
        "bundle_version": ARCHIVE_VERSION,
        "generated_at": _now(),
        "status": "archivable",
        "official_scores_claimed": False,
        "benchmark_name": "full_reproduction_fasttext",
        "run_mode": "local_full_ag_news_fasttext",
        "source_artifact_root": REDACTED_ROOT,
        "description": entry.description,
        "artifact_count": len(artifacts),
        "total_size_bytes": sum(int(item.get("size_bytes", 0)) for item in artifacts),
        "artifact_index": artifacts,
        "artifact_manifest": artifact_manifest,
        "limitations": limitations,
        "claim_boundary": (
            "local fastText AG News core-track reproduction and bounded improvement "
            "proof only; not all paper tables, not official leaderboard performance, "
            "and not arbitrary autonomous research improvement"
        ),
    }
    publication = _publication_guard(
        benchmark_name="full_reproduction_fasttext",
        run_mode="local_full_ag_news_fasttext",
        artifact_manifest=artifact_manifest,
        allowed_public_claims=[
            (
                "full AG News fastText core-track baseline, bounded client proposal "
                "improvement, and review artifacts are available"
            ),
            "downloadable sanitized release proof bundle and checksum are available",
        ],
        limitations=limitations,
    )
    _write_archive_files(output_dir, archive, artifacts, publication)
    return _result(entry, output_dir, artifacts)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _artifact_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_artifacts = payload.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise ValueError("payload artifacts must be a list")
    artifacts = []
    for index, artifact in enumerate(raw_artifacts):
        if not isinstance(artifact, dict):
            raise ValueError(f"artifacts[{index}] must be an object")
        relative = artifact.get("archive_relative_path") or artifact.get("archive_path")
        sha256 = artifact.get("sha256")
        if not _is_safe_relative_path(relative):
            raise ValueError(f"artifacts[{index}] archive path is invalid")
        if not _is_sha256(sha256):
            raise ValueError(f"artifacts[{index}] sha256 is invalid")
        role = artifact.get("role")
        if not isinstance(role, str) or not role:
            raise ValueError(f"artifacts[{index}] role is required")
        artifacts.append({
            "role": role,
            "archive_relative_path": str(relative),
            "size_bytes": artifact.get("size_bytes"),
            "sha256": str(sha256).lower(),
        })
    return artifacts


def _copy_manifest_artifacts(
    *,
    artifact_entries: list[dict[str, Any]],
    source_root: Path,
    output_dir: Path,
) -> list[dict[str, Any]]:
    copied = []
    for artifact in artifact_entries:
        relative = artifact["archive_relative_path"]
        source = _resolve_relative(source_root, relative)
        destination = output_dir / relative
        digest = str(artifact["sha256"])
        _copy_artifact(source, destination, digest)
        copied.append({
            **artifact,
            "size_bytes": destination.stat().st_size,
        })
    return copied


def _copy_artifact(source: Path, destination: Path, expected_sha256: str) -> None:
    if not source.is_file():
        raise ValueError(f"missing artifact file: {source}")
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual != expected_sha256.lower():
        raise ValueError(f"sha256 mismatch for artifact: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_record(role: str, path: Path, output_dir: Path) -> dict[str, Any]:
    return {
        "role": role,
        "archive_relative_path": path.relative_to(output_dir).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _path_from_manifest_value(value: Any, source_root: Path) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("manifest path value must be a non-empty string")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = source_root / path
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"manifest path does not exist: {path}")
    return path


def _optional_path_from_manifest_value(value: Any, source_root: Path) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = source_root / path
    return path.resolve()


def _write_sanitized_tar(source_tar: Path, destination_tar: Path) -> None:
    destination_tar.parent.mkdir(parents=True, exist_ok=True)
    if destination_tar.exists():
        destination_tar.unlink()
    with tempfile.TemporaryDirectory(prefix="mlrl-public-proof-") as tmp:
        tmp_root = Path(tmp)
        with tarfile.open(source_tar, "r:gz") as source_archive:
            for member in source_archive.getmembers():
                relative = PurePosixPath(member.name)
                if (
                    relative.is_absolute()
                    or any(part in {"", ".", ".."} for part in relative.parts)
                ):
                    raise ValueError(f"unsafe tar member path: {member.name}")
                target = tmp_root / Path(*relative.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    continue
                file_obj = source_archive.extractfile(member)
                if file_obj is None:
                    continue
                data = file_obj.read()
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    target.write_bytes(data)
                else:
                    target.write_text(_sanitize_text(text), encoding="utf-8")
        with tarfile.open(destination_tar, "w:gz") as output_archive:
            for path in sorted(tmp_root.rglob("*")):
                output_archive.add(path, arcname=path.relative_to(tmp_root).as_posix())


def _write_archive_files(
    output_dir: Path,
    archive: dict[str, Any],
    artifacts: list[dict[str, Any]],
    publication: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    publication_dir = output_dir / "publication"
    publication_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "proof-archive.json").write_text(
        json.dumps(_sanitize_public_payload(archive), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "artifact-index.json").write_text(
        json.dumps(
            {
                "artifact_count": len(artifacts),
                "total_size_bytes": sum(int(item.get("size_bytes") or 0) for item in artifacts),
                "artifacts": artifacts,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (publication_dir / "proof-publication.json").write_text(
        json.dumps(_sanitize_public_payload(publication), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    markdown_path = publication_dir / "proof-publication.md"
    if not markdown_path.exists():
        markdown_path.write_text(_render_publication_markdown(publication), encoding="utf-8")


def _publication_guard(
    *,
    benchmark_name: str,
    run_mode: str,
    artifact_manifest: dict[str, Any],
    allowed_public_claims: list[str],
    limitations: list[str],
) -> dict[str, Any]:
    return {
        "bundle_version": ARCHIVE_VERSION,
        "generated_at": _now(),
        "status": "publishable_with_limitations",
        "read_only": True,
        "official_scores_claimed": False,
        "artifact_root": REDACTED_ROOT,
        "benchmark_name": benchmark_name,
        "run_mode": run_mode,
        "claim_policy": {
            "score_claim": "not_allowed",
            "requires_limitations": True,
        },
        "missing_artifacts": [],
        "invalid_artifact_paths": [],
        "allowed_public_claims": allowed_public_claims,
        "blocked_public_claims": BLOCKED_PUBLIC_CLAIMS,
        "limitations": limitations,
        "artifact_manifest": artifact_manifest,
    }


def _render_publication_markdown(publication: dict[str, Any]) -> str:
    lines = [
        "# Proof Publication Guard",
        "",
        f"- status: `{publication.get('status')}`",
        f"- benchmark_name: `{publication.get('benchmark_name')}`",
        f"- run_mode: `{publication.get('run_mode')}`",
        "- official_scores_claimed: `false`",
        "",
        "## Allowed Public Claims",
        "",
        *[f"- {claim}" for claim in _string_list(publication.get("allowed_public_claims"))],
        "",
        "## Blocked Public Claims",
        "",
        *[f"- {claim}" for claim in _string_list(publication.get("blocked_public_claims"))],
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in _string_list(publication.get("limitations"))],
    ]
    return "\n".join(lines).rstrip() + "\n"


def _result(
    entry: ReleaseEvidenceEntry,
    output_dir: Path,
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "published",
        "name": entry.name,
        "description": entry.description,
        "archive_dir": str(output_dir),
        "proof_archive": str(output_dir / "proof-archive.json"),
        "artifact_index": str(output_dir / "artifact-index.json"),
        "publication_guard": str(output_dir / "publication" / "proof-publication.json"),
        "artifact_count": len(artifacts),
        "official_scores_claimed": False,
    }


def _prepare_output_dir(output_root: Path, name: str) -> Path:
    output_dir = output_root.expanduser().resolve() / name
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _resolve_relative(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"artifact escapes root: {relative}") from exc
    return candidate


def _sanitize_public_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_public_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_public_payload(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _sanitize_text(value: str) -> str:
    sanitized = value
    project_root = str(ROOT)
    if project_root in sanitized:
        sanitized = sanitized.replace(project_root, REDACTED_ROOT)
    sanitized = re.sub(r"/Users/[^/\\\s\"]+", REDACTED_ROOT, sanitized)
    sanitized = re.sub(r"/private/[^\\\s\"]+", REDACTED_ROOT, sanitized)
    sanitized = re.sub(r"/tmp/[^\\\s\"]+", REDACTED_ROOT, sanitized)
    sanitized = re.sub(r"/var/[^\\\s\"]+", REDACTED_ROOT, sanitized)
    sanitized = sanitized.replace(f"{REDACTED_ROOT}/.demo_runs", "redacted_runtime_artifacts")
    sanitized = sanitized.replace(f"{REDACTED_ROOT}/.external", "redacted_external_toolchain")
    return sanitized


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _default_benchmark_judge_type(archive: dict[str, Any]) -> str:
    run_mode = str(archive.get("run_mode") or "").lower()
    benchmark_name = str(archive.get("benchmark_name") or "").lower()
    if "official" in run_mode and "mle" in benchmark_name:
        return "official_scorer"
    if "official" in run_mode:
        return "official_debug_harness"
    return "local_artifact_review"


def _default_benchmark_metric(archive: dict[str, Any]) -> str:
    run_mode = str(archive.get("run_mode") or "").lower()
    if "mle" in str(archive.get("benchmark_name") or "").lower():
        return "local_grade_sample_feedback"
    if "paperbench" in run_mode:
        return "rubric_review_score"
    return "artifact_completeness"


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _is_safe_name(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+", value))


def _is_safe_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in value.split("/"))
    )


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
