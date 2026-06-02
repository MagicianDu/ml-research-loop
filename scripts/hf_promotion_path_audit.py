"""Build a promotion-path audit for Hugging Face external proof candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CP_READINESS = Path(
    "docs/hf-evaluation/cp-bench-p18-upload-readiness-audit/upload-readiness-audit.json"
)
DEFAULT_CP_PUBLIC_WATCH = Path(
    "docs/hf-evaluation/cp-bench-p18-public-result-watch/public-result-watch.json"
)
DEFAULT_CP_COMPETITIVENESS = Path(
    "docs/hf-evaluation/cp-bench-p18-leaderboard-competitiveness-audit/"
    "leaderboard-competitiveness-audit.json"
)
DEFAULT_DCP_LOCAL_EVAL = Path(
    "docs/hf-evaluation/dcp-bench-open-p4-expanded-eval/"
    "dcp-bench-open-local-eval-report.json"
)
DEFAULT_OUTPUT_DIR = Path("docs/hf-evaluation/promotion-path-audit")


def build_promotion_path_audit(
    *,
    output_dir: Path,
    cp_readiness: dict[str, Any] | None = None,
    cp_public_watch: dict[str, Any] | None = None,
    cp_competitiveness: dict[str, Any] | None = None,
    dcp_local_eval: dict[str, Any] | None = None,
    dcp_external_probe: dict[str, Any] | None = None,
    cp_readiness_path: Path = DEFAULT_CP_READINESS,
    cp_public_watch_path: Path = DEFAULT_CP_PUBLIC_WATCH,
    cp_competitiveness_path: Path = DEFAULT_CP_COMPETITIVENESS,
    dcp_local_eval_path: Path = DEFAULT_DCP_LOCAL_EVAL,
) -> dict[str, Any]:
    """Write a local audit that chooses the next promotion path."""
    cp_readiness = cp_readiness or _read_json(cp_readiness_path)
    cp_public_watch = cp_public_watch or _read_json(cp_public_watch_path)
    cp_competitiveness = cp_competitiveness or _read_json(cp_competitiveness_path)
    dcp_local_eval = dcp_local_eval or _read_json(dcp_local_eval_path)
    dcp_external_probe = dcp_external_probe or _default_dcp_external_probe()

    cp_path = _cp_bench_path(cp_readiness, cp_public_watch, cp_competitiveness)
    dcp_path = _dcp_bench_open_path(dcp_local_eval, dcp_external_probe)
    claimable = bool(cp_public_watch.get("claimable_public_result"))
    status = (
        "public_result_available_for_claim_review"
        if claimable
        else "not_promotable_yet"
    )
    recommended_next_action = _recommended_next_action(
        status=status,
        cp_path=cp_path,
        dcp_path=dcp_path,
    )

    payload = {
        "schema_version": "2026-06-02.hf-promotion-path-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "real_leaderboard_result_claimable": claimable,
        "recommended_next_action": recommended_next_action,
        "paths": {
            "cp_bench": cp_path,
            "dcp_bench_open": dcp_path,
        },
        "official_scores_claimed": False,
        "external_submission_status": "submitted" if claimable else "not_submitted",
        "claim_boundary": (
            "Promotion-path audit only. It may identify a route toward a public "
            "leaderboard result, but it does not upload, submit, or claim an "
            "official score by itself."
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "promotion-path-audit.json", payload)
    _write_readme(output_dir / "README.md", payload)
    _write_manifest(output_dir, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a local promotion-path audit for HF proof candidates."
    )
    parser.add_argument("--cp-readiness", type=Path, default=DEFAULT_CP_READINESS)
    parser.add_argument("--cp-public-watch", type=Path, default=DEFAULT_CP_PUBLIC_WATCH)
    parser.add_argument(
        "--cp-competitiveness",
        type=Path,
        default=DEFAULT_CP_COMPETITIVENESS,
    )
    parser.add_argument("--dcp-local-eval", type=Path, default=DEFAULT_DCP_LOCAL_EVAL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dcp-hf-org-url", default="https://huggingface.co/DCP-Bench-Open")
    parser.add_argument("--dcp-public-models", type=int, default=0)
    parser.add_argument("--dcp-public-datasets", type=int, default=0)
    parser.add_argument("--dcp-public-spaces", type=int, default=0)
    parser.add_argument("--dcp-external-checked-at", default="")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_promotion_path_audit(
        output_dir=args.output_dir,
        cp_readiness_path=args.cp_readiness,
        cp_public_watch_path=args.cp_public_watch,
        cp_competitiveness_path=args.cp_competitiveness,
        dcp_local_eval_path=args.dcp_local_eval,
        dcp_external_probe={
            "source_url": args.dcp_hf_org_url,
            "public_models": args.dcp_public_models,
            "public_datasets": args.dcp_public_datasets,
            "public_spaces": args.dcp_public_spaces,
            "checked_at": args.dcp_external_checked_at,
        },
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _cp_bench_path(
    cp_readiness: dict[str, Any],
    cp_public_watch: dict[str, Any],
    cp_competitiveness: dict[str, Any],
) -> dict[str, Any]:
    candidate = cp_competitiveness.get("local_candidate") or {}
    snapshot = cp_competitiveness.get("public_verified_leaderboard_snapshot") or {}
    target_public_result = cp_public_watch.get("target_public_result") or {}
    target_result_exists = bool(cp_public_watch.get("target_result_exists"))

    if target_result_exists:
        route_state = "public_result_available"
    elif cp_readiness.get("ready_for_public_upload_attempt"):
        route_state = "ready_for_explicit_upload_approval_not_uploaded"
    elif cp_readiness.get("blockers"):
        route_state = "blocked_before_upload"
    else:
        route_state = "not_ready_for_upload"

    return {
        "benchmark": "CP-Bench",
        "route_state": route_state,
        "target_result_path": cp_public_watch.get("target_result_path"),
        "target_result_exists": target_result_exists,
        "ready_for_public_upload_attempt": bool(
            cp_readiness.get("ready_for_public_upload_attempt")
        ),
        "claimable_public_result": bool(cp_public_watch.get("claimable_public_result")),
        "local_final_solution_accuracy_percent": candidate.get(
            "final_solution_accuracy_percent"
        ),
        "runtime_success": candidate.get("runtime_success"),
        "would_rank_if_uploaded": (
            target_public_result.get("public_rank")
            or snapshot.get("local_candidate_would_rank")
        ),
        "would_beat_public_entries": snapshot.get("would_beat_public_entries"),
        "public_entry_count": snapshot.get("entry_count"),
        "lowest_public_accuracy_percent": snapshot.get("lowest_public_accuracy_percent"),
        "promotional_strength": _cp_promotional_strength(snapshot),
        "upstream_archived": bool(cp_competitiveness.get("target_is_archived_by_upstream")),
        "upstream_successor": cp_competitiveness.get("upstream_successor"),
        "official_scores_claimed": False,
        "external_submission_status": (
            "submitted" if target_result_exists else "not_submitted"
        ),
    }


def _dcp_bench_open_path(
    dcp_local_eval: dict[str, Any],
    external_probe: dict[str, Any],
) -> dict[str, Any]:
    live_entries = {
        "models": int(external_probe.get("public_models") or 0),
        "datasets": int(external_probe.get("public_datasets") or 0),
        "spaces": int(external_probe.get("public_spaces") or 0),
    }
    has_public_route = any(live_entries.values())
    route_state = (
        "public_route_detected_requires_submission_gate"
        if has_public_route
        else "strong_local_eval_no_public_leaderboard_route"
    )
    return {
        "benchmark": "DCP-Bench-Open",
        "route_state": route_state,
        "local_final_solution_accuracy_percent": dcp_local_eval.get(
            "final_solution_accuracy_percent"
        ),
        "submitted_solution_accuracy_percent": dcp_local_eval.get(
            "submitted_solution_accuracy_percent"
        ),
        "runtime_success": (
            f"{dcp_local_eval.get('models_ran_successfully')}/"
            f"{dcp_local_eval.get('models_ran_successfully_denominator')}"
        ),
        "submitted_models": dcp_local_eval.get("total_submitted_models"),
        "dcp_problem_count": dcp_local_eval.get("dcp_problem_count"),
        "dcp_release": dcp_local_eval.get("dcp_release"),
        "live_hf_org_url": external_probe.get("source_url"),
        "live_hf_public_entries": live_entries,
        "external_probe_checked_at": external_probe.get("checked_at"),
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
    }


def _cp_promotional_strength(snapshot: dict[str, Any]) -> str:
    would_rank = snapshot.get("local_candidate_would_rank")
    would_beat = snapshot.get("would_beat_public_entries")
    if would_rank is None:
        return "unknown_until_public_result"
    if would_rank <= 10:
        return "strong_public_rank"
    if would_beat and would_beat > 0:
        return "entry_level_public_rank"
    return "not_worth_public_submission_yet"


def _recommended_next_action(
    *,
    status: str,
    cp_path: dict[str, Any],
    dcp_path: dict[str, Any],
) -> str:
    if status == "public_result_available_for_claim_review":
        return "verify_public_summary_and_prepare_bounded_promotional_claim"
    if cp_path["route_state"] == "ready_for_explicit_upload_approval_not_uploaded":
        return "request_explicit_human_approval_for_cp_bench_space_upload"
    if dcp_path["route_state"] == "public_route_detected_requires_submission_gate":
        return "build_dcp_bench_open_public_submission_gate"
    return "improve_local_candidate_or_find_public_leaderboard_route"


def _default_dcp_external_probe() -> dict[str, Any]:
    return {
        "source_url": "https://huggingface.co/DCP-Bench-Open",
        "public_models": 0,
        "public_datasets": 0,
        "public_spaces": 0,
        "checked_at": "",
    }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_readme(output_path: Path, payload: dict[str, Any]) -> None:
    cp_path = payload["paths"]["cp_bench"]
    dcp_path = payload["paths"]["dcp_bench_open"]
    live_entries = dcp_path["live_hf_public_entries"]
    lines = [
        "# HF Promotion Path Audit",
        "",
        "本目录判断当前哪条外部 proof 路线最接近可宣传榜单结果。",
        "",
        "## 当前状态",
        "",
        f"- status: `{payload['status']}`",
        (
            "- real_leaderboard_result_claimable: "
            f"`{str(payload['real_leaderboard_result_claimable']).lower()}`"
        ),
        f"- recommended_next_action: `{payload['recommended_next_action']}`",
        "- `official_scores_claimed=false`",
        f"- external_submission_status: `{payload['external_submission_status']}`",
        "",
        "当前不得宣传为官方榜单结果，除非公开结果文件已经出现并通过 claim review。",
        "",
        "## CP-Bench",
        "",
        f"- route_state: `{cp_path['route_state']}`",
        f"- target_result_exists: `{str(cp_path['target_result_exists']).lower()}`",
        (
            "- local_final_solution_accuracy_percent: "
            f"`{cp_path['local_final_solution_accuracy_percent']}`"
        ),
        f"- would_rank_if_uploaded: `{cp_path['would_rank_if_uploaded']}`",
        f"- promotional_strength: `{cp_path['promotional_strength']}`",
        "",
        "## DCP-Bench-Open",
        "",
        f"- route_state: `{dcp_path['route_state']}`",
        (
            "- local_final_solution_accuracy_percent: "
            f"`{dcp_path['local_final_solution_accuracy_percent']}`"
        ),
        (
            "- submitted_solution_accuracy_percent: "
            f"`{dcp_path['submitted_solution_accuracy_percent']}`"
        ),
        f"- live_hf_org_url: `{dcp_path['live_hf_org_url']}`",
        (
            "- live_hf_public_entries: "
            f"`models={live_entries['models']}, "
            f"datasets={live_entries['datasets']}, "
            f"spaces={live_entries['spaces']}`"
        ),
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


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
        "schema_version": "2026-06-02.hf-promotion-path-audit-manifest.v1",
        "status": payload["status"],
        "official_scores_claimed": False,
        "external_submission_status": payload["external_submission_status"],
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
