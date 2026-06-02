"""Build a local CP-Bench leaderboard competitiveness audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATE_ROUND = Path(
    "docs/hf-evaluation/cp-bench-p18-dcp-reverse-candidate-round/"
    "cp-bench-candidate-round-report.json"
)
DEFAULT_PUBLIC_WATCH = Path(
    "docs/hf-evaluation/cp-bench-p18-public-result-watch/public-result-watch.json"
)
DEFAULT_OUTPUT_DIR = Path("docs/hf-evaluation/cp-bench-p18-leaderboard-competitiveness-audit")


def build_leaderboard_competitiveness_audit(
    *,
    output_dir: Path,
    candidate_round: dict[str, Any] | None = None,
    public_watch: dict[str, Any] | None = None,
    candidate_round_path: Path = DEFAULT_CANDIDATE_ROUND,
    public_watch_path: Path = DEFAULT_PUBLIC_WATCH,
    source_label: str = "CP-Bench P18 local candidate",
) -> dict[str, Any]:
    """Write a local-only competitiveness audit from local and public evidence."""
    candidate_round = candidate_round or _read_json(candidate_round_path)
    public_watch = public_watch or _read_json(public_watch_path)
    after_summary = candidate_round.get("after_summary") or {}
    failure_summary = candidate_round.get("failure_summary") or {}
    snapshot = public_watch.get("public_verified_leaderboard_snapshot") or {}
    entries = snapshot.get("entries") if isinstance(snapshot.get("entries"), list) else []
    local_accuracy = float(after_summary.get("final_solution_accuracy_percent") or 0.0)
    higher_entries = [
        entry for entry in entries
        if float(entry.get("final_solution_accuracy_percent") or 0.0) > local_accuracy
    ]
    beaten_entries = [
        entry for entry in entries
        if local_accuracy > float(entry.get("final_solution_accuracy_percent") or 0.0)
    ]
    would_rank = len(higher_entries) + 1
    status = (
        "locally_competitive_for_manual_submission_review"
        if beaten_entries
        else "not_worth_public_submission_yet"
    )
    payload = {
        "schema_version": "2026-06-02.cp-bench-leaderboard-competitiveness-audit.v1",
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_label": source_label,
        "target_is_archived_by_upstream": True,
        "upstream_successor": "DCP-Bench-Open",
        "local_candidate": {
            "final_solution_accuracy_percent": local_accuracy,
            "submitted_models": after_summary.get("submitted_models"),
            "coverage_percent": after_summary.get("coverage_percent"),
            "runtime_success": after_summary.get("runtime_success"),
            "passed": failure_summary.get("passed"),
            "failed": failure_summary.get("failed"),
            "failed_problem_ids": failure_summary.get("failed_problem_ids") or [],
            "official_scores_claimed": False,
            "external_submission_status": "not_submitted",
        },
        "public_verified_leaderboard_snapshot": {
            "entry_count": snapshot.get("entry_count", len(entries)),
            "top_accuracy_percent": snapshot.get("top_accuracy_percent"),
            "lowest_public_accuracy_percent": snapshot.get("lowest_public_accuracy_percent"),
            "local_candidate_would_rank": would_rank,
            "would_beat_public_entries": len(beaten_entries),
            "nearest_lower_public_entry": _nearest_lower(entries, local_accuracy),
            "nearest_higher_public_entry": _nearest_higher(entries, local_accuracy),
        },
        "decision": (
            "prepare_manual_submission_gate"
            if status == "locally_competitive_for_manual_submission_review"
            else "continue_local_improvement"
        ),
        "reason": (
            f"Local candidate accuracy {local_accuracy:.2f} exceeds "
            f"{len(beaten_entries)} current public verified CP-Bench entries, "
            "but no external upload has been performed."
        ),
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
        "claim_boundary": (
            "This audit compares local evaluator output against public CP-Bench "
            "storage summaries. It is not a Hugging Face submission, official "
            "score, ranking, or external result."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "leaderboard-competitiveness-audit.json", payload)
    _write_readme(output_dir / "README.md", payload)
    _write_manifest(output_dir, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a local CP-Bench leaderboard competitiveness audit."
    )
    parser.add_argument("--candidate-round", type=Path, default=DEFAULT_CANDIDATE_ROUND)
    parser.add_argument("--public-watch", type=Path, default=DEFAULT_PUBLIC_WATCH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-label", default="CP-Bench P18 local candidate")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_leaderboard_competitiveness_audit(
        output_dir=args.output_dir,
        candidate_round_path=args.candidate_round,
        public_watch_path=args.public_watch,
        source_label=args.source_label,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _nearest_lower(entries: list[dict[str, Any]], local_accuracy: float) -> dict[str, Any] | None:
    lower = [
        entry for entry in entries
        if float(entry.get("final_solution_accuracy_percent") or 0.0) < local_accuracy
    ]
    if not lower:
        return None
    return max(lower, key=lambda entry: float(entry.get("final_solution_accuracy_percent") or 0.0))


def _nearest_higher(entries: list[dict[str, Any]], local_accuracy: float) -> dict[str, Any] | None:
    higher = [
        entry for entry in entries
        if float(entry.get("final_solution_accuracy_percent") or 0.0) > local_accuracy
    ]
    if not higher:
        return None
    return min(higher, key=lambda entry: float(entry.get("final_solution_accuracy_percent") or 0.0))


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_readme(path: Path, payload: dict[str, Any]) -> None:
    local = payload["local_candidate"]
    snapshot = payload["public_verified_leaderboard_snapshot"]
    lines = [
        "# CP-Bench Leaderboard Competitiveness Audit",
        "",
        "本目录只比较本地 evaluator 结果与公开 storage snapshot；不执行上传。",
        "",
        f"- status: `{payload['status']}`",
        f"- local accuracy: `{local['final_solution_accuracy_percent']}`",
        f"- runtime_success: `{local['runtime_success']}`",
        f"- expected public rank if uploaded: `{snapshot['local_candidate_would_rank']}`",
        f"- would beat public entries: `{snapshot['would_beat_public_entries']}`",
        "- `official_scores_claimed=false`",
        "- external_submission_status: `not_submitted`",
        "",
        "公开结果出现前，不得宣传为官方 leaderboard score 或 ranking。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_manifest(output_dir: Path, payload: dict[str, Any]) -> None:
    artifacts = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if path.name in {"artifact-manifest.json", "SHA256SUMS"} or not path.is_file():
            continue
        artifacts.append(
            {
                "path": path.name,
                "sha256": _sha256(path),
                "byte_count": path.stat().st_size,
            }
        )
    manifest = {
        "schema_version": "2026-06-02.cp-bench-leaderboard-competitiveness-manifest.v1",
        "status": payload["status"],
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
        "artifacts": artifacts,
    }
    _write_json(output_dir / "artifact-manifest.json", manifest)
    checksum_lines = [
        f"{artifact['sha256']}  {artifact['path']}" for artifact in artifacts
    ]
    checksum_lines.append(
        f"{_sha256(output_dir / 'artifact-manifest.json')}  artifact-manifest.json"
    )
    (output_dir / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
