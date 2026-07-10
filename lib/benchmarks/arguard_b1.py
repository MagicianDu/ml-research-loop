"""ArGuard B1 Codabench leaderboard proof helpers."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ARGUARD_B1_TARGET_ID = "arguard-b1-binary-classification"
ARGUARD_B1_URLS = {
    "competition": "https://www.codabench.org/competitions/16652/",
    "task_website": "https://araieval.github.io/ArGuard2026/taskB/",
    "repository": "https://github.com/araieval/ArGuard-2026-tasks",
    "repository_readme_raw": (
        "https://raw.githubusercontent.com/araieval/ArGuard-2026-tasks/main/README.md"
    ),
    "task_readme_raw": (
        "https://raw.githubusercontent.com/araieval/ArGuard-2026-tasks/main/taskB/README.md"
    ),
}
CRITICAL_CHECK_IDS = [
    "codabench_competition",
    "repository_readme",
    "task_readme",
]

Fetcher = Callable[[str, int], dict[str, Any]]


def build_arguard_b1_target_contract() -> dict[str, Any]:
    """Return the conservative ArGuard B1 target contract."""
    return {
        "target_id": ARGUARD_B1_TARGET_ID,
        "name": "ArGuard Subtask B1 Binary Classification",
        "platform": "Codabench",
        "task_family": "arabic_prompt_safety_classification",
        "urls": dict(ARGUARD_B1_URLS),
        "metrics": ["macro-F1"],
        "submission_format": {
            "format": "tsv",
            "required_header": ["id", "label", "run_id"],
            "labels": ["safe", "unsafe"],
        },
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
        "claim_boundary": (
            "ArGuard B1 target contract only; no Codabench submission, "
            "leaderboard score, ranking, or official external result is claimed."
        ),
    }


def write_arguard_b1_live_verification(
    output_dir: Path,
    *,
    timeout_seconds: int = 30,
    include_raw: bool = False,
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    """Write ArGuard B1 P0 live verification artifacts without submitting."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    raw_dir = output / "raw"
    if include_raw:
        raw_dir.mkdir(parents=True, exist_ok=True)

    target = build_arguard_b1_target_contract()
    fetch = fetcher or fetch_arguard_b1_url
    check_urls = {
        "codabench_competition": target["urls"]["competition"],
        "repository_readme": target["urls"]["repository_readme_raw"],
        "task_readme": target["urls"]["task_readme_raw"],
    }
    checks = []
    raw_texts: dict[str, str] = {}
    for check_id in CRITICAL_CHECK_IDS:
        check = dict(fetch(check_urls[check_id], timeout_seconds))
        check["check_id"] = check_id
        check["critical"] = True
        raw_texts[check_id] = str(check.get("raw_text") or check.get("text_excerpt") or "")
        if include_raw:
            raw_path = raw_dir / f"{len(checks) + 1:02d}-{_slug(check_id)}.txt"
            raw_path.write_text(
                raw_texts[check_id],
                encoding="utf-8",
            )
            check["raw_path"] = str(raw_path)
        checks.append(_public_check(check))

    task_text = raw_texts.get("task_readme", "")
    repo_text = raw_texts.get("repository_readme", "")
    hard_blockers = []
    asset_status = _arguard_b1_asset_status(task_text)
    if asset_status["data_and_scorer"] != "confirmed_released":
        hard_blockers.append("released_train_dev_scorer_not_confirmed")

    unreachable = [
        check["check_id"]
        for check in checks
        if check["critical"] and check.get("status") != "reachable"
    ]
    hard_blockers.extend(f"{check_id}_unreachable" for check_id in unreachable)
    verification_status = (
        "blocked_unreachable_sources"
        if unreachable
        else (
            "verified_with_asset_blockers"
            if hard_blockers
            else "verified_with_limitations"
        )
    )
    payload = {
        "schema_version": "2026-06-29.arguard-b1-live-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "written",
        "verification_status": verification_status,
        "target": target,
        "checks": checks,
        "asset_status": asset_status,
        "schedule": _arguard_b1_schedule(repo_text),
        "extracted_contract": {
            "subtask": "B1",
            "input": "Arabic prompt text",
            "labels": ["safe", "unsafe"],
            "primary_metric_detected": "macro-F1" if "macro-f1" in task_text.lower() else "",
            "submission_header_detected": (
                "id<TAB>label<TAB>run_id"
                if "id<tab>label<tab>run_id" in task_text.lower()
                else ""
            ),
        },
        "hard_blockers": sorted(set(hard_blockers)),
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
        "claim_boundary": target["claim_boundary"],
    }

    json_path = output / "arguard-b1-live-verification.json"
    contract_path = output / "arguard-b1-target-contract.md"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    contract_path.write_text(render_arguard_b1_target_contract(payload), encoding="utf-8")
    return {
        "status": "written",
        "verification_status": verification_status,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "json_path": str(json_path),
        "contract_path": str(contract_path),
    }


def fetch_arguard_b1_url(url: str, timeout_seconds: int) -> dict[str, Any]:
    """Fetch one public ArGuard B1 URL and return a bounded check record."""
    request = urllib.request.Request(url, headers={"User-Agent": "ml-research-loop/arguard-b1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(200_000)
            text = raw.decode("utf-8", errors="replace")
            return {
                "status": "reachable",
                "url": url,
                "status_code": response.status,
                "content_length": len(raw),
                "text_excerpt": text[:2000],
                "raw_text": text,
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": "unreachable",
            "url": url,
            "status_code": exc.code,
            "error": str(exc),
            "text_excerpt": "",
        }
    except OSError as exc:
        return {
            "status": "unreachable",
            "url": url,
            "status_code": None,
            "error": str(exc),
            "text_excerpt": "",
        }


def render_arguard_b1_target_contract(payload: dict[str, Any]) -> str:
    """Render an ArGuard B1 live verification record as Markdown."""
    target = payload["target"]
    lines = [
        "# ArGuard B1 Live Verification",
        "",
        f"schema_version: `{payload['schema_version']}`",
        "official_scores_claimed: `false`",
        f"target_id: `{target['target_id']}`",
        f"verification_status: `{payload['verification_status']}`",
        "",
        "## Claim Boundary",
        "",
        payload["claim_boundary"],
        "",
        "## Target Contract",
        "",
        f"- platform: `{target['platform']}`",
        f"- primary_metric: `{', '.join(target['metrics'])}`",
        f"- submission_format: `{target['submission_format']['format']}`",
        f"- required_header: `{', '.join(target['submission_format']['required_header'])}`",
        f"- labels: `{', '.join(target['submission_format']['labels'])}`",
        "",
        "## Asset Status",
        "",
        f"- data_and_scorer: `{payload['asset_status']['data_and_scorer']}`",
        "",
        "## Hard Blockers",
        "",
    ]
    blockers = payload.get("hard_blockers") or []
    if blockers:
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Checks", ""])
    for check in payload["checks"]:
        lines.append(f"- {check['check_id']}: `{check['status']}` {check['url']}")
    return "\n".join(lines).rstrip() + "\n"


def _arguard_b1_asset_status(task_text: str) -> dict[str, Any]:
    lowered = task_text.lower()
    blocked_markers = [
        "tbd",
        "will be released",
        "once released",
        "planned starter",
    ]
    data_and_scorer = (
        "not_confirmed_released_in_public_readme"
        if any(marker in lowered for marker in blocked_markers)
        else "confirmed_released"
    )
    return {
        "data_and_scorer": data_and_scorer,
        "macro_f1_detected": "macro-f1" in lowered,
        "b1_output_header_detected": "id<tab>label<tab>run_id" in lowered,
    }


def _arguard_b1_schedule(repo_text: str) -> dict[str, str]:
    schedule = {}
    for key, pattern in {
        "development_assets": r"evaluation scripts:\s*([A-Za-z]+\s+\d+,\s+\d{4})",
        "blind_test_release": r"blind test set release:\s*([A-Za-z]+\s+\d+,\s+\d{4})",
        "final_submission_deadline": r"Final submission deadline.*?:\s*([A-Za-z]+\s+\d+,\s+\d{4})",
    }.items():
        match = re.search(pattern, repo_text, flags=re.IGNORECASE)
        if match:
            schedule[key] = match.group(1)
    return schedule


def _public_check(check: dict[str, Any]) -> dict[str, Any]:
    return {
        "check_id": check["check_id"],
        "critical": bool(check.get("critical", False)),
        "url": str(check.get("url", "")),
        "status": str(check.get("status", "")),
        "status_code": check.get("status_code"),
        "content_length": check.get("content_length"),
        "text_excerpt": str(check.get("text_excerpt", ""))[:2000],
        **({"raw_path": check["raw_path"]} if check.get("raw_path") else {}),
    }


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower() or "artifact"
