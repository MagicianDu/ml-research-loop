#!/usr/bin/env python3
"""Validate a fresh public checkout of ml-research-loop."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


DEFAULT_REPO_URL = "https://github.com/MagicianDu/ml-research-loop.git"


@dataclass(frozen=True)
class FreshCommand:
    label: str
    argv: list[str]
    cwd: Path
    timeout_seconds: int


@dataclass(frozen=True)
class FreshResult:
    label: str
    returncode: int
    duration_seconds: float
    stdout: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a fresh public checkout")
    parser.add_argument(
        "--stable-readiness",
        action="store_true",
        help="Report beta/stable release readiness without cloning or installing.",
    )
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--ref", default="main")
    parser.add_argument("--workdir", type=Path, default=None)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--keep-workdir", action="store_true")
    parser.add_argument(
        "--skip-golden-path",
        action="store_true",
        help="Skip the bounded MCP golden-path demo.",
    )
    parser.add_argument(
        "--skip-full-release-check",
        action="store_true",
        help="Reserved for launch scripts; this verifier already runs the shorter fresh-check path.",
    )
    return parser.parse_args()


def build_stable_readiness_report(project_root: Path) -> dict[str, object]:
    root = project_root.expanduser().resolve()
    texts = {
        "release_notes": _read_text(root / "docs" / "release-notes.md"),
        "release_checklist": _read_text(root / "docs" / "release-checklist.md"),
        "client_matrix": _read_text(root / "docs" / "client-compatibility-matrix.md"),
        "proof_matrix": _read_text(
            root / "docs" / "evidence" / "autonomous-product-proof-matrix-cn.md"
        ),
        "pilot_guide": _read_text(root / "docs" / "institution-pilot-guide-cn.md"),
    }

    preview_blockers = _preview_blockers(texts)
    beta_readiness = _beta_gate_checks(texts)
    beta_blockers = _beta_blockers(texts)
    release_artifacts = build_release_artifact_report(root)
    stable_blockers = _stable_blockers(
        root=root,
        texts=texts,
        release_artifacts=release_artifacts,
    )
    if preview_blockers:
        status = "blocked"
    elif beta_blockers:
        status = "preview_ready"
    elif stable_blockers:
        status = "beta_ready"
    else:
        status = "stable_ready"
    return {
        "status": status,
        "release_boundary": {
            "preview": {
                "status": "blocked" if preview_blockers else "ready",
                "blockers": preview_blockers,
            },
            "beta": {
                "status": "blocked" if beta_blockers else "ready",
                "blockers": beta_blockers,
            },
            "stable": {
                "status": "blocked" if stable_blockers else "ready",
                "blockers": stable_blockers,
            },
        },
        "beta_readiness": beta_readiness,
        "beta_blockers": beta_blockers,
        "stable_blockers": stable_blockers,
        "release_artifacts": release_artifacts,
    }


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _preview_blockers(texts: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    if not texts["release_notes"]:
        blockers.append("missing_release_notes")
    if not texts["release_checklist"]:
        blockers.append("missing_release_checklist")
    return blockers


def _beta_blockers(texts: dict[str, str]) -> list[str]:
    return [
        str(gate["blocker"])
        for gate in _beta_gate_checks(texts)
        if gate["status"] == "blocked" and gate.get("blocker")
    ]


def _beta_gate_checks(texts: dict[str, str]) -> list[dict[str, object]]:
    combined = "\n".join(texts.values()).lower()
    release_notes = texts["release_notes"].lower()
    return [
        _gate_check(
            gate="release_gate",
            ready="scripts/release_check.py" in combined and "beta release gate" in combined,
            blocker="missing_release_gate",
            evidence="scripts/release_check.py --json",
            next_action="Run the release gate and keep the command documented before beta.",
        ),
        _gate_check(
            gate="client_acceptance",
            ready="mcp_client_acceptance.py" in combined or "mcp client acceptance" in combined,
            blocker="missing_mcp_client_acceptance",
            evidence="scripts/mcp_client_acceptance.py",
            next_action="Run MCP client acceptance and document the result.",
        ),
        _gate_check(
            gate="skills_dry_run",
            ready="init-skills" in combined and "dry-run" in combined,
            blocker="missing_skills_install_dry_run",
            evidence="ml-loop init-skills --dry-run",
            next_action="Run Codex and Claude skills dry-run before beta.",
        ),
        _gate_check(
            gate="fresh_checkout",
            ready="fresh_checkout_check.py" in combined or "clean checkout install" in combined,
            blocker="missing_clean_checkout_install",
            evidence="scripts/fresh_checkout_check.py",
            next_action="Validate install from a clean checkout.",
        ),
        _gate_check(
            gate="bounded_demo",
            ready="mcp_golden_path.py" in combined or "bounded demo" in combined,
            blocker="missing_bounded_demo",
            evidence="scripts/mcp_golden_path.py",
            next_action="Run the bounded MCP golden-path demo.",
        ),
        _gate_check(
            gate="autonomous_research_demo",
            ready=(
                "autonomous_research_demo.py" in combined
                or "autonomous research demo" in combined
            ),
            blocker="missing_autonomous_research_demo",
            evidence="scripts/autonomous_research_demo.py",
            next_action="Run the autonomous research demo and keep limitations explicit.",
        ),
        _gate_check(
            gate="proof_matrix",
            ready=_proof_matrix_entry_count(texts["proof_matrix"]) >= 3,
            blocker="missing_proof_matrix_entries",
            evidence="docs/evidence/autonomous-product-proof-matrix-cn.md",
            next_action="Add at least three capability rows to the proof matrix.",
        ),
        _gate_check(
            gate="pilot_guide",
            ready=_pilot_guide_complete(texts["pilot_guide"]),
            blocker="missing_pilot_guide",
            evidence="docs/institution-pilot-guide-cn.md",
            next_action="Document install, feedback, privacy/resource, and sign-off boundaries.",
        ),
        _gate_check(
            gate="known_limitations",
            ready="known limitations" in release_notes,
            blocker="missing_known_limitations",
            evidence="docs/release-notes.md#known-limitations",
            next_action="Keep public known limitations visible in release notes.",
        ),
        {
            "gate": "optional_cognee_adapter",
            "status": "not_required",
            "blocker": None,
            "evidence": "Cognee is an optional memory adapter, not a beta release gate.",
            "next_action": "Run optional live-smoke evidence separately when configured.",
        },
    ]


def _gate_check(
    *,
    gate: str,
    ready: bool,
    blocker: str,
    evidence: str,
    next_action: str,
) -> dict[str, object]:
    return {
        "gate": gate,
        "status": "ready" if ready else "blocked",
        "blocker": None if ready else blocker,
        "evidence": evidence,
        "next_action": None if ready else next_action,
    }


def _stable_blockers(
    *,
    root: Path,
    texts: dict[str, str],
    release_artifacts: dict[str, object] | None = None,
) -> list[str]:
    blockers: list[str] = []
    combined = "\n".join(texts.values()).lower()
    if "preview.v" in combined or "frozen contract" not in combined:
        blockers.append("missing_frozen_contract_versions")
    if not _client_matrix_covers_required_clients(texts["client_matrix"]):
        blockers.append("missing_client_compatibility_matrix")
    if _external_pilot_feedback_count(root) < 3:
        blockers.append("missing_external_pilot_feedback")
    if len(_real_task_proof_archives(root)) < 2:
        blockers.append("missing_real_task_proof_archives")
    if not _has_official_debug_benchmark_proof(root):
        blockers.append("missing_official_debug_benchmark_proof")
    if not _public_claims_mapped(root, texts["proof_matrix"]):
        blockers.append("missing_public_claim_proof_mapping")
    artifact_report = release_artifacts or build_release_artifact_report(root)
    artifact_status = artifact_report["status"]
    if artifact_status == "missing":
        blockers.append("missing_downloadable_release_artifact")
    elif artifact_status in {"hash_missing", "hash_mismatch"}:
        blockers.append("missing_release_artifact_hash")
    return blockers


def _proof_matrix_entry_count(markdown: str) -> int:
    rows = [
        line
        for line in markdown.splitlines()
        if line.strip().startswith("|")
        and "---" not in line
        and "Capability" not in line
        and len(line.split("|")) >= 5
    ]
    return len(rows)


def _pilot_guide_complete(markdown: str) -> bool:
    lowered = markdown.lower()
    marker_groups = [
        ("pilot", "试用"),
        ("feedback", "反馈"),
        ("privacy", "隐私", "数据安全"),
        ("resource", "资源", "耗时", "机器"),
    ]
    return all(any(marker in lowered for marker in group) for group in marker_groups)


def _client_matrix_covers_required_clients(markdown: str) -> bool:
    lowered = markdown.lower()
    return all(client in lowered for client in ["codex", "claude code", "claude desktop"])


def _external_pilot_feedback_count(root: Path) -> int:
    feedback_roots = [
        root / "examples" / "pilot" / "feedback",
        root / "docs" / "pilot-feedback",
    ]
    count = 0
    for feedback_root in feedback_roots:
        if not feedback_root.exists():
            continue
        for path in feedback_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".json", ".md", ".yml", ".yaml"}:
                text = _read_text(path).lower()
                if "external" in text or "pilot" in text:
                    count += 1
    return count


def _real_task_proof_archives(root: Path) -> list[Path]:
    archives = []
    for archive in _proof_archive_candidates(root):
        if _is_complete_proof_archive(archive):
            archives.append(archive)
    return archives


def _proof_archive_candidates(root: Path) -> list[Path]:
    search_roots = [
        root / "docs" / "evidence" / "proof-archives",
        root / "release" / "evidence",
        root / "dist" / "evidence",
    ]
    archives: list[Path] = []
    for search_root in search_roots:
        if search_root.exists():
            archives.extend(search_root.rglob("proof-archive.json"))
    return archives


def _is_complete_proof_archive(archive_path: Path) -> bool:
    artifact_index_path = archive_path.parent / "artifact-index.json"
    publication_guard_path = archive_path.parent / "publication" / "proof-publication.json"
    if not artifact_index_path.exists() or not publication_guard_path.exists():
        return False
    archive = _read_json_object(archive_path)
    artifact_index = _read_json_object(artifact_index_path)
    publication_guard = _read_json_object(publication_guard_path)
    artifacts = artifact_index.get("artifacts")
    return (
        bool(archive)
        and bool(publication_guard.get("blocked_public_claims"))
        and isinstance(artifacts, list)
        and len(artifacts) > 0
        and all(
            _artifact_file_matches_hash(archive_path.parent, artifact)
            for artifact in artifacts
        )
    )


def _has_official_debug_benchmark_proof(root: Path) -> bool:
    return any(
        _is_official_debug_proof_archive(archive) for archive in _proof_archive_candidates(root)
    )


def _is_official_debug_proof_archive(archive_path: Path) -> bool:
    if not _is_complete_proof_archive(archive_path):
        return False
    archive = _read_json_object(archive_path)
    artifact_index = _read_json_object(archive_path.parent / "artifact-index.json")
    artifact_manifest = archive.get("artifact_manifest", {})
    if not isinstance(artifact_manifest, dict):
        artifact_manifest = {}
    run_mode = str(archive.get("run_mode") or artifact_manifest.get("run_mode") or "").lower()
    judge_type = str(
        archive.get("judge_type") or artifact_manifest.get("judge_type") or ""
    ).lower()
    benchmark_name = str(
        archive.get("benchmark_name") or artifact_manifest.get("benchmark_name") or ""
    ).lower()
    artifacts = artifact_index.get("artifacts", [])
    roles = {
        str(artifact.get("role", "")).lower()
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    required_roles = {
        "command_lines",
        "resolved_config",
        "environment_manifest",
        "raw_logs",
        "raw_reports",
        "limitations_note",
    }
    return (
        bool(benchmark_name)
        and ("official" in run_mode or "official" in judge_type)
        and required_roles.issubset(roles)
    )


def _artifact_has_hash_evidence(artifact: object) -> bool:
    if not isinstance(artifact, dict):
        return False
    sha256 = artifact.get("sha256")
    return (
        isinstance(artifact.get("role"), str)
        and isinstance(artifact.get("archive_relative_path"), str)
        and isinstance(sha256, str)
        and len(sha256) == 64
        and all(character in "0123456789abcdefABCDEF" for character in sha256)
    )


def _artifact_file_matches_hash(archive_root: Path, artifact: object) -> bool:
    if not _artifact_has_hash_evidence(artifact) or not isinstance(artifact, dict):
        return False
    relative = artifact.get("archive_relative_path")
    if not _is_safe_relative_path(relative):
        return False
    artifact_path = (archive_root / str(relative)).resolve()
    try:
        artifact_path.relative_to(archive_root.resolve())
    except ValueError:
        return False
    if not artifact_path.is_file():
        return False
    actual_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    return actual_hash == str(artifact["sha256"]).lower()


def _is_safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in value.split("/"))
    )


def _public_claims_mapped(root: Path, proof_matrix: str) -> bool:
    claim_map = _read_json_object(root / "docs" / "evidence" / "public-claims-map.json")
    claims = claim_map.get("public_claims")
    if not isinstance(claims, list) or not claims:
        return False
    required_fields = {
        "claim_id",
        "public_claim",
        "proof_matrix_entry",
        "evidence",
        "claim_boundary",
    }
    for claim in claims:
        if not isinstance(claim, dict):
            return False
        if any(
            not isinstance(claim.get(field), str) or not claim[field]
            for field in required_fields
        ):
            return False
        if str(claim["proof_matrix_entry"]) not in proof_matrix:
            return False
        evidence_path = _resolve_release_evidence_path(root, str(claim["evidence"]))
        if evidence_path is None or not evidence_path.is_file():
            return False
    return True


def _resolve_release_evidence_path(root: Path, relative_path: str) -> Path | None:
    if not _is_safe_relative_path(relative_path):
        return None
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_release_artifact_report(root: Path) -> dict[str, object]:
    release_root = root.expanduser().resolve()
    dist = release_root / "dist"
    wheels = sorted(dist.glob("*.whl")) if dist.exists() else []
    sdists = sorted(dist.glob("*.tar.gz")) if dist.exists() else []
    artifacts = sorted([*wheels, *sdists])
    hash_files = _release_hash_files(dist)
    missing: list[str] = []
    if not wheels:
        missing.append("dist/*.whl")
    if not sdists:
        missing.append("dist/*.tar.gz")
    if not hash_files:
        missing.append("dist/SHA256SUMS or dist/*.sha256")

    artifact_names = [_relative_display(release_root, path) for path in artifacts]
    hash_file_names = [_relative_display(release_root, path) for path in hash_files]
    hash_mismatches = _release_artifact_hash_mismatches(
        release_root=release_root,
        dist=dist,
        artifacts=artifacts,
        hash_files=hash_files,
    )
    verified = [
        name
        for name in artifact_names
        if not any(mismatch["artifact"] == name for mismatch in hash_mismatches)
    ]
    if not artifacts:
        status = "missing"
    elif not hash_files:
        status = "hash_missing"
    elif len(wheels) == 0 or len(sdists) == 0:
        status = "missing"
    elif hash_mismatches:
        status = "hash_mismatch"
    else:
        status = "verified"

    return {
        "status": status,
        "artifacts": artifact_names,
        "hash_files": hash_file_names,
        "verified": verified if status == "verified" else [],
        "missing": missing,
        "hash_mismatches": hash_mismatches,
        "next_action": _release_artifact_next_action(status),
    }


def _has_downloadable_release_artifact(root: Path) -> bool:
    return build_release_artifact_report(root)["status"] == "verified"


def _release_hash_files(dist: Path) -> list[Path]:
    if not dist.exists():
        return []
    hash_files: list[Path] = []
    sums = dist / "SHA256SUMS"
    if sums.is_file():
        hash_files.append(sums)
    hash_files.extend(sorted(dist.glob("*.sha256")))
    return sorted(hash_files)


def _release_artifact_hash_mismatches(
    *,
    release_root: Path,
    dist: Path,
    artifacts: list[Path],
    hash_files: list[Path],
) -> list[dict[str, str]]:
    if not artifacts or not hash_files:
        return []
    expected_hashes = _read_release_hash_entries(dist, hash_files)
    mismatches: list[dict[str, str]] = []
    for artifact in artifacts:
        display = _relative_display(release_root, artifact)
        dist_relative = artifact.relative_to(dist).as_posix()
        expected = (
            expected_hashes.get(display)
            or expected_hashes.get(dist_relative)
            or expected_hashes.get(artifact.name)
        )
        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if expected is None:
            mismatches.append({
                "artifact": display,
                "reason": "missing_hash_entry",
                "expected_sha256": "",
                "actual_sha256": actual,
            })
        elif expected.lower() != actual:
            mismatches.append({
                "artifact": display,
                "reason": "sha256_mismatch",
                "expected_sha256": expected.lower(),
                "actual_sha256": actual,
            })
    return mismatches


def _read_release_hash_entries(dist: Path, hash_files: list[Path]) -> dict[str, str]:
    entries: dict[str, str] = {}
    for hash_file in hash_files:
        for line in _read_text(hash_file).splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()
            digest = parts[0].lower()
            if not _is_sha256(digest):
                continue
            if len(parts) >= 2:
                artifact_name = parts[-1].lstrip("*")
                entries[artifact_name] = digest
                entries[f"dist/{artifact_name}"] = digest
                continue
            if hash_file.suffix == ".sha256":
                artifact_name = hash_file.name[: -len(".sha256")]
                if artifact_name:
                    entries[artifact_name] = digest
                    entries[f"dist/{artifact_name}"] = digest
                try:
                    sidecar_relative = hash_file.relative_to(dist).as_posix()
                except ValueError:
                    sidecar_relative = hash_file.name
                if sidecar_relative.endswith(".sha256"):
                    entries[sidecar_relative[: -len(".sha256")]] = digest
    return entries


def _is_sha256(value: str) -> bool:
    return (
        len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def _relative_display(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _release_artifact_next_action(status: object) -> str | None:
    if status == "verified":
        return None
    if status == "hash_missing":
        return (
            "Write SHA-256 verification, for example: "
            "python3 -m build && shasum -a 256 dist/* > dist/SHA256SUMS; rerun readiness."
        )
    if status == "hash_mismatch":
        return (
            "Regenerate SHA-256 sidecars or SHA256SUMS from the final artifact bytes; "
            "do not reuse stale hashes."
        )
    return (
        "Build the release wheel and sdist first, for example: "
        "python3 -m build; then write SHA-256 verification and rerun readiness."
    )


def make_workdir(workdir: Path | None) -> Path:
    if workdir is not None:
        root = workdir.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root
    return Path(tempfile.gettempdir()) / f"ml-research-loop-fresh-{uuid.uuid4().hex[:8]}"


def build_commands(
    *,
    repo_url: str,
    ref: str,
    python: str,
    workdir: Path,
    skip_golden_path: bool,
) -> tuple[Path, list[FreshCommand]]:
    checkout = workdir / "ml-research-loop"
    venv_python = checkout / ".venv" / "bin" / "python"
    ml_loop = checkout / ".venv" / "bin" / "ml-loop"
    runtime_root = checkout / ".fresh-check" / "runtime"
    skill_root = checkout / ".fresh-check" / "skills"
    commands = [
        FreshCommand(
            label="git-clone",
            argv=["git", "clone", "--depth", "1", "--branch", ref, repo_url, str(checkout)],
            cwd=workdir,
            timeout_seconds=120,
        ),
        FreshCommand(
            label="create-venv",
            argv=[python, "-m", "venv", ".venv"],
            cwd=checkout,
            timeout_seconds=120,
        ),
        FreshCommand(
            label="install",
            argv=[str(venv_python), "-m", "pip", "install", "-e", ".[dev]"],
            cwd=checkout,
            timeout_seconds=900,
        ),
        FreshCommand(
            label="mcp-client-acceptance",
            argv=[
                str(venv_python),
                "scripts/mcp_client_acceptance.py",
                "--python",
                str(venv_python),
                "--project-root",
                str(checkout),
            ],
            cwd=checkout,
            timeout_seconds=60,
        ),
        FreshCommand(
            label="render-codex-config",
            argv=[
                str(ml_loop),
                "init-mcp-config",
                "--client",
                "codex",
                "--project-root",
                str(checkout),
                "--python",
                str(venv_python),
            ],
            cwd=checkout,
            timeout_seconds=30,
        ),
        FreshCommand(
            label="skills-dry-run",
            argv=[
                str(ml_loop),
                "init-skills",
                "--client",
                "codex",
                "--project-root",
                str(checkout),
                "--target-root",
                str(skill_root),
                "--dry-run",
            ],
            cwd=checkout,
            timeout_seconds=30,
        ),
    ]
    if not skip_golden_path:
        commands.append(
            FreshCommand(
                label="mcp-golden-path",
                argv=[
                    str(venv_python),
                    "scripts/mcp_golden_path.py",
                    "--runtime-root",
                    str(runtime_root),
                    "--max-experiments",
                    "1",
                    "--experiment-duration",
                    "30",
                ],
                cwd=checkout,
                timeout_seconds=180,
            )
        )
    return checkout, commands


def run_command(command: FreshCommand) -> FreshResult:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command.argv,
            cwd=command.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=command.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _timeout_stdout(command=command, exc=exc)
        return FreshResult(
            label=command.label,
            returncode=124,
            duration_seconds=round(time.monotonic() - start, 3),
            stdout=stdout,
        )
    return FreshResult(
        label=command.label,
        returncode=proc.returncode,
        duration_seconds=round(time.monotonic() - start, 3),
        stdout=proc.stdout,
    )


def _timeout_stdout(command: FreshCommand, exc: subprocess.TimeoutExpired) -> str:
    captured = exc.stdout or exc.output or ""
    if isinstance(captured, bytes):
        captured = captured.decode("utf-8", errors="replace")
    timeout = exc.timeout or command.timeout_seconds
    return "\n".join([
        f"{command.label} timed out after {timeout:g} seconds.",
        f"Command: {' '.join(command.argv)}",
        str(captured),
    ]).strip()


def render_summary(
    *,
    repo_url: str,
    ref: str,
    checkout: Path,
    results: list[FreshResult],
) -> str:
    payload = {
        "status": "passed" if all(result.returncode == 0 for result in results) else "failed",
        "repo_url": repo_url,
        "ref": ref,
        "checkout": str(checkout),
        "checks": [
            {
                "label": result.label,
                "returncode": result.returncode,
                "duration_seconds": result.duration_seconds,
                "stdout_tail": "\n".join(result.stdout.splitlines()[-20:]),
            }
            for result in results
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> int:
    args = parse_args()
    if args.stable_readiness:
        print(json.dumps(build_stable_readiness_report(Path.cwd()), ensure_ascii=False, indent=2))
        return 0
    workdir = make_workdir(args.workdir)
    workdir.mkdir(parents=True)
    checkout, commands = build_commands(
        repo_url=args.repo_url,
        ref=args.ref,
        python=args.python,
        workdir=workdir,
        skip_golden_path=args.skip_golden_path,
    )
    if checkout.exists():
        shutil.rmtree(checkout)
    results: list[FreshResult] = []
    try:
        for command in commands:
            result = run_command(command)
            results.append(result)
            if result.returncode != 0:
                break
        print(render_summary(repo_url=args.repo_url, ref=args.ref, checkout=checkout, results=results))
        return 0 if all(result.returncode == 0 for result in results) else 1
    finally:
        if args.workdir is None and not args.keep_workdir and workdir.exists():
            shutil.rmtree(workdir)


if __name__ == "__main__":
    raise SystemExit(main())
