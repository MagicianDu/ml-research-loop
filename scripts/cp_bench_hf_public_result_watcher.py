"""Watch for a public CP-Bench result and build a claim-boundary artifact.

This script is read-only. It inspects public Hugging Face storage, parses
published CP-Bench summary files, and records whether the target result is
publicly claimable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.cp_bench_hf_gate_preflight import (
    DATASET_REPO_ID,
    DEFAULT_GATE_DIR,
    VERIFIED_DATASET_PATH,
    build_preflight,
)


DEFAULT_OUTPUT_DIR = Path("docs/hf-evaluation/cp-bench-p17-public-result-watch")
RESULTS_PREFIX = f"results/{VERIFIED_DATASET_PATH}"
SUMMARY_PATTERN = re.compile(
    r"Total Submitted Models that also exist in the dataset:\s*(?P<submitted>\d+).*?"
    r"Models That Ran Successfully \(out of submitted models\):\s*"
    r"(?P<successful>\d+)\s*/\s*(?P<runtime_denominator>\d+).*?"
    r"Submission coverage perc:\s*(?P<coverage>[0-9.]+)%.*?"
    r"Error perc:\s*(?P<error>[0-9.]+)%.*?"
    r"Consistency perc:\s*(?P<consistency>[0-9.]+)%.*?"
    r"Final Solution Accuracy perc:\s*(?P<accuracy>[0-9.]+)%",
    re.DOTALL,
)


def parse_cp_bench_summary(text: str) -> dict[str, Any]:
    """Parse the official CP-Bench summary footer metrics."""
    match = SUMMARY_PATTERN.search(text)
    if match is None:
        raise ValueError("CP-Bench summary does not contain the expected metrics footer")
    successful = int(match.group("successful"))
    runtime_denominator = int(match.group("runtime_denominator"))
    return {
        "total_submitted_models_in_dataset": int(match.group("submitted")),
        "runtime_success": f"{successful}/{runtime_denominator}",
        "runtime_success_count": successful,
        "runtime_denominator": runtime_denominator,
        "coverage_percent": float(match.group("coverage")),
        "error_percent": float(match.group("error")),
        "consistency_percent": float(match.group("consistency")),
        "final_solution_accuracy_percent": float(match.group("accuracy")),
    }


def build_public_result_watch(
    *,
    gate_dir: Path,
    output_dir: Path,
    api: Any | None = None,
    repo_files: list[str] | None = None,
    summary_texts: dict[str, str] | None = None,
    summary_loader: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Write a read-only public-result watch artifact."""
    preflight = build_preflight(gate_dir, api=api, repo_files=repo_files)
    sanitized_preflight = _sanitize_preflight(preflight, gate_dir)
    public_storage_error = None
    if repo_files is None:
        files, public_storage_error = _list_repo_files(api)
    else:
        files = repo_files

    target_result_path = sanitized_preflight["target_result_path"]
    summary_paths = sorted(
        path
        for path in files
        if path.startswith(f"{RESULTS_PREFIX}/") and path.endswith("/summary.txt")
    )
    entries, parse_errors = _load_public_entries(
        summary_paths=summary_paths,
        target_result_path=target_result_path,
        summary_texts=summary_texts or {},
        summary_loader=summary_loader,
    )
    snapshot = _build_public_snapshot(entries)
    target_entry = next(
        (entry for entry in entries if entry["summary_path"] == target_result_path),
        None,
    )
    target_result_exists = target_entry is not None
    status = "public_result_available" if target_result_exists else "waiting_for_public_result"
    if sanitized_preflight["gate_validation"]["status"] != "valid":
        status = "blocked_invalid_gate"
    elif public_storage_error is not None:
        status = "blocked_public_storage_unreadable"
    elif parse_errors and not target_result_exists:
        status = "waiting_for_public_result_with_parse_warnings"

    payload: dict[str, Any] = {
        "schema_version": "2026-06-02.cp-bench-public-result-watch.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "dataset_repo_id": DATASET_REPO_ID,
        "dataset_version_path": VERIFIED_DATASET_PATH,
        "source_results_prefix": RESULTS_PREFIX,
        "gate_dir": _display_path(gate_dir),
        "preflight": sanitized_preflight,
        "target_result_path": target_result_path,
        "target_result_exists": target_result_exists,
        "target_public_result": (
            _augment_target_entry(target_entry, snapshot) if target_entry else None
        ),
        "public_verified_leaderboard_snapshot": snapshot,
        "public_storage_error": public_storage_error,
        "parse_errors": parse_errors,
        "claimable_public_result": target_result_exists,
        "external_upload_performed_by_script": False,
        "official_scores_claimed": False,
        "external_submission_status": "submitted" if target_result_exists else "not_submitted",
        "promotion_boundary": _promotion_boundary(target_result_exists),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "public-result-watch.json", payload)
    _write_readme(output_dir / "README.md", payload)
    _write_manifest(output_dir, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write a read-only CP-Bench public result watch artifact."
    )
    parser.add_argument("--gate-dir", type=Path, default=DEFAULT_GATE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_public_result_watch(gate_dir=args.gate_dir, output_dir=args.output_dir)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _list_repo_files(api: Any | None) -> tuple[list[str], dict[str, str] | None]:
    if api is None:
        api = _new_hf_api()
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            files = api.list_repo_files(repo_id=DATASET_REPO_ID, repo_type="dataset")
            return files, None
        except Exception as exc:  # pragma: no cover - depends on network state.
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
    assert last_error is not None
    return [], {
        "error_type": type(last_error).__name__,
        "message": str(last_error).splitlines()[0] if str(last_error) else "",
    }


def _new_hf_api() -> Any:
    from huggingface_hub import HfApi

    return HfApi()


def _load_public_entries(
    *,
    summary_paths: list[str],
    target_result_path: str,
    summary_texts: dict[str, str],
    summary_loader: Callable[[str], str] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in summary_paths:
        try:
            text = summary_texts[path] if path in summary_texts else _load_summary(path, summary_loader)
            metrics = parse_cp_bench_summary(text)
        except Exception as exc:  # pragma: no cover - exact network/cache errors vary.
            if path == target_result_path:
                errors.append(
                    {
                        "summary_path": path,
                        "error_type": type(exc).__name__,
                        "message": str(exc).splitlines()[0] if str(exc) else "",
                    }
                )
            continue
        entries.append(
            {
                "name": _entry_name_from_summary_path(path),
                "summary_path": path,
                **metrics,
            }
        )
    return entries, errors


def _load_summary(path: str, summary_loader: Callable[[str], str] | None) -> str:
    if summary_loader is not None:
        return summary_loader(path)

    from huggingface_hub import hf_hub_download

    downloaded = hf_hub_download(
        repo_id=DATASET_REPO_ID,
        repo_type="dataset",
        filename=path,
    )
    return Path(downloaded).read_text(encoding="utf-8")


def _build_public_snapshot(entries: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        entries,
        key=lambda entry: (
            -entry["final_solution_accuracy_percent"],
            entry["name"],
        ),
    )
    for index, entry in enumerate(ranked, start=1):
        entry["public_rank"] = index
    lowest = ranked[-1] if ranked else None
    top = ranked[0] if ranked else None
    return {
        "entry_count": len(ranked),
        "top_accuracy_percent": top["final_solution_accuracy_percent"] if top else None,
        "lowest_public_accuracy_percent": (
            lowest["final_solution_accuracy_percent"] if lowest else None
        ),
        "entries": ranked,
    }


def _augment_target_entry(
    target_entry: dict[str, Any] | None,
    snapshot: dict[str, Any],
) -> dict[str, Any] | None:
    if target_entry is None:
        return None
    accuracy = target_entry["final_solution_accuracy_percent"]
    return {
        **target_entry,
        "public_entry_count": snapshot["entry_count"],
        "would_beat_public_entries": sum(
            1
            for entry in snapshot["entries"]
            if entry["summary_path"] != target_entry["summary_path"]
            and entry["final_solution_accuracy_percent"] < accuracy
        ),
    }


def _promotion_boundary(target_result_exists: bool) -> dict[str, Any]:
    if target_result_exists:
        return {
            "status": "public_result_can_be_quoted_with_source",
            "allowed_claim": (
                "可以引用公开 summary.txt 中的 Final Solution Accuracy 和排名快照，"
                "但必须同时说明 CP-Bench 已被 DCP-Bench-Open 取代。"
            ),
            "forbidden_claims": [
                "不得声称这是 DCP-Bench-Open 官方成绩。",
                "不得隐去 CP-Bench archived/upstream successor 边界。",
            ],
        }
    return {
        "status": "no_public_result_yet",
        "allowed_claim": "只能说明本地 gate/dry-run 已准备好，不能宣传 CP-Bench 官方分数或排名。",
        "forbidden_claims": [
                "不得把本地 evaluator 结果写成官方成绩。",
            "不得声称已出现在 CP-Bench leaderboard。",
        ],
    }


def _entry_name_from_summary_path(path: str) -> str:
    parts = path.split("/")
    return parts[-2] if len(parts) >= 2 else path


def _sanitize_preflight(preflight: dict[str, Any], gate_dir: Path) -> dict[str, Any]:
    sanitized = json.loads(json.dumps(preflight))
    sanitized["gate_validation"]["gate_dir"] = _display_path(gate_dir)
    return sanitized


def _write_readme(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CP-Bench Public Result Watch",
        "",
        "本目录是只读公开结果 watcher，不执行上传。",
        "",
        "## 当前状态",
        "",
        f"- status: `{payload['status']}`",
        f"- target result: `{payload['target_result_path']}`",
        f"- target_result_exists: `{str(payload['target_result_exists']).lower()}`",
        f"- claimable_public_result: `{str(payload['claimable_public_result']).lower()}`",
        "- `external_upload_performed_by_script=false`",
        "- `official_scores_claimed=false`",
        "",
        "没有公开 `summary.txt` 前，不得宣传 CP-Bench leaderboard score 或 ranking。",
        "",
        "## 文件",
        "",
        "- `public-result-watch.json`: 公开 storage、summary 解析、排名快照和宣传边界。",
        "- `artifact-manifest.json` / `SHA256SUMS`: 完整性记录。",
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
        "schema_version": "2026-06-02.cp-bench-public-result-watch-manifest.v1",
        "status": payload["status"],
        "official_scores_claimed": False,
        "external_submission_status": payload["external_submission_status"],
        "external_upload_performed_by_script": False,
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


def _display_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.name


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
