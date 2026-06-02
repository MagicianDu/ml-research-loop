"""Build a CP-Bench submission from DCP-Bench-Open candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DCP_SUBMISSION = Path("docs/hf-evaluation/dcp-bench-open-p4-expanded-eval/submission.jsonl")
DEFAULT_DCP_REPORT = Path(
    "docs/hf-evaluation/dcp-bench-open-p4-expanded-eval/dcp-bench-open-local-eval-report.json"
)
DEFAULT_OUTPUT_DIR = Path("docs/hf-evaluation/cp-bench-p18-dcp-reverse-candidate")


def build_cp_submission_from_dcp(
    *,
    cp_dataset_path: Path,
    dcp_submission_path: Path,
    output_dir: Path,
    dcp_eval_report_path: Path | None = None,
    source_label: str,
) -> dict[str, Any]:
    """Write a CP-Bench style submission using DCP candidate rows."""
    cp_records = _read_jsonl(cp_dataset_path)
    dcp_records = _read_jsonl(dcp_submission_path)
    dcp_by_id = {str(record["id"]): record for record in dcp_records}
    dcp_failed_ids = _read_dcp_failed_ids(dcp_eval_report_path)

    mapped_records: list[dict[str, str]] = []
    mapped_cp_ids: list[str] = []
    alias_mappings: list[dict[str, str]] = []
    missing_cp_ids: list[str] = []
    dcp_failed_overlap: list[dict[str, str]] = []

    for cp_record in cp_records:
        cp_id = str(cp_record["id"])
        match = _find_dcp_match(cp_id, dcp_by_id)
        if match is None:
            missing_cp_ids.append(cp_id)
            continue
        dcp_id, dcp_record = match
        mapped_records.append({"id": cp_id, "model": str(dcp_record["model"])})
        mapped_cp_ids.append(cp_id)
        if dcp_id != _normalize_cp_id(cp_id):
            alias_mappings.append({"cp_id": cp_id, "dcp_id": dcp_id})
        if dcp_id in dcp_failed_ids:
            dcp_failed_overlap.append({"cp_id": cp_id, "dcp_id": dcp_id})

    dcp_failed_overlap_ids = {item["cp_id"] for item in dcp_failed_overlap}
    dcp_passed_overlap_count = sum(
        1 for cp_id in mapped_cp_ids if cp_id not in dcp_failed_overlap_ids
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "submission.jsonl", mapped_records)

    payload = {
        "schema_version": "2026-06-02.cp-bench-from-dcp-candidates.v1",
        "status": "written",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_label": source_label,
        "cp_dataset_path": _display_path(cp_dataset_path),
        "dcp_submission_path": _display_path(dcp_submission_path),
        "dcp_eval_report_path": _display_path(dcp_eval_report_path),
        "cp_dataset_count": len(cp_records),
        "dcp_candidate_count": len(dcp_records),
        "mapped_count": len(mapped_records),
        "missing_count": len(missing_cp_ids),
        "alias_mapped_count": len(alias_mappings),
        "mapped_cp_ids": mapped_cp_ids,
        "missing_cp_ids": missing_cp_ids,
        "alias_mappings": alias_mappings,
        "dcp_failed_overlap_count": len(dcp_failed_overlap),
        "dcp_passed_overlap_count": dcp_passed_overlap_count,
        "dcp_failed_overlap": dcp_failed_overlap,
        "submission_path": "submission.jsonl",
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
        "external_upload_performed": False,
        "claim_boundary": (
            "CP-Bench candidate built from local DCP-Bench-Open candidates only; "
            "not a Hugging Face upload, leaderboard score, ranking, or official "
            "external result."
        ),
    }
    _write_json(output_dir / "candidate-build-report.json", payload)
    _write_source_audit(output_dir / "source-audit.json", payload)
    _write_readme(output_dir / "README.md", payload)
    _write_manifest(output_dir)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a CP-Bench submission by reverse-mapping DCP candidates."
    )
    parser.add_argument("--cp-dataset", type=Path, required=True)
    parser.add_argument("--dcp-submission", type=Path, default=DEFAULT_DCP_SUBMISSION)
    parser.add_argument("--dcp-eval-report", type=Path, default=DEFAULT_DCP_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-label", default="DCP-Bench-Open P4 expanded eval")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_cp_submission_from_dcp(
        cp_dataset_path=args.cp_dataset,
        dcp_submission_path=args.dcp_submission,
        output_dir=args.output_dir,
        dcp_eval_report_path=args.dcp_eval_report,
        source_label=args.source_label,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "written" else 1


def _find_dcp_match(
    cp_id: str,
    dcp_by_id: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]] | None:
    for candidate_id in _dcp_candidate_aliases(cp_id):
        if candidate_id in dcp_by_id:
            return candidate_id, dcp_by_id[candidate_id]
    return None


def _dcp_candidate_aliases(cp_id: str) -> list[str]:
    normalized = _normalize_cp_id(cp_id)
    aliases = [normalized]
    if cp_id.startswith("aplai_course__") and "_" in normalized:
        session_number, rest = normalized.split("_", 1)
        aliases.append(f"session{session_number}_{rest}")
    return aliases


def _normalize_cp_id(cp_id: str) -> str:
    return cp_id.split("__", 1)[1] if "__" in cp_id else cp_id


def _read_dcp_failed_ids(path: Path | None) -> set[str]:
    if path is None:
        return set()
    payload = _read_json(path)
    values = payload.get("failed_model_ids")
    if not isinstance(values, list):
        return set()
    return {str(value) for value in values}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path} contains a non-object JSONL row")
        records.append(payload)
    return records


def _write_jsonl(path: Path, records: list[dict[str, str]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_source_audit(path: Path, payload: dict[str, Any]) -> None:
    source_audit = {
        "schema_version": "2026-06-02.cp-bench-from-dcp-source-audit.v1",
        "source_policy": "reverse_map_local_dcp_candidates_no_cp_reference_model_field",
        "source_label": payload["source_label"],
        "mapped_count": payload["mapped_count"],
        "alias_mapped_count": payload["alias_mapped_count"],
        "missing_count": payload["missing_count"],
        "dcp_failed_overlap_count": payload["dcp_failed_overlap_count"],
        "dcp_passed_overlap_count": payload["dcp_passed_overlap_count"],
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
        "claim_boundary": payload["claim_boundary"],
    }
    _write_json(path, source_audit)


def _write_readme(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CP-Bench P18 DCP Reverse Candidate",
        "",
        "本目录把 DCP-Bench-Open 本地候选反向映射为 CP-Bench verified submission。",
        "它不执行上传，也不声明官方榜单成绩。",
        "",
        "## 当前状态",
        "",
        f"- status: `{payload['status']}`",
        f"- mapped_count: `{payload['mapped_count']}`",
        f"- missing_count: `{payload['missing_count']}`",
        f"- alias_mapped_count: `{payload['alias_mapped_count']}`",
        f"- dcp_passed_overlap_count: `{payload['dcp_passed_overlap_count']}`",
        f"- dcp_failed_overlap_count: `{payload['dcp_failed_overlap_count']}`",
        "- `official_scores_claimed=false`",
        "- external_submission_status: `not_submitted`",
        "",
        "## 边界",
        "",
        "- 这是本地候选构建 artifact。",
        "- CP-Bench 本地 evaluator 跑通前，不得宣传它的 CP-Bench 分数。",
        "- 公开 `summary.txt` 出现前，不得宣传为官方 leaderboard score 或 ranking。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_manifest(output_dir: Path) -> None:
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
        "schema_version": "2026-06-02.cp-bench-from-dcp-manifest.v1",
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


def _display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    if path.is_absolute():
        return path.name
    return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
