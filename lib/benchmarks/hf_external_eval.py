"""Hugging Face external evaluation target planning."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "2026-05-18.hf-external-eval-plan.v1"
DEFAULT_SHORTLIST_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "hf-evaluation" / "target-shortlist.json"
)
REQUIRED_TARGET_FIELDS = {
    "target_id",
    "name",
    "hf_kind",
    "task_family",
    "urls",
    "primary_metric",
    "submission_mode",
    "resource_fit",
    "product_fit_score",
    "recommended_phase",
    "why_match",
    "risks",
    "acceptance",
    "claim_boundary",
}


def load_hf_eval_targets(shortlist_path: Path | None = None) -> dict[str, Any]:
    """Load and validate the HF external evaluation target shortlist."""
    path = (shortlist_path or DEFAULT_SHORTLIST_PATH).expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("HF eval shortlist must be a JSON object")
    if payload.get("official_scores_claimed") is not False:
        raise ValueError("HF eval shortlist must preserve official_scores_claimed=false")
    targets = payload.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("HF eval shortlist targets must be a non-empty list")

    seen_ids: set[str] = set()
    for index, target in enumerate(targets):
        _validate_target(target, index)
        target_id = target["target_id"]
        if target_id in seen_ids:
            raise ValueError(f"duplicate HF eval target_id: {target_id}")
        seen_ids.add(target_id)
    return payload


def select_hf_eval_targets(
    payload: dict[str, Any],
    *,
    task_family: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return targets sorted by product fit and phase for a planner/client."""
    targets = payload.get("targets")
    if not isinstance(targets, list):
        raise ValueError("HF eval payload targets must be a list")
    filtered = [
        target
        for target in targets
        if isinstance(target, dict)
        and (task_family is None or target.get("task_family") == task_family)
    ]
    filtered.sort(
        key=lambda target: (
            -int(target.get("product_fit_score", 0)),
            str(target.get("recommended_phase", "")),
            str(target.get("target_id", "")),
        )
    )
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be positive")
        return filtered[:limit]
    return filtered


def build_hf_external_eval_plan(
    *,
    shortlist_path: Path | None = None,
    target_id: str | None = None,
) -> dict[str, Any]:
    """Build a conservative proof plan for one HF external evaluation target."""
    shortlist = load_hf_eval_targets(shortlist_path)
    selected = _select_target(shortlist, target_id)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "planned",
        "official_scores_claimed": False,
        "target": selected,
        "claim_boundary": selected["claim_boundary"],
        "default_next_step": _default_next_step(selected),
        "phases": [
            {
                "phase": "P0",
                "goal": "live verification",
                "acceptance": [
                    "确认公开 URL、leaderboard 或 submission portal 当前可访问。",
                    "记录是否需要 HF_TOKEN、Space、模型仓库或人工审核。",
                    "不上传、不提交、不声明官方成绩。",
                ],
            },
            {
                "phase": "P1",
                "goal": "local baseline",
                "acceptance": [
                    "读取公开数据或样例规则。",
                    "生成 baseline manifest、原始输出和 metric parser。",
                    "保存 artifact hashes 和限制说明。",
                ],
            },
            {
                "phase": "P2",
                "goal": "client-guided iteration",
                "acceptance": [
                    "Codex/Claude 基于失败样例提出一轮 proposal。",
                    "MCP/CLI 执行受控改动并比较指标。",
                    "失败 proposal 和 rollback 也进入 artifact。",
                ],
            },
            {
                "phase": "P3",
                "goal": "external submission gate",
                "acceptance": [
                    "生成提交文件、Space API 或 model-card eval result dry-run。",
                    "人工确认后才允许外部上传。",
                    "提交成功后把公开 URL、时间、hash 和截图/响应纳入 proof archive。",
                ],
            },
        ],
        "blocked_public_claims": [
            "official HF leaderboard score before public submission evidence exists",
            "arbitrary model improvement from a single local run",
            "competition result without reproducible proof archive",
        ],
    }


def write_hf_external_eval_plan(
    output_dir: Path,
    *,
    shortlist_path: Path | None = None,
    target_id: str | None = None,
) -> dict[str, Any]:
    """Write a JSON and Markdown plan for a selected HF external evaluation target."""
    payload = build_hf_external_eval_plan(
        shortlist_path=shortlist_path,
        target_id=target_id,
    )
    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "hf-external-eval-plan.json"
    markdown_path = output / "hf-external-eval-plan.md"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_hf_external_eval_plan_markdown(payload), encoding="utf-8")
    return {
        "status": "written",
        "official_scores_claimed": False,
        "target_id": payload["target"]["target_id"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def render_hf_external_eval_plan_markdown(payload: dict[str, Any]) -> str:
    """Render a selected HF external eval plan as Markdown."""
    target = payload["target"]
    lines = [
        "# Hugging Face External Evaluation Proof Plan",
        "",
        f"schema_version: `{payload['schema_version']}`",
        "official_scores_claimed: `false`",
        f"target_id: `{target['target_id']}`",
        f"name: {target['name']}",
        f"hf_kind: `{target['hf_kind']}`",
        f"task_family: `{target['task_family']}`",
        f"primary_metric: `{target['primary_metric']}`",
        "",
        "## Claim Boundary",
        "",
        target["claim_boundary"],
        "",
        "## URLs",
        "",
    ]
    for name, url in target["urls"].items():
        lines.append(f"- {name}: {url}")
    lines.extend(
        [
            "",
            "## Why This Target",
            "",
        ]
    )
    _append_list(lines, target["why_match"])
    lines.extend(["", "## Risks", ""])
    _append_list(lines, target["risks"])
    lines.extend(["", "## Acceptance", ""])
    _append_list(lines, target["acceptance"])
    lines.extend(["", "## Phases", ""])
    for phase in payload["phases"]:
        lines.extend(["", f"### {phase['phase']}: {phase['goal']}", ""])
        _append_list(lines, phase["acceptance"])
    lines.extend(["", "## Blocked Public Claims", ""])
    _append_list(lines, payload["blocked_public_claims"])
    return "\n".join(lines).rstrip() + "\n"


def _validate_target(target: Any, index: int) -> None:
    if not isinstance(target, dict):
        raise ValueError(f"targets[{index}] must be an object")
    missing = sorted(REQUIRED_TARGET_FIELDS - set(target))
    if missing:
        raise ValueError(f"targets[{index}] missing fields: {', '.join(missing)}")
    for field in (
        "target_id",
        "name",
        "hf_kind",
        "task_family",
        "primary_metric",
        "submission_mode",
        "resource_fit",
        "recommended_phase",
        "claim_boundary",
    ):
        if not isinstance(target.get(field), str) or not target[field]:
            raise ValueError(f"targets[{index}].{field} must be a non-empty string")
    score = target.get("product_fit_score")
    if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5:
        raise ValueError(f"targets[{index}].product_fit_score must be an integer 1..5")
    urls = target.get("urls")
    if not isinstance(urls, dict) or not urls:
        raise ValueError(f"targets[{index}].urls must be a non-empty object")
    for name, url in urls.items():
        if not isinstance(name, str) or not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError(f"targets[{index}].urls must contain https URLs")
    for field in ("why_match", "risks", "acceptance"):
        values = target.get(field)
        if not isinstance(values, list) or not values or not all(
            isinstance(value, str) and value for value in values
        ):
            raise ValueError(f"targets[{index}].{field} must be a non-empty string list")


def _select_target(payload: dict[str, Any], target_id: str | None) -> dict[str, Any]:
    targets = payload["targets"]
    if target_id:
        for target in targets:
            if target["target_id"] == target_id:
                return target
        raise ValueError(f"unknown HF eval target_id: {target_id}")
    preferred = payload.get("selection_policy", {}).get("preferred_first_pilot")
    for target in targets:
        if target["target_id"] == preferred:
            return target
    return select_hf_eval_targets(payload, limit=1)[0]


def _default_next_step(target: dict[str, Any]) -> str:
    return (
        f"Run live verification for {target['target_id']}, then build a local baseline "
        "without submitting to Hugging Face."
    )


def _append_list(lines: list[str], values: list[str]) -> None:
    if not values:
        lines.append("- none")
        return
    for value in values:
        lines.append(f"- {value}")
