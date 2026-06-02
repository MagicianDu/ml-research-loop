"""Build a DCP-Bench-Open migration gate from an existing CP-Bench submission.

The gate is intentionally local-only. It normalizes CP-Bench problem ids to
DCP-Bench-Open ids, parses a DCP evaluator summary, and records the claim
boundary without uploading or claiming an official leaderboard score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CP_SUBMISSION = Path(
    "docs/hf-evaluation/cp-bench-p17-manual-submission-gate/submission.jsonl"
)
DEFAULT_OUTPUT_DIR = Path("docs/hf-evaluation/dcp-bench-open-p0-p17-migration")


def normalize_dcp_problem_id(problem_id: str) -> str:
    """Remove the CP-Bench source prefix used before DCP-Bench-Open."""
    if "__" not in problem_id:
        return problem_id
    return problem_id.split("__", 1)[1]


def parse_dcp_eval_summary(summary_path: Path) -> dict[str, Any]:
    """Parse DCP-Bench-Open evaluator summary metrics and per-model outcomes."""
    raw_text = summary_path.read_text(encoding="utf-8")
    sanitized_summary = sanitize_machine_paths(raw_text)
    model_blocks = _extract_model_blocks(raw_text)
    passed_model_ids: list[str] = []
    failed_model_ids: list[str] = []
    model_outcomes: list[dict[str, str]] = []

    for model_id, body in model_blocks:
        status = _classify_model_block(body)
        model_outcomes.append({"id": model_id, "status": status})
        if status == "passed":
            passed_model_ids.append(model_id)
        else:
            failed_model_ids.append(model_id)

    metrics = _parse_overall_metrics(raw_text)
    metrics.update(
        {
            "passed_model_ids": passed_model_ids,
            "failed_model_ids": failed_model_ids,
            "model_outcomes": model_outcomes,
            "sanitized_summary": sanitized_summary,
        }
    )
    return metrics


def sanitize_machine_paths(text: str) -> str:
    """Replace machine-specific temporary paths in evaluator output."""
    sanitized = text
    markers = (
        "/" + "private" + "/" + "var" + "/" + "folders",
        "/" + "var" + "/" + "folders",
        "/" + "Users" + "/",
        "/" + "private" + "/" + "tmp",
        "/" + "tmp",
    )
    for marker in markers:
        sanitized = re.sub(re.escape(marker) + r"\S+", "<temporary_evaluator_script>", sanitized)
    return "\n".join(line.rstrip() for line in sanitized.splitlines()) + "\n"


def build_migration_gate(
    *,
    cp_submission_path: Path,
    dcp_dataset_path: Path,
    dcp_summary_path: Path,
    output_dir: Path,
    dcp_release: str,
    dcp_commit: str,
) -> dict[str, Any]:
    """Write a local DCP-Bench-Open migration gate artifact bundle."""
    cp_records = _read_jsonl(cp_submission_path)
    dcp_records = _read_jsonl(dcp_dataset_path)
    dcp_by_id = {str(record.get("id")): record for record in dcp_records}

    normalized_records = []
    missing_ids = []
    for record in cp_records:
        normalized = dict(record)
        normalized["id"] = normalize_dcp_problem_id(str(record.get("id", "")))
        if normalized["id"] not in dcp_by_id:
            missing_ids.append(normalized["id"])
        normalized_records.append(normalized)

    summary = parse_dcp_eval_summary(dcp_summary_path)
    reference_audit = _audit_reference_matches(normalized_records, dcp_by_id)
    status = "written" if not missing_ids else "invalid_missing_dcp_ids"

    output_dir.mkdir(parents=True, exist_ok=True)
    submission_path = output_dir / "submission.jsonl"
    _write_jsonl(submission_path, normalized_records)

    eval_summary_path = output_dir / "evaluation-summary.txt"
    eval_summary_path.write_text(summary["sanitized_summary"], encoding="utf-8")

    report = {
        "schema_version": "2026-06-02.dcp-bench-open-migration-gate.v1",
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark": "DCP-Bench-Open",
        "dcp_release": dcp_release,
        "dcp_commit": dcp_commit,
        "dcp_problem_count": len(dcp_by_id),
        "source_submission": cp_submission_path.as_posix(),
        "source_submission_sha256": _sha256(cp_submission_path),
        "dcp_dataset_sha256": _sha256(dcp_dataset_path),
        "raw_summary_sha256": _sha256(dcp_summary_path),
        "normalized_submission_path": "submission.jsonl",
        "evaluation_summary_path": "evaluation-summary.txt",
        "total_submitted_models": summary["total_submitted_models"],
        "models_ran_successfully": summary["models_ran_successfully"],
        "models_ran_successfully_denominator": summary["models_ran_successfully_denominator"],
        "submission_coverage_percent": summary["submission_coverage_percent"],
        "error_percent": summary["error_percent"],
        "consistency_percent": summary["consistency_percent"],
        "final_solution_accuracy_percent": summary["final_solution_accuracy_percent"],
        "submitted_solution_accuracy_percent": summary["submitted_solution_accuracy_percent"],
        "passed_model_count": len(summary["passed_model_ids"]),
        "failed_model_count": len(summary["failed_model_ids"]),
        "failed_model_ids": summary["failed_model_ids"],
        "missing_dcp_ids": missing_ids,
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
        "external_upload_performed": False,
        "leaderboard_claimed": False,
        "claim_boundary": (
            "Local DCP-Bench-Open v0.1.0 evaluator run only; not a public "
            "leaderboard result and not an official external submission."
        ),
        **reference_audit,
    }

    report_path = output_dir / "dcp-bench-open-local-eval-report.json"
    _write_json(report_path, report)

    source_audit = {
        "schema_version": "2026-06-02.dcp-bench-open-source-audit.v1",
        "source_policy": "no_dcp_reference_model_or_example_solution_for_generation",
        "candidate_model_source": "existing CP-Bench P17 manual submission gate",
        "dcp_reference_model_used_for_generation": False,
        "dcp_example_solution_used_for_generation": False,
        "dcp_model_exact_match_count": reference_audit["dcp_model_exact_match_count"],
        "dcp_example_solution_literal_match_count": reference_audit[
            "dcp_example_solution_literal_match_count"
        ],
        "normalized_problem_count": len(normalized_records),
        "dcp_problem_count": len(dcp_by_id),
        "claim_boundary": report["claim_boundary"],
    }
    _write_json(output_dir / "source-audit.json", source_audit)
    _write_readme(output_dir / "README.md", report)
    _write_manifest(output_dir)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a local DCP-Bench-Open migration gate from CP-Bench artifacts."
    )
    parser.add_argument("--cp-submission", type=Path, default=DEFAULT_CP_SUBMISSION)
    parser.add_argument("--dcp-dataset", type=Path, required=True)
    parser.add_argument("--dcp-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dcp-release", default="v0.1.0")
    parser.add_argument("--dcp-commit", default="5bef2cec7c62fecb0cfc47c7bb6879588fbaaf26")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_migration_gate(
        cp_submission_path=args.cp_submission,
        dcp_dataset_path=args.dcp_dataset,
        dcp_summary_path=args.dcp_summary,
        output_dir=args.output_dir,
        dcp_release=args.dcp_release,
        dcp_commit=args.dcp_commit,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "written" else 1


def _extract_model_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^--- Model: (.*?) ---$", text, flags=re.MULTILINE))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append((match.group(1), text[start:end]))
    return blocks


def _classify_model_block(body: str) -> str:
    if "OBJECTIVE CHECK: PASSED fully" in body:
        return "passed"
    if "CONSISTENCY: FAILED" in body:
        return "failed_consistency"
    if "OBJECTIVE CHECK: FAILED" in body:
        return "failed_objective"
    if "FAILED: Execution failed" in body:
        return "failed_execution"
    if "FAILED: Could not extract JSON" in body:
        return "failed_output_json"
    if "FAILED: No output" in body:
        return "failed_no_output"
    if "TIMEOUT:" in body:
        return "timeout"
    return "unknown"


def _parse_overall_metrics(text: str) -> dict[str, Any]:
    success = _require_match(
        r"Models That Ran Successfully \(out of submitted models\):\s*(\d+)/(\d+)",
        text,
    )
    return {
        "total_submitted_models": _int_metric(
            text, "Total Submitted Models that also exist in the dataset"
        ),
        "models_ran_successfully": int(success.group(1)),
        "models_ran_successfully_denominator": int(success.group(2)),
        "submission_coverage_percent": _percent_metric(text, "Submission coverage perc"),
        "error_percent": _percent_metric(text, "Error perc"),
        "consistency_percent": _percent_metric(text, "Consistency perc"),
        "final_solution_accuracy_percent": _percent_metric(
            text, "Final Solution Accuracy perc"
        ),
        "submitted_solution_accuracy_percent": _percent_metric(
            text, "Final Solution Accuracy perc \\(considering only submitted models\\)"
        ),
    }


def _int_metric(text: str, label: str) -> int:
    return int(_require_match(rf"{label}:\s*(\d+)", text).group(1))


def _percent_metric(text: str, label: str) -> float:
    return float(_require_match(rf"{label}:\s*([0-9.]+)%", text).group(1))


def _require_match(pattern: str, text: str) -> re.Match[str]:
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"DCP summary missing metric matching: {pattern}")
    return match


def _audit_reference_matches(
    submission_records: list[dict[str, Any]],
    dcp_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    model_matches: list[str] = []
    example_solution_matches: list[str] = []
    for record in submission_records:
        problem_id = str(record.get("id") or "")
        submitted_model = str(record.get("model") or "").strip()
        dcp_record = dcp_by_id.get(problem_id)
        if not dcp_record:
            continue
        dcp_model = str(dcp_record.get("model") or "").strip()
        dcp_model_with_instance = (
            str(dcp_record.get("example_instance") or "").strip() + "\n" + dcp_model
        ).strip()
        if submitted_model in {dcp_model, dcp_model_with_instance}:
            model_matches.append(problem_id)
        example_solution = dcp_record.get("example_solution")
        if example_solution is not None and _contains_json_literal(submitted_model, example_solution):
            example_solution_matches.append(problem_id)
    return {
        "dcp_reference_model_used_for_generation": False,
        "dcp_example_solution_used_for_generation": False,
        "dcp_model_exact_match_count": len(model_matches),
        "dcp_model_exact_match_ids": model_matches,
        "dcp_example_solution_literal_match_count": len(example_solution_matches),
        "dcp_example_solution_literal_match_ids": example_solution_matches,
    }


def _contains_json_literal(text: str, payload: Any) -> bool:
    compact = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    default = json.dumps(payload, sort_keys=True)
    compact_text = re.sub(r"\s+", "", text)
    return compact in compact_text or default in text


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path} line {line_number} must be a JSON object")
        records.append(payload)
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_readme(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# DCP-Bench-Open P0 P17 迁移门禁",
        "",
        "本目录记录 CP-Bench P17 候选迁移到 DCP-Bench-Open v0.1.0 的本地 evaluator 结果。",
        "它不是公开榜单成绩，也没有执行任何外部上传。",
        "",
        "## 结果",
        "",
        f"- DCP release: `{report['dcp_release']}`",
        f"- DCP commit: `{report['dcp_commit']}`",
        f"- DCP problem count: `{report['dcp_problem_count']}`",
        f"- submitted models: `{report['total_submitted_models']}`",
        f"- runtime success: `{report['models_ran_successfully']}/"
        f"{report['models_ran_successfully_denominator']}`",
        f"- submission coverage: `{report['submission_coverage_percent']:.2f}%`",
        f"- final solution accuracy: `{report['final_solution_accuracy_percent']:.2f}%`",
        f"- submitted-only accuracy: `{report['submitted_solution_accuracy_percent']:.2f}%`",
        f"- passed models: `{report['passed_model_count']}`",
        f"- failed models: `{report['failed_model_count']}`",
        "",
        "失败 ID:",
    ]
    if report["failed_model_ids"]:
        lines.extend(f"- `{item}`" for item in report["failed_model_ids"])
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 声明边界",
            "",
            "- `official_scores_claimed=false`",
            "- `external_submission_status=not_submitted`",
            "- `external_upload_performed=false`",
            "- 不得宣传为 DCP-Bench-Open 官方榜单或外部提交成绩。",
            "- 这只能宣传为固定公开 release 上的本地 evaluator 迁移结果。",
            "",
            "## 文件",
            "",
            "- `submission.jsonl`: DCP-normalized P17 submission。",
            "- `evaluation-summary.txt`: 已净化机器路径的 evaluator summary。",
            "- `dcp-bench-open-local-eval-report.json`: 结构化评测报告。",
            "- `source-audit.json`: no-reference 边界审计。",
            "- `artifact-manifest.json` / `SHA256SUMS`: artifact 完整性记录。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_manifest(output_dir: Path) -> None:
    artifact_names = [
        "submission.jsonl",
        "evaluation-summary.txt",
        "dcp-bench-open-local-eval-report.json",
        "source-audit.json",
        "README.md",
    ]
    manifest = {
        "schema_version": "2026-06-02.dcp-bench-open-artifact-manifest.v1",
        "status": "written",
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
        "artifacts": [
            {
                "path": name,
                "sha256": _sha256(output_dir / name),
                "byte_count": (output_dir / name).stat().st_size,
            }
            for name in artifact_names
        ],
    }
    manifest_path = output_dir / "artifact-manifest.json"
    _write_json(manifest_path, manifest)
    checksum_names = [*artifact_names, "artifact-manifest.json"]
    checksum_lines = [
        f"{_sha256(output_dir / name)}  {name}"
        for name in checksum_names
    ]
    (output_dir / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
