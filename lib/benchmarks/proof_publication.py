"""Publication guard for official benchmark proof-run artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PUBLICATION_BUNDLE_VERSION = "2026-05-06.proof-publication.v1"
REQUIRED_ARTIFACTS = [
    "command_lines",
    "resolved_config",
    "environment_manifest",
    "raw_logs",
    "raw_reports",
    "limitations_note",
]


def build_proof_publication_bundle(
    artifact_manifest: dict[str, Any],
    artifact_root: Path,
) -> dict[str, Any]:
    """Validate proof-run artifacts and return allowed public claims."""
    artifact_root = artifact_root.expanduser().resolve()
    missing_artifacts, invalid_artifact_paths = _artifact_path_issues(
        artifact_manifest,
        artifact_root,
    )
    official_scores_claimed = bool(artifact_manifest.get("official_scores_claimed"))
    score_evidence_ok = _score_evidence_exists(artifact_manifest, artifact_root)
    claim_policy = _claim_policy(official_scores_claimed, score_evidence_ok)
    status = _status(
        missing_artifacts=missing_artifacts,
        invalid_artifact_paths=invalid_artifact_paths,
        official_scores_claimed=official_scores_claimed,
        score_evidence_ok=score_evidence_ok,
    )
    return {
        "bundle_version": PUBLICATION_BUNDLE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "read_only": True,
        "official_scores_claimed": official_scores_claimed,
        "artifact_root": str(artifact_root),
        "benchmark_name": artifact_manifest.get("benchmark_name"),
        "run_mode": artifact_manifest.get("run_mode"),
        "claim_policy": claim_policy,
        "missing_artifacts": missing_artifacts,
        "invalid_artifact_paths": invalid_artifact_paths,
        "allowed_public_claims": _allowed_public_claims(status, official_scores_claimed),
        "blocked_public_claims": _blocked_public_claims(
            missing_artifacts=missing_artifacts,
            invalid_artifact_paths=invalid_artifact_paths,
            official_scores_claimed=official_scores_claimed,
            score_evidence_ok=score_evidence_ok,
        ),
        "limitations": list(artifact_manifest.get("limitations", [])),
        "artifact_manifest": artifact_manifest,
        "write_targets": ["proof-publication.json", "proof-publication.md"],
    }


def write_proof_publication_bundle(
    bundle: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Write publication guard JSON and markdown files."""
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "proof-publication.json"
    markdown_path = output_dir / "proof-publication.md"
    json_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_proof_publication_markdown(bundle), encoding="utf-8")
    return {
        "status": "written",
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "bundle": {
            "status": bundle.get("status"),
            "official_scores_claimed": bundle.get("official_scores_claimed"),
            "claim_policy": bundle.get("claim_policy"),
        },
    }


def render_proof_publication_markdown(bundle: dict[str, Any]) -> str:
    """Render publication claims and limitations."""
    lines = [
        "# Benchmark Proof Publication Guard",
        "",
        "This bundle is not an official leaderboard score report unless score evidence is present in the artifact bundle.",
        "",
        f"- status: `{bundle.get('status')}`",
        f"- benchmark_name: `{bundle.get('benchmark_name')}`",
        f"- run_mode: `{bundle.get('run_mode')}`",
        f"- official_scores_claimed: `{str(bundle.get('official_scores_claimed')).lower()}`",
        f"- score_claim_policy: `{bundle.get('claim_policy', {}).get('score_claim')}`",
        "",
        "## Allowed Public Claims",
        "",
    ]
    for claim in bundle.get("allowed_public_claims", []):
        lines.append(f"- {claim}")
    lines.extend(["", "## Blocked Public Claims", ""])
    for claim in bundle.get("blocked_public_claims", []):
        lines.append(f"- {claim}")
    lines.extend(["", "## Missing Artifacts", ""])
    missing = bundle.get("missing_artifacts", [])
    lines.extend(f"- `{item}`" for item in missing) if missing else lines.append("- none")
    lines.extend(["", "## Limitations", ""])
    limitations = bundle.get("limitations", [])
    lines.extend(f"- {item}" for item in limitations) if limitations else lines.append("- none")
    if not bundle.get("official_scores_claimed"):
        lines.extend(["", "This is not an official leaderboard score."])
    return "\n".join(lines).rstrip() + "\n"


def _artifact_path_issues(
    artifact_manifest: dict[str, Any],
    artifact_root: Path,
) -> tuple[list[str], list[str]]:
    artifacts = artifact_manifest.get("artifacts", {})
    missing: list[str] = []
    invalid: list[str] = []
    for key in REQUIRED_ARTIFACTS:
        relative = artifacts.get(key)
        path = _resolve_inside_root(artifact_root, relative)
        if path is None:
            missing.append(key)
            if relative:
                invalid.append(key)
            continue
        if not path.exists():
            missing.append(key)
    return missing, invalid


def _score_evidence_exists(artifact_manifest: dict[str, Any], artifact_root: Path) -> bool:
    relative = artifact_manifest.get("score_evidence_path")
    path = _resolve_inside_root(artifact_root, relative)
    return bool(path and path.exists())


def _resolve_inside_root(artifact_root: Path, relative: Any) -> Path | None:
    if not relative:
        return None
    candidate = (artifact_root / str(relative)).expanduser().resolve()
    try:
        candidate.relative_to(artifact_root)
    except ValueError:
        return None
    return candidate


def _claim_policy(official_scores_claimed: bool, score_evidence_ok: bool) -> dict[str, Any]:
    if official_scores_claimed and score_evidence_ok:
        return {
            "score_claim": "allowed_with_evidence",
            "requires_limitations": True,
        }
    if official_scores_claimed:
        return {
            "score_claim": "blocked_missing_evidence",
            "requires_limitations": True,
        }
    return {
        "score_claim": "not_allowed",
        "requires_limitations": True,
    }


def _status(
    *,
    missing_artifacts: list[str],
    invalid_artifact_paths: list[str],
    official_scores_claimed: bool,
    score_evidence_ok: bool,
) -> str:
    if missing_artifacts or invalid_artifact_paths:
        return "blocked"
    if official_scores_claimed and not score_evidence_ok:
        return "blocked"
    return "publishable_with_limitations"


def _allowed_public_claims(status: str, official_scores_claimed: bool) -> list[str]:
    if status == "blocked":
        return []
    claims = [
        "debug proof-run artifacts are available",
        "commands, config, environment, logs, reports, and limitations are published",
    ]
    if official_scores_claimed:
        claims.append("official score evidence is included for review")
    return claims


def _blocked_public_claims(
    *,
    missing_artifacts: list[str],
    invalid_artifact_paths: list[str],
    official_scores_claimed: bool,
    score_evidence_ok: bool,
) -> list[str]:
    blocked = [
        "official leaderboard score" if not official_scores_claimed else "unqualified score promotion",
        "deterministic local fixture score as official benchmark performance",
    ]
    if missing_artifacts:
        blocked.append("artifact completeness")
    if invalid_artifact_paths:
        blocked.append("artifact path confinement")
    if official_scores_claimed and not score_evidence_ok:
        blocked.append("official score claim")
        blocked.append("official score claim without score evidence")
    return blocked
