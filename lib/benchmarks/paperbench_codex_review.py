"""Codex-assisted review bundles for PaperBench artifacts."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CODEX_REVIEW_BUNDLE_VERSION = "2026-05-07.paperbench-codex-review.v1"
CODEX_REVIEW_REPORT_VERSION = "2026-05-07.paperbench-codex-review-report.v1"


def write_paperbench_codex_review_bundle(
    *,
    run_dir: Path,
    paper_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Write a keyless PaperBench review packet intended for Codex."""
    run_dir = run_dir.expanduser().resolve()
    paper_dir = paper_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    packet_dir = output_dir / "packet"
    if packet_dir.exists():
        shutil.rmtree(packet_dir)
    packet_files = _copy_review_packet(
        run_dir=run_dir,
        paper_dir=paper_dir,
        packet_dir=packet_dir,
    )
    grade_payload = _read_json_optional(run_dir / "grade.json")
    paper_id = _paper_id(grade_payload, paper_dir)
    bundle = {
        "bundle_version": CODEX_REVIEW_BUNDLE_VERSION,
        "generated_at": _utc_now(),
        "status": "ready_for_codex_review",
        "benchmark_name": "paperbench",
        "review_mode": "codex_assisted_rubric_review",
        "judge_type": "codex_assisted",
        "official_scores_claimed": False,
        "paperbench_score": None,
        "paper_id": paper_id,
        "source": {
            "run_dir": str(run_dir),
            "paper_dir": str(paper_dir),
        },
        "packet_dir": "packet",
        "packet_files": packet_files,
        "review_schema": _review_schema(),
        "allowed_public_claims": [
            "PaperBench artifacts were prepared for Codex-assisted rubric review",
            "Codex review may be reported separately from official PaperBench scores",
        ],
        "blocked_public_claims": [
            "official PaperBench score",
            "official leaderboard result",
            "LLM judge result from the official PaperBench grader",
        ],
        "instructions": [
            "Use the paper and rubric as the source of truth.",
            "Use only packet evidence when assigning scores.",
            "Return missing evidence when a rubric item cannot be supported.",
            "Do not call this an official PaperBench score.",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = output_dir / "codex-review-bundle.json"
    prompt_path = output_dir / "codex-review-prompt.md"
    bundle_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    prompt_path.write_text(_render_review_prompt(bundle), encoding="utf-8")
    return {
        "status": "written",
        "bundle_path": str(bundle_path),
        "prompt_path": str(prompt_path),
        "packet_dir": str(packet_dir),
        "bundle": {
            "status": bundle["status"],
            "judge_type": bundle["judge_type"],
            "official_scores_claimed": bundle["official_scores_claimed"],
            "paperbench_score": bundle["paperbench_score"],
            "paper_id": bundle["paper_id"],
        },
    }


def write_paperbench_codex_review_report(
    *,
    bundle_path: Path,
    review_payload: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Persist a client-supplied Codex review without claiming official scores."""
    bundle_path = bundle_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    codex_review = _normalize_codex_review(review_payload)
    report = {
        "report_version": CODEX_REVIEW_REPORT_VERSION,
        "generated_at": _utc_now(),
        "status": "codex_review_recorded",
        "benchmark_name": "paperbench",
        "paper_id": bundle.get("paper_id"),
        "review_mode": "codex_assisted_rubric_review",
        "judge_type": "codex_assisted",
        "official_scores_claimed": False,
        "paperbench_score": None,
        "codex_review": codex_review,
        "source_bundle": str(bundle_path),
        "allowed_public_claims": [
            "Codex-assisted rubric review was recorded with evidence references",
        ],
        "blocked_public_claims": [
            "official PaperBench score",
            "official leaderboard result",
            "official PaperBench real judge score",
        ],
        "limitations": [
            "Codex-assisted review is not an official PaperBench score.",
            "Scores depend on the evidence packet and client model judgment.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "codex-review-report.json"
    markdown_path = output_dir / "codex-review-report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_render_review_report_markdown(report), encoding="utf-8")
    return {
        "status": "written",
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "report": {
            "status": report["status"],
            "judge_type": report["judge_type"],
            "official_scores_claimed": report["official_scores_claimed"],
            "paperbench_score": report["paperbench_score"],
            "codex_review_score": codex_review.get("codex_review_score"),
        },
    }


def _copy_review_packet(
    *,
    run_dir: Path,
    paper_dir: Path,
    packet_dir: Path,
) -> dict[str, str]:
    files: dict[str, str] = {}
    files.update(_copy_named_files(
        source_dir=paper_dir,
        destination_dir=packet_dir / "paper",
        role_to_name={
            "paper_md": "paper.md",
            "rubric_json": "rubric.json",
            "addendum_md": "addendum.md",
        },
        required_roles={"paper_md", "rubric_json"},
        relative_to=packet_dir.parent,
    ))
    files.update(_copy_named_files(
        source_dir=run_dir,
        destination_dir=packet_dir / "run",
        role_to_name={
            "grade_json": "grade.json",
            "metadata_json": "metadata.json",
            "status_json": "status.json",
            "agent_log": "agent.log",
            "run_log": "run.log",
        },
        required_roles={"grade_json"},
        relative_to=packet_dir.parent,
    ))
    latest_submission = _latest_submission_dir(run_dir)
    if latest_submission is not None:
        files.update(_copy_named_files(
            source_dir=latest_submission,
            destination_dir=packet_dir / "submissions",
            role_to_name={
                "submission_log": "log.json",
                "submission_executed_metadata": "submission_executed_metadata.json",
                "submission_executed_grader_output": "submission_executed_grader_output_0.json",
            },
            required_roles=set(),
            relative_to=packet_dir.parent,
        ))
    return files


def _copy_named_files(
    *,
    source_dir: Path,
    destination_dir: Path,
    role_to_name: dict[str, str],
    required_roles: set[str],
    relative_to: Path,
) -> dict[str, str]:
    copied: dict[str, str] = {}
    for role, filename in role_to_name.items():
        source = source_dir / filename
        if not source.exists():
            if role in required_roles:
                raise FileNotFoundError(str(source))
            continue
        if not source.is_file():
            if role in required_roles:
                raise IsADirectoryError(str(source))
            continue
        destination = destination_dir / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied[role] = destination.relative_to(relative_to).as_posix()
    return copied


def _latest_submission_dir(run_dir: Path) -> Path | None:
    submissions_dir = run_dir / "submissions"
    if not submissions_dir.exists():
        return None
    candidates = sorted(path for path in submissions_dir.iterdir() if path.is_dir())
    return candidates[-1] if candidates else None


def _paper_id(grade_payload: dict[str, Any], paper_dir: Path) -> str:
    result = grade_payload.get("paperbench_result")
    if isinstance(result, dict) and result.get("paper_id"):
        return str(result["paper_id"])
    return paper_dir.name


def _review_schema() -> dict[str, Any]:
    return {
        "required_fields": [
            "summary",
            "codex_review_score",
            "leaf_scores",
            "evidence_refs",
            "missing_evidence",
            "confidence",
        ],
        "leaf_score_fields": [
            "rubric_id",
            "score",
            "evidence_refs",
            "missing_evidence",
            "reasoning_summary",
            "confidence",
        ],
    }


def _normalize_codex_review(review_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": str(review_payload.get("summary") or ""),
        "codex_review_score": review_payload.get("codex_review_score"),
        "leaf_scores": _list_of_dicts(review_payload.get("leaf_scores")),
        "evidence_refs": _list_of_strings(review_payload.get("evidence_refs")),
        "missing_evidence": _list_of_strings(review_payload.get("missing_evidence")),
        "confidence": review_payload.get("confidence"),
    }


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _read_json_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _render_review_prompt(bundle: dict[str, Any]) -> str:
    packet_files = bundle.get("packet_files", {})
    lines = [
        "# PaperBench Codex Review Prompt",
        "",
        "This is a Codex-assisted rubric review, not an official PaperBench score.",
        "",
        f"- paper_id: `{bundle.get('paper_id')}`",
        "- official_scores_claimed=false",
        "- judge_type=codex_assisted",
        "- paperbench_score=null",
        "",
        "## Evidence Packet",
        "",
    ]
    for role, path in sorted(packet_files.items()):
        lines.append(f"- `{role}`: `{path}`")
    lines.extend([
        "",
        "## Required Output",
        "",
        "Return JSON with `summary`, `codex_review_score`, `leaf_scores`, "
        "`evidence_refs`, `missing_evidence`, and `confidence`.",
        "Each leaf score must cite evidence from the packet or list the missing evidence.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def _render_review_report_markdown(report: dict[str, Any]) -> str:
    review = report.get("codex_review", {})
    lines = [
        "# PaperBench Codex Review Report",
        "",
        "This is a Codex-assisted rubric review. It is not an official PaperBench score.",
        "",
        f"- status: `{report.get('status')}`",
        f"- paper_id: `{report.get('paper_id')}`",
        f"- judge_type: `{report.get('judge_type')}`",
        f"- official_scores_claimed: `{str(report.get('official_scores_claimed')).lower()}`",
        f"- paperbench_score: `{report.get('paperbench_score')}`",
        f"- codex_review_score: `{review.get('codex_review_score')}`",
        "",
        "## Summary",
        "",
        str(review.get("summary") or ""),
        "",
        "## Missing Evidence",
        "",
    ]
    missing = review.get("missing_evidence", [])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.extend(["", "## Blocked Public Claims", ""])
    lines.extend(f"- {item}" for item in report.get("blocked_public_claims", []))
    return "\n".join(lines).rstrip() + "\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
