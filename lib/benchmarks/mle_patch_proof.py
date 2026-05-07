"""Proof bundle writer for official MLE-bench patch rounds."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.benchmarks.proof_archive import (
    build_proof_archive_bundle,
    write_proof_archive_bundle,
)


PATCH_PROOF_BUNDLE_VERSION = "2026-05-07.official-mle-patch-proof.v1"
PATCH_ROUND_OUTPUT_DIR_NAMES = {
    "benchmark-rounds",
    "mle-patch-rounds",
    "patch-round",
    "patch-rounds",
    "rounds",
}


def write_official_mle_patch_round_proof_bundle(
    *,
    patch_round_report: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Write proof artifacts and a hashed archive for one persisted patch round."""
    patch_round_report = patch_round_report.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    report = _read_json_object(patch_round_report)
    source_root = _patch_round_source_root(patch_round_report)
    artifact_root = output_dir / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, str] = {}
    artifacts["command_lines"] = _write_text_artifact(
        artifact_root,
        "commands.txt",
        _render_commands(report),
    )
    artifacts["resolved_config"] = _write_json_artifact(
        artifact_root,
        "config.json",
        _resolved_config(report, patch_round_report),
    )
    artifacts["environment_manifest"] = _write_json_artifact(
        artifact_root,
        "environment.json",
        _environment_manifest(report),
    )
    artifacts["raw_logs"] = _write_text_artifact(
        artifact_root,
        "logs/combined.log",
        _combined_logs(report, source_root),
    )
    artifacts["raw_reports"] = _write_json_artifact(
        artifact_root,
        "reports/patch-round-report.json",
        report,
    )
    artifacts["limitations_note"] = _write_text_artifact(
        artifact_root,
        "LIMITATIONS.md",
        _limitations_note(report),
    )

    _copy_optional_artifact(
        artifacts,
        artifact_root,
        role="patch_diff",
        source=_safe_optional_path(report.get("patch_diff_path"), source_root),
        destination="patches/patch.diff",
    )
    round_payload = report.get("round") if isinstance(report.get("round"), dict) else {}
    solve_payload = (
        round_payload.get("solve") if isinstance(round_payload.get("solve"), dict) else {}
    )
    grade_payload = (
        round_payload.get("grade") if isinstance(round_payload.get("grade"), dict) else {}
    )
    _copy_optional_artifact(
        artifacts,
        artifact_root,
        role="round_report",
        source=_safe_optional_path(round_payload.get("round_report_path"), source_root),
        destination="reports/round-report.json",
    )
    _copy_optional_artifact(
        artifacts,
        artifact_root,
        role="solve_log",
        source=_safe_optional_path(solve_payload.get("log_path"), source_root),
        destination="logs/solve.log",
    )
    _copy_optional_artifact(
        artifacts,
        artifact_root,
        role="grade_log",
        source=_safe_optional_path(grade_payload.get("log_path"), source_root),
        destination="logs/grade.log",
    )
    workspace = _safe_optional_path(
        report.get("workspace") or round_payload.get("workspace"),
        source_root,
    )
    if workspace:
        _copy_optional_artifact(
            artifacts,
            artifact_root,
            role="solver_snapshot",
            source=workspace / "solve.py",
            destination="snapshots/solve.py",
        )
    _copy_optional_artifact(
        artifacts,
        artifact_root,
        role="submission_snapshot",
        source=_safe_optional_path(round_payload.get("submission_path"), source_root)
        or (workspace / "submission.csv" if workspace else None),
        destination="snapshots/submission.csv",
    )

    manifest = _artifact_manifest(report, artifacts)
    manifest_path = output_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    archive_bundle = build_proof_archive_bundle(manifest, artifact_root)
    archive_payload = write_proof_archive_bundle(
        archive_bundle,
        artifact_root,
        output_dir / "archive",
    )
    return {
        "status": archive_payload["status"],
        "bundle_version": PATCH_PROOF_BUNDLE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "official_scores_claimed": False,
        "patch_round_report": str(patch_round_report),
        "manifest_path": str(manifest_path),
        "artifact_root": str(artifact_root),
        "archive": archive_payload,
    }


def _artifact_manifest(report: dict[str, Any], artifacts: dict[str, str]) -> dict[str, Any]:
    return {
        "manifest_version": PATCH_PROOF_BUNDLE_VERSION,
        "benchmark_name": "mle_bench",
        "run_mode": "official_debug_patch_round",
        "official_scores_claimed": False,
        "competition_id": report.get("competition_id"),
        "round_id": report.get("round_id"),
        "status": report.get("status"),
        "limitations": [
            "local mlebench grade-sample feedback only",
            "no official leaderboard score claimed",
            "patch was generated by the MCP client model and executed by ML Research Loop",
        ],
        "artifacts": artifacts,
    }


def _resolved_config(report: dict[str, Any], patch_round_report: Path) -> dict[str, Any]:
    round_payload = report.get("round") if isinstance(report.get("round"), dict) else {}
    return {
        "bundle_version": PATCH_PROOF_BUNDLE_VERSION,
        "patch_round_report": str(patch_round_report),
        "competition_id": report.get("competition_id"),
        "round_id": report.get("round_id"),
        "status": report.get("status"),
        "workspace": report.get("workspace"),
        "official_mle_bench": bool(report.get("official_mle_bench")),
        "official_scores_claimed": False,
        "patch_execution": report.get("patch_execution"),
        "loop_decision": report.get("loop_decision"),
        "round_status": round_payload.get("status"),
    }


def _environment_manifest(report: dict[str, Any]) -> dict[str, Any]:
    metadata = (
        report.get("execution_metadata")
        if isinstance(report.get("execution_metadata"), dict)
        else {}
    )
    return {
        "bundle_version": PATCH_PROOF_BUNDLE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution_metadata": metadata,
        "official_scores_claimed": False,
    }


def _render_commands(report: dict[str, Any]) -> str:
    metadata = (
        report.get("execution_metadata")
        if isinstance(report.get("execution_metadata"), dict)
        else {}
    )
    command = metadata.get("command") if isinstance(metadata.get("command"), list) else []
    round_payload = report.get("round") if isinstance(report.get("round"), dict) else {}
    grade = round_payload.get("grade") if isinstance(round_payload.get("grade"), dict) else {}
    lines = [
        "# Official MLE-bench Patch Round Commands",
        f"competition_id={report.get('competition_id')}",
        f"round_id={report.get('round_id')}",
        "official_scores_claimed=false",
    ]
    if command:
        lines.append("solve_command=" + json.dumps(command))
    if grade.get("mlebench_executable") and grade.get("submission_path"):
        lines.append(
            "grade_command="
            + json.dumps([
                grade.get("mlebench_executable"),
                "grade-sample",
                grade.get("submission_path"),
                report.get("competition_id"),
                "--data-dir",
                grade.get("data_dir"),
            ])
        )
    return "\n".join(lines).rstrip() + "\n"


def _combined_logs(report: dict[str, Any], source_root: Path) -> str:
    round_payload = report.get("round") if isinstance(report.get("round"), dict) else {}
    solve = round_payload.get("solve") if isinstance(round_payload.get("solve"), dict) else {}
    grade = round_payload.get("grade") if isinstance(round_payload.get("grade"), dict) else {}
    sections = [
        "# Official MLE-bench Patch Round Logs",
        "",
        "## solve.log",
        _read_text_or_note(_safe_optional_path(solve.get("log_path"), source_root)),
        "",
        "## grade.log",
        _read_text_or_note(_safe_optional_path(grade.get("log_path"), source_root)),
    ]
    return "\n".join(sections).rstrip() + "\n"


def _limitations_note(report: dict[str, Any]) -> str:
    round_payload = report.get("round") if isinstance(report.get("round"), dict) else {}
    grade = round_payload.get("grade") if isinstance(round_payload.get("grade"), dict) else {}
    grade_report = grade.get("report") if isinstance(grade.get("report"), dict) else {}
    return "\n".join([
        "# Official MLE-bench Patch Round Limitations",
        "",
        "- This artifact bundle captures local `mlebench grade-sample` feedback.",
        "- This is not an official leaderboard score.",
        "- `official_scores_claimed` is fixed to `false` in this bundle.",
        f"- round_status: `{report.get('status')}`",
        f"- valid_submission: `{grade_report.get('valid_submission')}`",
        f"- local_debug_score: `{grade_report.get('score')}`",
        "",
    ])


def _write_text_artifact(artifact_root: Path, relative: str, content: str) -> str:
    path = artifact_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return relative


def _write_json_artifact(artifact_root: Path, relative: str, payload: dict[str, Any]) -> str:
    path = artifact_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return relative


def _copy_optional_artifact(
    artifacts: dict[str, str],
    artifact_root: Path,
    *,
    role: str,
    source: Path | None,
    destination: str,
) -> None:
    if source is None or not source.is_file():
        return
    destination_path = artifact_root / destination
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination_path)
    artifacts[role] = destination


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _optional_path(value: Any) -> Path | None:
    if not value:
        return None
    return Path(str(value)).expanduser().resolve()


def _safe_optional_path(value: Any, source_root: Path) -> Path | None:
    path = _optional_path(value)
    if path is None:
        return None
    try:
        path.relative_to(source_root)
    except ValueError:
        return None
    return path


def _patch_round_source_root(patch_round_report: Path) -> Path:
    parents = patch_round_report.parents
    if len(parents) > 2 and parents[1].name in PATCH_ROUND_OUTPUT_DIR_NAMES:
        return parents[2]
    return patch_round_report.parent


def _read_text_or_note(path: Path | None) -> str:
    if path is None or not path.is_file():
        return "missing"
    return path.read_text(encoding="utf-8", errors="replace")
