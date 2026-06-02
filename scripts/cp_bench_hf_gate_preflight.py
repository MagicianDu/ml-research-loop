"""CP-Bench manual submission gate preflight.

This script validates a local CP-Bench manual submission gate and probes the
public Hugging Face storage state. It never uploads files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.benchmarks import validate_cp_bench_submission


DATASET_REPO_ID = "kostis-init/my-storage"
VERIFIED_DATASET_PATH = "v1_verified"
DEFAULT_GATE_DIR = Path("docs/hf-evaluation/cp-bench-p17-manual-submission-gate")
REQUIRED_GATE_ARTIFACTS = {
    "submission.jsonl",
    "submission-report.md",
    "manual-checklist.md",
    "manual-upload-instructions.md",
    "approach-report.pdf",
    "submission-metadata.json",
    "README.md",
    "source-report.json",
}


def normalize_submission_name(value: str) -> str:
    """Match the CP-Bench Space submission name normalization."""
    stripped = value.strip().replace(" ", "_").lower()
    return "".join(character for character in stripped if character.isalnum() or character == "_")[
        :30
    ]


def validate_gate(gate_dir: Path) -> dict[str, Any]:
    """Validate local gate artifacts without contacting Hugging Face."""
    gate = gate_dir.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []

    manifest_path = gate / "artifact-manifest.json"
    metadata_path = gate / "submission-metadata.json"
    checksum_path = gate / "SHA256SUMS"
    submission_path = gate / "submission.jsonl"

    manifest = _read_json_object(manifest_path, errors)
    metadata = _read_json_object(metadata_path, errors)
    checksum_entries = _read_sha256sums(checksum_path, errors)

    if manifest:
        _require_false(manifest, "official_scores_claimed", "artifact-manifest.json", errors)
        _require_value(
            manifest,
            "external_submission_status",
            "not_submitted",
            "artifact-manifest.json",
            errors,
        )
        _require_value(manifest, "manual_submission_required", True, "artifact-manifest.json", errors)

    if metadata:
        _require_false(metadata, "official_scores_claimed", "submission-metadata.json", errors)
        _require_value(
            metadata,
            "external_submission_status",
            "not_submitted",
            "submission-metadata.json",
            errors,
        )
        submission_name = str(metadata.get("submission_name") or "")
        normalized_name = normalize_submission_name(submission_name)
        if not submission_name:
            errors.append("submission-metadata.json missing submission_name")
        elif normalized_name != submission_name:
            errors.append(
                "submission_name must already match CP-Bench Space normalization: "
                f"{submission_name!r} -> {normalized_name!r}"
            )
        elif len(submission_name) > 30:
            errors.append("submission_name exceeds CP-Bench Space 30 character limit")
    else:
        submission_name = ""
        normalized_name = ""

    if manifest:
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list):
            errors.append("artifact-manifest.json artifacts must be a list")
            artifacts = []
        artifact_paths = {
            str(artifact.get("path") or "")
            for artifact in artifacts
            if isinstance(artifact, dict)
        }
        missing_artifacts = sorted(REQUIRED_GATE_ARTIFACTS - artifact_paths)
        if missing_artifacts:
            errors.append(
                "artifact-manifest.json missing required gate artifacts: "
                + ", ".join(missing_artifacts)
            )
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                errors.append("artifact-manifest.json contains a non-object artifact entry")
                continue
            _validate_manifest_artifact(gate, artifact, errors)

    if checksum_entries:
        for relative_path, expected_digest in checksum_entries.items():
            path = gate / relative_path
            if not path.exists():
                errors.append(f"SHA256SUMS references missing file: {relative_path}")
                continue
            actual_digest = _sha256(path)
            if actual_digest != expected_digest:
                errors.append(f"SHA256SUMS digest mismatch for {relative_path}")
        if "artifact-manifest.json" not in checksum_entries:
            errors.append("SHA256SUMS must include artifact-manifest.json")

    submission_validation = validate_cp_bench_submission(submission_path)
    if submission_validation.get("status") != "valid":
        errors.append(f"submission.jsonl invalid: {submission_validation.get('reason')}")

    pdf_path = gate / "approach-report.pdf"
    if not pdf_path.exists():
        errors.append("approach-report.pdf missing")
    elif pdf_path.suffix != ".pdf":
        errors.append("approach-report.pdf must be a PDF file")

    for text_path in (
        gate / "README.md",
        gate / "submission-report.md",
        gate / "manual-checklist.md",
        gate / "manual-upload-instructions.md",
    ):
        if text_path.exists():
            text = text_path.read_text(encoding="utf-8")
            if "official_scores_claimed" in text and "false" not in text.lower():
                warnings.append(f"{text_path.name} mentions official_scores_claimed without false")
            if _contains_machine_path(text):
                errors.append(f"{text_path.name} contains a machine-specific path")

    return {
        "status": "valid" if not errors else "invalid",
        "gate_dir": str(gate),
        "submission_name": submission_name,
        "normalized_submission_name": normalized_name,
        "dataset_version": metadata.get("dataset_version") if metadata else None,
        "modelling_framework": metadata.get("modelling_framework") if metadata else None,
        "base_llm": metadata.get("base_llm") if metadata else None,
        "submission_validation": _relative_submission_validation(submission_validation),
        "artifact_count": len(manifest.get("artifacts", [])) if manifest else 0,
        "checksum_count": len(checksum_entries),
        "errors": errors,
        "warnings": warnings,
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
        "manual_submission_required": True,
    }


def build_preflight(
    gate_dir: Path,
    *,
    api: Any | None = None,
    repo_files: list[str] | None = None,
) -> dict[str, Any]:
    """Build a live preflight report for a local gate and public HF storage."""
    gate_validation = validate_gate(gate_dir)
    submission_name = str(gate_validation.get("submission_name") or "")
    if repo_files is None:
        api = api or _new_hf_api()
        auth_state = _read_hf_auth_state(api)
        repo_state = _read_hf_repo_files(api)
        files = repo_state.get("files", [])
    else:
        auth_state = _read_hf_auth_state(api) if api is not None else _unknown_auth_state()
        repo_state = {"status": "readable", "file_count": len(repo_files), "error": None}
        files = repo_files

    submission_prefix = f"submissions/{VERIFIED_DATASET_PATH}/{submission_name}/"
    result_prefix = f"results/{VERIFIED_DATASET_PATH}/{submission_name}/"
    target_submission_exists = any(path.startswith(submission_prefix) for path in files)
    target_result_exists = any(path == f"{result_prefix}summary.txt" for path in files)
    public_repo_state = dict(repo_state)
    public_repo_state.pop("files", None)

    if gate_validation["status"] != "valid":
        status = "blocked_invalid_gate"
    elif repo_state["status"] != "readable":
        status = "blocked_hf_storage_unreadable"
    elif target_result_exists:
        status = "public_result_available"
    elif target_submission_exists:
        status = "submitted_waiting_for_result"
    elif auth_state["status"] != "logged_in":
        status = "blocked_missing_hf_auth"
    else:
        status = "ready_for_manual_space_upload"

    return {
        "schema_version": "2026-06-01.cp-bench-hf-upload-preflight.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "dataset_repo_id": DATASET_REPO_ID,
        "dataset_version_path": VERIFIED_DATASET_PATH,
        "gate_validation": gate_validation,
        "hf_auth": auth_state,
        "hf_storage": public_repo_state,
        "target_submission_exists": target_submission_exists,
        "target_result_exists": target_result_exists,
        "target_submission_path": submission_prefix.rstrip("/"),
        "target_result_path": f"{result_prefix}summary.txt",
        "observed_external_submission_status": (
            "submitted" if target_submission_exists else "not_submitted"
        ),
        "manual_approval_required": True,
        "external_upload_performed_by_script": False,
        "official_scores_claimed": False,
        "claim_boundary": (
            "Preflight report only; it validates local gate readiness and public "
            "Hugging Face storage state, but never uploads files or claims an "
            "official leaderboard score."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a CP-Bench manual submission gate and probe HF storage."
    )
    parser.add_argument("--gate-dir", type=Path, default=DEFAULT_GATE_DIR)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_preflight(args.gate_dir)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _new_hf_api() -> Any:
    from huggingface_hub import HfApi

    return HfApi()


def _read_hf_auth_state(api: Any) -> dict[str, Any]:
    try:
        who = api.whoami()
    except Exception as exc:  # pragma: no cover - exact HF exception type is version-dependent.
        return {
            "status": "not_logged_in",
            "error_type": type(exc).__name__,
            "message": str(exc).splitlines()[0] if str(exc) else "",
        }
    return {
        "status": "logged_in",
        "name": who.get("name") or who.get("fullname") or who.get("email"),
    }


def _unknown_auth_state() -> dict[str, Any]:
    return {
        "status": "not_checked",
        "message": "repo_files injected by caller; auth was not probed",
    }


def _read_hf_repo_files(api: Any) -> dict[str, Any]:
    try:
        files = api.list_repo_files(repo_id=DATASET_REPO_ID, repo_type="dataset")
    except Exception as exc:  # pragma: no cover - network errors are environment-dependent.
        return {
            "status": "unreadable",
            "file_count": 0,
            "files": [],
            "error_type": type(exc).__name__,
            "message": str(exc).splitlines()[0] if str(exc) else "",
        }
    return {
        "status": "readable",
        "file_count": len(files),
        "files": files,
        "error": None,
    }


def _read_json_object(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing {path.name}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name} is invalid JSON: {exc.msg}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{path.name} must be a JSON object")
        return {}
    return payload


def _read_sha256sums(path: Path, errors: list[str]) -> dict[str, str]:
    if not path.exists():
        errors.append("missing SHA256SUMS")
        return {}
    entries: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            errors.append(f"SHA256SUMS line {line_number} has invalid format")
            continue
        digest, relative_path = match.groups()
        entries[relative_path] = digest
    return entries


def _validate_manifest_artifact(gate: Path, artifact: dict[str, Any], errors: list[str]) -> None:
    relative_path = str(artifact.get("path") or "")
    if not relative_path:
        errors.append("artifact-manifest.json artifact missing path")
        return
    path = gate / relative_path
    if not path.exists():
        errors.append(f"artifact-manifest.json references missing file: {relative_path}")
        return
    actual_digest = _sha256(path)
    if artifact.get("sha256") != actual_digest:
        errors.append(f"artifact-manifest.json sha256 mismatch for {relative_path}")
    actual_size = path.stat().st_size
    if artifact.get("byte_count") != actual_size:
        errors.append(f"artifact-manifest.json byte_count mismatch for {relative_path}")


def _require_false(
    payload: dict[str, Any],
    key: str,
    source_name: str,
    errors: list[str],
) -> None:
    if payload.get(key) is not False:
        errors.append(f"{source_name} must keep {key}=false")


def _require_value(
    payload: dict[str, Any],
    key: str,
    expected: Any,
    source_name: str,
    errors: list[str],
) -> None:
    if payload.get(key) != expected:
        errors.append(f"{source_name} must keep {key}={expected!r}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_submission_validation(payload: dict[str, Any]) -> dict[str, Any]:
    validation = dict(payload)
    path = validation.get("path")
    if path:
        validation["path"] = Path(str(path)).name
    return validation


def _contains_machine_path(text: str) -> bool:
    user_home_marker = "/" + "Users" + "/"
    private_temp_marker = "/" + "private" + "/" + "var" + "/" + "folders"
    temp_marker = "/" + "var" + "/" + "folders"
    workspace_marker = "Documents" + "/" + "ml-research-loop"
    return any(
        marker in text
        for marker in (user_home_marker, private_temp_marker, temp_marker, workspace_marker)
    )


if __name__ == "__main__":
    raise SystemExit(main())
