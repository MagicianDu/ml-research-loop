"""Build a guarded CP-Bench Gradio Space submission plan.

Default behavior is a dry-run artifact only. A public upload can only be
attempted when the caller passes an explicit confirmation flag and a human
approval note.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.cp_bench_hf_gate_preflight import DEFAULT_GATE_DIR, build_preflight
from scripts.cp_bench_hf_submission_packet import SPACE_REPO_ID, SPACE_URL


DEFAULT_OUTPUT_DIR = Path("docs/hf-evaluation/cp-bench-p17-gradio-submission-dry-run")
SPACE_CONFIG_URL = "https://kostis-init-cp-bench-leaderboard.hf.space/config"
SPACE_CLIENT_TARGET = SPACE_REPO_ID
SPACE_GRADIO_API_NAME = "/handle_upload"
RAW_SPACE_GRADIO_API_NAME = SPACE_GRADIO_API_NAME.removeprefix("/")
EXPECTED_SPACE_INPUTS = [
    ("submission_name", "Submission Name (required)", "textbox"),
    ("submission_file", "Upload Submission File (required, .jsonl)", "file"),
    ("report_file", "Upload PDF Report (optional, but recommended)", "file"),
    ("model_framework", "Modelling Framework (required)", "dropdown"),
    ("base_llm", "Base LLM (required)", "textbox"),
    ("dataset_version", "Dataset Version (required)", "dropdown"),
]


def build_gradio_submission_plan(
    *,
    gate_dir: Path,
    output_dir: Path,
    api: Any | None = None,
    repo_files: list[str] | None = None,
    space_config: dict[str, Any] | None = None,
    probe_space_config: bool = True,
    confirm_public_upload: bool = False,
    human_approval_note: str | None = None,
    client_factory: Callable[[str], Any] | None = None,
    file_adapter: Callable[[Path], Any] | None = None,
) -> dict[str, Any]:
    """Write a dry-run plan, or guardedly submit through the CP-Bench Space."""
    preflight = build_preflight(gate_dir, api=api, repo_files=repo_files)
    sanitized_preflight = _sanitize_preflight(preflight, gate_dir)
    space_api_contract = build_space_api_contract(
        space_config=space_config,
        probe_space_config=probe_space_config,
    )
    gate_validation = sanitized_preflight["gate_validation"]
    gradio_upload = _build_gradio_upload_plan(gate_dir, gate_validation)
    would_upload = _is_gradio_upload_ready(sanitized_preflight, space_api_contract)
    status = _dry_run_status(sanitized_preflight, space_api_contract, would_upload)

    payload: dict[str, Any] = {
        "schema_version": "2026-06-02.cp-bench-hf-gradio-submission-plan.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "gate_dir": _display_path(gate_dir),
        "space_repo_id": SPACE_REPO_ID,
        "space_url": SPACE_URL,
        "space_config_url": SPACE_CONFIG_URL,
        "space_api_contract": space_api_contract,
        "preflight": sanitized_preflight,
        "gradio_upload": gradio_upload,
        "requires_human_approval": True,
        "confirm_public_upload": confirm_public_upload,
        "human_approval_note_recorded": bool(human_approval_note),
        "would_upload": would_upload,
        "external_upload_performed_by_script": False,
        "official_scores_claimed": False,
        "external_submission_status": sanitized_preflight[
            "observed_external_submission_status"
        ],
        "claim_boundary": (
            "Gradio submission plan only unless confirm_public_upload=true and a "
            "human_approval_note is supplied. Without a public result file, this "
            "artifact claims no official CP-Bench leaderboard score or ranking."
        ),
    }

    if confirm_public_upload and would_upload:
        if not human_approval_note:
            payload["status"] = "blocked_missing_human_approval_note"
        else:
            _attempt_gradio_upload(
                payload=payload,
                gate_dir=gate_dir,
                client_factory=client_factory,
                file_adapter=file_adapter,
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "gradio-submission-plan.json", payload)
    _write_readme(output_dir / "README.md", payload)
    _write_manifest(output_dir, payload)
    return payload


def build_space_api_contract(
    *,
    space_config: dict[str, Any] | None = None,
    probe_space_config: bool = True,
) -> dict[str, Any]:
    """Parse the live or injected Gradio config for the handle_upload endpoint."""
    source = "injected_space_config"
    if space_config is None and probe_space_config:
        source = "live_space_config"
        try:
            space_config = _fetch_space_config()
        except Exception as exc:  # pragma: no cover - depends on network state.
            return {
                "schema_version": "2026-06-02.cp-bench-space-api-contract.v1",
                "status": "unreadable",
                "source": source,
                "space_config_url": SPACE_CONFIG_URL,
                "api_name": SPACE_GRADIO_API_NAME,
                "expected_call_order": [name for name, _, _ in EXPECTED_SPACE_INPUTS],
                "error_type": type(exc).__name__,
                "message": str(exc).splitlines()[0] if str(exc) else "",
            }
    elif space_config is None:
        source = "static_expected_contract"
        return {
            "schema_version": "2026-06-02.cp-bench-space-api-contract.v1",
            "status": "not_probed",
            "source": source,
            "space_config_url": SPACE_CONFIG_URL,
            "api_name": SPACE_GRADIO_API_NAME,
            "expected_call_order": [name for name, _, _ in EXPECTED_SPACE_INPUTS],
        }

    dependencies = space_config.get("dependencies", [])
    components = {
        component.get("id"): component
        for component in space_config.get("components", [])
        if isinstance(component, dict)
    }
    dependency = next(
        (
            item
            for item in dependencies
            if isinstance(item, dict)
            and item.get("api_name") == RAW_SPACE_GRADIO_API_NAME
        ),
        None,
    )
    if dependency is None:
        return {
            "schema_version": "2026-06-02.cp-bench-space-api-contract.v1",
            "status": "missing_handle_upload",
            "source": source,
            "space_config_url": SPACE_CONFIG_URL,
            "api_name": SPACE_GRADIO_API_NAME,
            "expected_call_order": [name for name, _, _ in EXPECTED_SPACE_INPUTS],
        }

    input_components = _describe_input_components(dependency, components)
    mismatches = _space_input_mismatches(input_components)
    status = "matched" if not mismatches else "input_order_mismatch"
    return {
        "schema_version": "2026-06-02.cp-bench-space-api-contract.v1",
        "status": status,
        "source": source,
        "space_config_url": SPACE_CONFIG_URL,
        "api_name": SPACE_GRADIO_API_NAME,
        "raw_api_name": dependency.get("api_name"),
        "dependency_id": dependency.get("id"),
        "input_components": input_components,
        "output_component_ids": dependency.get("outputs", []),
        "expected_call_order": [name for name, _, _ in EXPECTED_SPACE_INPUTS],
        "mismatches": mismatches,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write a guarded CP-Bench Gradio Space submission plan."
    )
    parser.add_argument("--gate-dir", type=Path, default=DEFAULT_GATE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--skip-space-config-probe", action="store_true")
    parser.add_argument("--confirm-public-upload", action="store_true")
    parser.add_argument("--human-approval-note")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_gradio_submission_plan(
        gate_dir=args.gate_dir,
        output_dir=args.output_dir,
        probe_space_config=not args.skip_space_config_probe,
        confirm_public_upload=args.confirm_public_upload,
        human_approval_note=args.human_approval_note,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _fetch_space_config() -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(SPACE_CONFIG_URL, timeout=20) as response:
                payload = json.load(response)
            break
        except Exception as exc:  # pragma: no cover - depends on network state.
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
    else:
        assert last_error is not None
        raise last_error
    if not isinstance(payload, dict):
        raise ValueError("Space config response is not a JSON object")
    return payload


def _describe_input_components(
    dependency: dict[str, Any],
    components: dict[Any, dict[str, Any]],
) -> list[dict[str, Any]]:
    described = []
    for slot, component_id in enumerate(dependency.get("inputs", [])):
        component = components.get(component_id, {})
        props = component.get("props", {}) if isinstance(component, dict) else {}
        described.append(
            {
                "slot": slot,
                "component_id": component_id,
                "type": component.get("type") if isinstance(component, dict) else None,
                "label": props.get("label") if isinstance(props, dict) else None,
            }
        )
    return described


def _space_input_mismatches(input_components: list[dict[str, Any]]) -> list[str]:
    mismatches: list[str] = []
    if len(input_components) != len(EXPECTED_SPACE_INPUTS):
        mismatches.append(
            "handle_upload input count mismatch: "
            f"{len(input_components)} != {len(EXPECTED_SPACE_INPUTS)}"
        )
    for index, expected in enumerate(EXPECTED_SPACE_INPUTS):
        if index >= len(input_components):
            break
        expected_name, expected_label, expected_type = expected
        actual = input_components[index]
        actual["expected_name"] = expected_name
        if actual.get("label") != expected_label:
            mismatches.append(
                f"slot {index} label mismatch: {actual.get('label')!r} != {expected_label!r}"
            )
        if actual.get("type") != expected_type:
            mismatches.append(
                f"slot {index} type mismatch: {actual.get('type')!r} != {expected_type!r}"
            )
    return mismatches


def _is_gradio_upload_ready(
    preflight: dict[str, Any],
    space_api_contract: dict[str, Any],
) -> bool:
    return (
        preflight["gate_validation"]["status"] == "valid"
        and preflight["hf_storage"]["status"] == "readable"
        and not preflight["target_submission_exists"]
        and not preflight["target_result_exists"]
        and space_api_contract["status"] == "matched"
    )


def _dry_run_status(
    preflight: dict[str, Any],
    space_api_contract: dict[str, Any],
    would_upload: bool,
) -> str:
    if preflight["gate_validation"]["status"] != "valid":
        return "blocked_invalid_gate"
    if preflight["hf_storage"]["status"] != "readable":
        return "blocked_hf_storage_unreadable"
    if preflight["target_result_exists"]:
        return "public_result_available"
    if preflight["target_submission_exists"]:
        return "submitted_waiting_for_result"
    if space_api_contract["status"] == "unreadable":
        return "blocked_space_config_unreadable"
    if space_api_contract["status"] != "matched":
        return "blocked_space_api_contract_mismatch"
    if would_upload:
        return "dry_run_ready_for_human_approved_space_upload"
    return "blocked_unknown_gradio_readiness"


def _build_gradio_upload_plan(gate_dir: Path, gate_validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "client_target": SPACE_CLIENT_TARGET,
        "space_url": SPACE_URL,
        "api_name": SPACE_GRADIO_API_NAME,
        "submission_name": gate_validation["submission_name"],
        "dataset_version": gate_validation["dataset_version"],
        "model_framework": gate_validation["modelling_framework"],
        "base_llm": gate_validation["base_llm"],
        "submission_file": _display_path(gate_dir / "submission.jsonl"),
        "report_file": _display_path(gate_dir / "approach-report.pdf"),
        "input_order": [name for name, _, _ in EXPECTED_SPACE_INPUTS],
    }


def _attempt_gradio_upload(
    *,
    payload: dict[str, Any],
    gate_dir: Path,
    client_factory: Callable[[str], Any] | None,
    file_adapter: Callable[[Path], Any] | None,
) -> None:
    try:
        client, adapter = _build_client_and_adapter(client_factory, file_adapter)
    except ModuleNotFoundError as exc:
        payload["status"] = "blocked_missing_gradio_client"
        payload["gradio_client_error"] = {
            "error_type": type(exc).__name__,
            "message": str(exc).splitlines()[0] if str(exc) else "",
        }
        return

    upload = payload["gradio_upload"]
    submission_path = gate_dir.expanduser().resolve() / "submission.jsonl"
    report_path = gate_dir.expanduser().resolve() / "approach-report.pdf"
    try:
        response = client.predict(
            upload["submission_name"],
            adapter(submission_path),
            adapter(report_path),
            upload["model_framework"],
            upload["base_llm"],
            upload["dataset_version"],
            api_name=SPACE_GRADIO_API_NAME,
        )
    except Exception as exc:  # pragma: no cover - exact client errors are version-dependent.
        payload["status"] = "gradio_upload_failed"
        payload["external_upload_performed_by_script"] = True
        payload["external_submission_status"] = "unknown_after_upload_attempt"
        payload["gradio_response"] = {
            "status": "exception",
            "error_type": type(exc).__name__,
            "message": str(exc).splitlines()[0] if str(exc) else "",
        }
        return

    payload["external_upload_performed_by_script"] = True
    payload["gradio_response"] = {
        "status": "received",
        "text": str(response),
    }
    if _looks_successful_upload_response(str(response)):
        payload["status"] = "submitted_via_gradio_pending_public_result"
        payload["external_submission_status"] = "submitted"
    else:
        payload["status"] = "gradio_upload_rejected_or_failed"
        payload["external_submission_status"] = "unknown_after_upload_attempt"


def _build_client_and_adapter(
    client_factory: Callable[[str], Any] | None,
    file_adapter: Callable[[Path], Any] | None,
) -> tuple[Any, Callable[[Path], Any]]:
    if client_factory is not None:
        return client_factory(SPACE_CLIENT_TARGET), file_adapter or (lambda path: str(path))

    from gradio_client import Client, handle_file

    return Client(SPACE_CLIENT_TARGET), file_adapter or handle_file


def _looks_successful_upload_response(response: str) -> bool:
    normalized = response.lower()
    negative_markers = ("failed", "invalid", "error", "required", "exists")
    return "uploaded" in normalized and not any(marker in normalized for marker in negative_markers)


def _sanitize_preflight(preflight: dict[str, Any], gate_dir: Path) -> dict[str, Any]:
    sanitized = json.loads(json.dumps(preflight))
    sanitized["gate_validation"]["gate_dir"] = _display_path(gate_dir)
    return sanitized


def _write_readme(path: Path, payload: dict[str, Any]) -> None:
    upload = payload["gradio_upload"]
    lines = [
        "# CP-Bench Gradio Submission Dry Run",
        "",
        "本目录记录一次 CP-Bench Space Gradio 表单提交计划。",
        "默认状态不会上传；只有显式确认公开上传并记录人工批准说明时，脚本才会调用 Gradio 客户端。",
        "",
        "## 当前状态",
        "",
        f"- status: `{payload['status']}`",
        f"- Space: `{payload['space_url']}`",
        f"- API: `{upload['api_name']}`",
        f"- submission name: `{upload['submission_name']}`",
        f"- target result: `{payload['preflight']['target_result_path']}`",
        "- `external_upload_performed_by_script="
        f"{str(payload['external_upload_performed_by_script']).lower()}`",
        "- `official_scores_claimed=false`；公开结果文件出现前不得宣传榜单成绩或排名。",
        "",
        "## 文件",
        "",
        "- `gradio-submission-plan.json`: gate、Space API 合约、表单参数和声明边界。",
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
        "schema_version": "2026-06-02.cp-bench-hf-gradio-submission-manifest.v1",
        "status": payload["status"],
        "official_scores_claimed": False,
        "external_submission_status": payload["external_submission_status"],
        "external_upload_performed_by_script": payload[
            "external_upload_performed_by_script"
        ],
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
