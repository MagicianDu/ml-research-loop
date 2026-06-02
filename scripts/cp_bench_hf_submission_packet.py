"""Build a CP-Bench Hugging Face Space submission readiness packet.

The packet is intentionally non-uploading. It records the exact Space form
fields, current public-storage state, and post-upload verification commands so a
human can approve and perform the external submission without reconstructing the
state from scattered artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.cp_bench_hf_gate_preflight import (
    DEFAULT_GATE_DIR,
    build_preflight,
)


DEFAULT_OUTPUT_DIR = Path("docs/hf-evaluation/cp-bench-p17-space-submission-packet")
SPACE_REPO_ID = "kostis-init/CP-Bench-Leaderboard"
SPACE_URL = "https://huggingface.co/spaces/kostis-init/CP-Bench-Leaderboard"


def build_submission_packet(
    *,
    gate_dir: Path,
    output_dir: Path,
    api: Any | None = None,
    repo_files: list[str] | None = None,
) -> dict[str, Any]:
    """Write a non-uploading CP-Bench Space submission readiness packet."""
    preflight = build_preflight(gate_dir, api=api, repo_files=repo_files)
    sanitized_preflight = _sanitize_preflight(preflight, gate_dir)
    gate_validation = sanitized_preflight["gate_validation"]
    manual_upload = {
        "space_repo_id": SPACE_REPO_ID,
        "space_url": SPACE_URL,
        "submission_name": gate_validation["submission_name"],
        "dataset_version": gate_validation["dataset_version"],
        "modelling_framework": gate_validation["modelling_framework"],
        "base_llm": gate_validation["base_llm"],
        "submission_file": "submission.jsonl",
        "report_pdf": "approach-report.pdf",
        "target_submission_path": sanitized_preflight["target_submission_path"],
        "target_result_path": sanitized_preflight["target_result_path"],
        "requires_human_approval": True,
        "can_upload_now": sanitized_preflight["status"] == "ready_for_manual_space_upload",
    }
    payload = {
        "schema_version": "2026-06-02.cp-bench-hf-submission-packet.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": sanitized_preflight["status"],
        "gate_dir": _display_path(gate_dir),
        "preflight": sanitized_preflight,
        "manual_upload": manual_upload,
        "external_upload_performed_by_script": False,
        "official_scores_claimed": False,
        "external_submission_status": sanitized_preflight[
            "observed_external_submission_status"
        ],
        "claim_boundary": (
            "Readiness packet only; it records how to submit through the CP-Bench "
            "Hugging Face Space after human approval, but performs no external "
            "upload and claims no official leaderboard score."
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "submission-readiness-report.json", payload)
    _write_json(output_dir / "manual-form-fields.json", _manual_form_fields(manual_upload))
    _write_readme(output_dir / "README.md", payload)
    _write_post_upload_verification(output_dir / "post-upload-verification.md", payload)
    _write_manifest(output_dir)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write a non-uploading CP-Bench HF Space submission packet."
    )
    parser.add_argument("--gate-dir", type=Path, default=DEFAULT_GATE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_submission_packet(gate_dir=args.gate_dir, output_dir=args.output_dir)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _sanitize_preflight(preflight: dict[str, Any], gate_dir: Path) -> dict[str, Any]:
    sanitized = json.loads(json.dumps(preflight))
    sanitized["gate_validation"]["gate_dir"] = _display_path(gate_dir)
    return sanitized


def _display_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.name


def _manual_form_fields(manual_upload: dict[str, Any]) -> dict[str, str]:
    return {
        "Submission Name": str(manual_upload["submission_name"]),
        "Dataset Version": str(manual_upload["dataset_version"]),
        "Modelling Framework": str(manual_upload["modelling_framework"]),
        "Base LLM": str(manual_upload["base_llm"]),
        "Report PDF": str(manual_upload["report_pdf"]),
        "Submission File": str(manual_upload["submission_file"]),
    }


def _write_readme(path: Path, payload: dict[str, Any]) -> None:
    manual = payload["manual_upload"]
    lines = [
        "# CP-Bench P17 Space Submission Packet",
        "",
        "本目录是 CP-Bench P17 外部提交前的只读 readiness packet。",
        "它不执行上传，不声明官方 leaderboard score。",
        "",
        "## 当前状态",
        "",
        f"- preflight status: `{payload['status']}`",
        f"- Space: `{manual['space_url']}`",
        f"- target submission: `{manual['target_submission_path']}`",
        f"- target result: `{manual['target_result_path']}`",
        "- `external_upload_performed_by_script=false`",
        "- `official_scores_claimed=false`",
        "",
        "## 文件",
        "",
        "- `submission-readiness-report.json`: preflight、表单字段和声明边界。",
        "- `manual-form-fields.json`: Space 表单字段。",
        "- `post-upload-verification.md`: 上传后的公开结果验证步骤。",
        "- `artifact-manifest.json` / `SHA256SUMS`: 完整性记录。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_post_upload_verification(path: Path, payload: dict[str, Any]) -> None:
    target_result = payload["manual_upload"]["target_result_path"]
    lines = [
        "# CP-Bench P17 Post-upload Verification",
        "",
        "上传后必须等公开 storage 出现结果文件，才能更新任何官方提交状态。",
        "",
        "## 验证步骤",
        "",
        "1. 重新运行只读 preflight：",
        "",
        "```bash",
        ".venv/bin/python scripts/cp_bench_hf_gate_preflight.py \\",
        "  --gate-dir docs/hf-evaluation/cp-bench-p17-manual-submission-gate \\",
        "  --json",
        "```",
        "",
        f"2. 确认 `target_result_path` 为 `{target_result}`，且 `target_result_exists=true`。",
        "3. 读取公开 `summary.txt` 后，再决定是否更新 `external_submission_status`。",
        "4. 没有公开结果前，不得宣传 CP-Bench leaderboard score 或 ranking。",
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
        "schema_version": "2026-06-02.cp-bench-hf-submission-packet-manifest.v1",
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
        "external_upload_performed_by_script": False,
        "artifacts": artifacts,
    }
    _write_json(output_dir / "artifact-manifest.json", manifest)
    checksum_lines = [
        f"{artifact['sha256']}  {artifact['path']}" for artifact in artifacts
    ]
    checksum_lines.append(f"{_sha256(output_dir / 'artifact-manifest.json')}  artifact-manifest.json")
    (output_dir / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
