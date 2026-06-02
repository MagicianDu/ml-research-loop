"""Audit CP-Bench public upload readiness without uploading.

The audit consolidates the Gradio submission dry-run, public result watcher, and
local environment checks into one artifact that states whether an explicit
human-approved upload can be attempted.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_GRADIO_PLAN = Path(
    "docs/hf-evaluation/cp-bench-p17-gradio-submission-dry-run/gradio-submission-plan.json"
)
DEFAULT_PUBLIC_WATCH = Path(
    "docs/hf-evaluation/cp-bench-p17-public-result-watch/public-result-watch.json"
)
DEFAULT_OUTPUT_DIR = Path("docs/hf-evaluation/cp-bench-p17-upload-readiness-audit")
DEFAULT_GATE_DIR = Path("docs/hf-evaluation/cp-bench-p17-manual-submission-gate")
INSTALL_COMMAND = "pip install 'ml-research-loop[hf-cp-bench]'"


def build_upload_readiness_audit(
    *,
    output_dir: Path,
    gradio_plan: dict[str, Any] | None = None,
    public_watch: dict[str, Any] | None = None,
    environment_probe: dict[str, Any] | None = None,
    dependency_probe: dict[str, Any] | None = None,
    gradio_plan_path: Path = DEFAULT_GRADIO_PLAN,
    public_watch_path: Path = DEFAULT_PUBLIC_WATCH,
) -> dict[str, Any]:
    """Write a local-only upload readiness audit."""
    gradio_plan = gradio_plan or _read_json(gradio_plan_path)
    public_watch = public_watch or _read_json(public_watch_path)
    environment_probe = environment_probe or probe_environment()
    dependency_probe = dependency_probe or probe_dependency_declaration()

    blockers = _collect_blockers(gradio_plan, environment_probe, dependency_probe)
    notes = _collect_non_blocking_notes(gradio_plan, environment_probe)
    ready_for_public_upload_attempt = not blockers and bool(gradio_plan.get("would_upload"))
    claimable_public_result = bool(public_watch.get("claimable_public_result"))
    status = _audit_status(
        blockers=blockers,
        ready_for_public_upload_attempt=ready_for_public_upload_attempt,
        claimable_public_result=claimable_public_result,
    )

    payload = {
        "schema_version": "2026-06-02.cp-bench-upload-readiness-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ready_for_public_upload_attempt": ready_for_public_upload_attempt,
        "claimable_public_result": claimable_public_result,
        "blockers": blockers,
        "non_blocking_notes": notes,
        "next_action": _next_action(status),
        "inputs": {
            "gradio_plan_status": gradio_plan.get("status"),
            "space_api_contract_status": (gradio_plan.get("space_api_contract") or {}).get("status"),
            "public_watch_status": public_watch.get("status"),
            "target_submission_exists": (gradio_plan.get("preflight") or {}).get(
                "target_submission_exists"
            ),
            "target_result_exists": public_watch.get("target_result_exists"),
            "target_submission_path": (gradio_plan.get("preflight") or {}).get(
                "target_submission_path"
            ),
            "target_result_path": (
                public_watch.get("target_result_path")
                or (gradio_plan.get("preflight") or {}).get("target_result_path")
            ),
        },
        "environment_probe": environment_probe,
        "dependency_probe": dependency_probe,
        "approval_commands": _approval_commands(),
        "external_upload_performed_by_script": False,
        "official_scores_claimed": False,
        "external_submission_status": (
            "submitted" if claimable_public_result else "not_submitted"
        ),
        "claim_boundary": (
            "Upload readiness audit only. It never uploads and never claims an "
            "official CP-Bench score. A promotable result requires a public "
            "summary.txt for the target submission."
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "upload-readiness-audit.json", payload)
    _write_readme(output_dir / "README.md", payload)
    _write_manifest(output_dir, payload)
    return payload


def probe_environment() -> dict[str, Any]:
    """Probe local tooling needed for scripted or diagnostic upload paths."""
    return {
        "gradio_client_installed": importlib.util.find_spec("gradio_client") is not None,
        "huggingface_hub_installed": importlib.util.find_spec("huggingface_hub") is not None,
        "hf_cli_installed": shutil.which("hf") is not None,
    }


def probe_dependency_declaration(pyproject_path: Path = Path("pyproject.toml")) -> dict[str, Any]:
    """Probe whether the install extra declares the Space submission client."""
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    cp_bench_extra = pyproject["project"]["optional-dependencies"]["hf-cp-bench"]
    return {
        "hf_cp_bench_extra_declares_gradio_client": (
            "gradio_client>=2.5.0" in cp_bench_extra
        ),
        "install_command": INSTALL_COMMAND,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write a local-only CP-Bench upload readiness audit."
    )
    parser.add_argument("--gradio-plan", type=Path, default=DEFAULT_GRADIO_PLAN)
    parser.add_argument("--public-watch", type=Path, default=DEFAULT_PUBLIC_WATCH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_upload_readiness_audit(
        output_dir=args.output_dir,
        gradio_plan_path=args.gradio_plan,
        public_watch_path=args.public_watch,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _collect_blockers(
    gradio_plan: dict[str, Any],
    environment_probe: dict[str, Any],
    dependency_probe: dict[str, Any],
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    preflight = gradio_plan.get("preflight") or {}
    gate_validation = preflight.get("gate_validation") or {}
    space_contract = gradio_plan.get("space_api_contract") or {}

    if gate_validation.get("status") != "valid":
        blockers.append({"id": "invalid_gate", "severity": "hard", "scope": "submission_gate"})
    if preflight.get("target_submission_exists"):
        blockers.append(
            {"id": "target_submission_already_exists", "severity": "hard", "scope": "hf_storage"}
        )
    if preflight.get("target_result_exists"):
        blockers.append(
            {"id": "target_result_already_exists", "severity": "hard", "scope": "hf_storage"}
        )
    if space_contract.get("status") == "unreadable":
        blockers.append(
            {"id": "space_config_unreadable", "severity": "hard", "scope": "gradio_upload"}
        )
    elif space_contract.get("status") not in {"matched", None}:
        blockers.append(
            {"id": "space_contract_mismatch", "severity": "hard", "scope": "gradio_upload"}
        )
    if not environment_probe.get("gradio_client_installed"):
        blockers.append(
            {
                "id": "missing_gradio_client",
                "severity": "hard",
                "scope": "scripted_gradio_upload",
            }
        )
    if not dependency_probe.get("hf_cp_bench_extra_declares_gradio_client"):
        blockers.append(
            {
                "id": "missing_gradio_client_dependency_declaration",
                "severity": "hard",
                "scope": "scripted_gradio_upload",
            }
        )
    return blockers


def _collect_non_blocking_notes(
    gradio_plan: dict[str, Any],
    environment_probe: dict[str, Any],
) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    preflight = gradio_plan.get("preflight") or {}
    if preflight.get("status") == "blocked_missing_hf_auth":
        notes.append({"id": "hf_auth_missing_for_direct_storage", "scope": "direct_storage_upload"})
    if not environment_probe.get("hf_cli_installed"):
        notes.append({"id": "hf_cli_missing", "scope": "manual_diagnostics"})
    return notes


def _audit_status(
    *,
    blockers: list[dict[str, str]],
    ready_for_public_upload_attempt: bool,
    claimable_public_result: bool,
) -> str:
    if claimable_public_result:
        return "public_result_available_for_claim_review"
    if blockers:
        return "blocked_before_public_upload"
    if ready_for_public_upload_attempt:
        return "ready_for_explicit_public_upload_approval"
    return "not_ready_for_public_upload"


def _next_action(status: str) -> str:
    if status == "ready_for_explicit_public_upload_approval":
        return "request_explicit_human_approval_for_cp_bench_space_upload"
    if status == "blocked_before_public_upload":
        return "resolve_hard_blockers_then_regenerate_gradio_plan"
    if status == "public_result_available_for_claim_review":
        return "verify_public_summary_and_prepare_promotional_claim"
    return "rerun_readiness_after_refreshing_inputs"


def _approval_commands() -> dict[str, str]:
    gate_dir = DEFAULT_GATE_DIR.as_posix()
    gradio_output = DEFAULT_GRADIO_PLAN.parent.as_posix()
    watch_output = DEFAULT_PUBLIC_WATCH.parent.as_posix()
    readiness_output = DEFAULT_OUTPUT_DIR.as_posix()
    return {
        "scripted_gradio_upload": (
            ".venv/bin/python scripts/cp_bench_hf_gradio_submission.py "
            f"--gate-dir {gate_dir} "
            f"--output-dir {gradio_output} "
            "--confirm-public-upload "
            "--human-approval-note '<explicit approval note>'"
        ),
        "post_upload_watch": (
            ".venv/bin/python scripts/cp_bench_hf_public_result_watcher.py "
            f"--gate-dir {gate_dir} "
            f"--output-dir {watch_output}"
        ),
        "readiness_refresh": (
            ".venv/bin/python scripts/cp_bench_hf_upload_readiness_audit.py "
            f"--output-dir {readiness_output}"
        ),
    }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_readme(path: Path, payload: dict[str, Any]) -> None:
    dependency_probe = payload["dependency_probe"]
    approval_commands = payload["approval_commands"]
    lines = [
        "# CP-Bench P17 Upload Readiness Audit",
        "",
        "本目录汇总公开上传前的本地状态；它不执行上传。",
        "",
        "## 当前状态",
        "",
        f"- status: `{payload['status']}`",
        f"- ready_for_public_upload_attempt: `{str(payload['ready_for_public_upload_attempt']).lower()}`",
        f"- claimable_public_result: `{str(payload['claimable_public_result']).lower()}`",
        f"- blockers: `{len(payload['blockers'])}`",
        f"- next_action: `{payload['next_action']}`",
        "- `external_upload_performed_by_script=false`",
        "- `official_scores_claimed=false`",
        "",
        "只有公开 `summary.txt` 出现后，才允许进入宣传 claim review。",
        "",
        "## 依赖证据",
        "",
        (
            "- hf-cp-bench extra declares gradio_client: "
            f"`{str(dependency_probe['hf_cp_bench_extra_declares_gradio_client']).lower()}`"
        ),
        f"- install_command: `{dependency_probe['install_command']}`",
        "",
        "## 明确批准后命令",
        "",
        "第一条命令只有在用户明确批准真实公开上传后才可执行。",
        "",
        "### 公开上传",
        "",
        "```bash",
        approval_commands["scripted_gradio_upload"],
        "```",
        "",
        "### 上传后检查公开结果",
        "",
        "```bash",
        approval_commands["post_upload_watch"],
        "```",
        "",
        "### 刷新 readiness audit",
        "",
        "```bash",
        approval_commands["readiness_refresh"],
        "```",
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
        "schema_version": "2026-06-02.cp-bench-upload-readiness-audit-manifest.v1",
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
