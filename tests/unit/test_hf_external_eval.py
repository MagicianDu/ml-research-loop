from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib import mcp_service
from lib.benchmarks.hf_external_eval import (
    build_hf_external_eval_plan,
    load_hf_eval_targets,
    select_hf_eval_targets,
    write_hf_external_eval_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_load_hf_eval_targets_preserves_claim_boundary() -> None:
    payload = load_hf_eval_targets()

    assert payload["official_scores_claimed"] is False
    assert len(payload["targets"]) >= 5
    assert payload["selection_policy"]["preferred_first_pilot"] == (
        "smol-ai-worldcup-shift"
    )
    for target in payload["targets"]:
        assert target["claim_boundary"]
        assert target["product_fit_score"] in {1, 2, 3, 4, 5}
        assert all(url.startswith("https://") for url in target["urls"].values())
        assert "leaderboard" in json.dumps(target, ensure_ascii=False).lower() or (
            target["hf_kind"] in {"competition_platform", "eval_results"}
        )


def test_select_hf_eval_targets_prefers_high_product_fit() -> None:
    payload = load_hf_eval_targets()

    targets = select_hf_eval_targets(payload, limit=2)

    assert [target["target_id"] for target in targets] == [
        "smol-ai-worldcup-shift",
        "frugal-ai-challenge-text",
    ]


def test_build_hf_external_eval_plan_uses_preferred_target_by_default() -> None:
    plan = build_hf_external_eval_plan()

    assert plan["status"] == "planned"
    assert plan["official_scores_claimed"] is False
    assert plan["target"]["target_id"] == "smol-ai-worldcup-shift"
    assert plan["default_next_step"].startswith("Run live verification")
    assert "official HF leaderboard score" in plan["blocked_public_claims"][0]
    assert [phase["phase"] for phase in plan["phases"]] == ["P0", "P1", "P2", "P3"]


def test_write_hf_external_eval_plan_writes_json_and_markdown(tmp_path: Path) -> None:
    result = write_hf_external_eval_plan(
        tmp_path / "hf-plan",
        target_id="turingbench-2-questions",
    )

    json_path = Path(result["json_path"])
    markdown_path = Path(result["markdown_path"])
    assert result["status"] == "written"
    assert result["official_scores_claimed"] is False
    assert result["target_id"] == "turingbench-2-questions"
    assert json_path.exists()
    assert markdown_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["target"]["target_id"] == "turingbench-2-questions"
    assert payload["official_scores_claimed"] is False
    assert "official_scores_claimed: `false`" in markdown
    assert "TuringBench" in markdown
    assert "Blocked Public Claims" in markdown


def test_load_hf_eval_targets_rejects_official_score_claims(tmp_path: Path) -> None:
    shortlist = tmp_path / "shortlist.json"
    source = json.loads(
        (PROJECT_ROOT / "docs/hf-evaluation/target-shortlist.json").read_text(
            encoding="utf-8"
        )
    )
    source["official_scores_claimed"] = True
    shortlist.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="official_scores_claimed=false"):
        load_hf_eval_targets(shortlist)


def test_hf_external_eval_mcp_tools_are_exposed_and_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(tmp_path))

    tool_names = {tool["name"] for tool in mcp_service.tool_definitions()}
    assert "get_hf_external_eval_targets" in tool_names
    assert "write_hf_external_eval_plan" in tool_names
    assert "get_hf_external_eval_targets" in mcp_service.REQUIRED_TOOLS
    assert "write_hf_external_eval_plan" in mcp_service.REQUIRED_TOOLS

    listed = mcp_service.get_hf_external_eval_targets_tool({"limit": 1})
    assert listed["status"] == "listed"
    assert listed["official_scores_claimed"] is False
    assert listed["targets"][0]["target_id"] == "smol-ai-worldcup-shift"

    written = mcp_service.write_hf_external_eval_plan_tool({
        "target_id": "smol-ai-worldcup-shift",
        "output_dir": str(tmp_path / "hf-plan"),
    })
    assert written["status"] == "written"
    assert written["official_scores_claimed"] is False
    assert Path(written["json_path"]).exists()
    assert Path(written["markdown_path"]).exists()


def test_service_manifest_mentions_hf_external_validation() -> None:
    manifest = mcp_service.get_service_manifest_tool({})

    assert "hf_external_eval_targets" in manifest["planning_signals"]
    assert manifest["hf_external_eval_targets"]["official_scores_claimed"] is False
    assert manifest["hf_external_eval_plan"]["official_scores_claimed"] is False
    workflows = {workflow["name"]: workflow for workflow in manifest["recommended_workflows"]}
    assert "hf_external_validation" in workflows
    assert "get_hf_external_eval_targets" in workflows["hf_external_validation"]["tools"]
