from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_mcp_client_config_templates_are_parseable() -> None:
    codex_config = PROJECT_ROOT / "examples" / "mcp" / "codex-config.toml"
    claude_code_config = PROJECT_ROOT / "examples" / "mcp" / "claude-code.mcp.json"
    claude_desktop_config = PROJECT_ROOT / "examples" / "mcp" / "claude-desktop-config.json"

    assert "mcp_servers.mlResearchLoop" in codex_config.read_text(encoding="utf-8")

    claude_code = json.loads(claude_code_config.read_text(encoding="utf-8"))
    claude_desktop = json.loads(claude_desktop_config.read_text(encoding="utf-8"))

    assert claude_code["mcpServers"]["ml-research-loop"]["type"] == "stdio"
    assert claude_desktop["mcpServers"]["ml-research-loop"]["type"] == "stdio"
    assert claude_code["mcpServers"]["ml-research-loop"]["command"] == "/ABS/PATH/TO/python3"


def test_mcp_setup_doc_contains_golden_path_and_client_sections() -> None:
    doc = (PROJECT_ROOT / "docs" / "mcp-client-setup.md").read_text(encoding="utf-8")

    assert "scripts/mcp_golden_path.py" in doc
    assert "scripts/mcp_auto_next_demo.py" in doc
    assert "Codex" in doc
    assert "Claude Code" in doc
    assert "Claude Desktop" in doc
    assert "contract_version" in doc
    assert "2026-04-30.preview.v1" in doc
    assert "tool_contracts" in doc
    assert "ML_RESEARCH_LOOP_ALLOWED_ROOTS" in doc
    assert "execution_sandbox.status == enforced" in doc
    assert "wait_for_rate_limit_reset" in doc
    assert "rate_limited" in doc
    assert "run_next_experiment_from_review" in doc
    assert "provider_coverage" in doc
    assert "provider_coverage_gate" in doc
    assert "evidence_citations" in doc
    assert "diff_preview" in doc
    assert "execution_guardrails" in doc
    assert "run_client_patch_experiment" in doc
    assert "change_proposal" in doc
    assert "task_patch_only" in doc
    assert "include_final_review" in doc
    assert "loop_decision" in doc
    assert "ml-loop check" in doc
    assert "artifacts list" in doc
    assert "research_task -> read_paper -> propose_hypotheses" in doc
    assert "run_hypothesis_experiment -> review_research_results" in doc


def test_product_examples_cover_expected_flows() -> None:
    doc = (PROJECT_ROOT / "examples" / "README.md").read_text(encoding="utf-8")

    assert "synthetic" in doc
    assert "local real-data" in doc
    assert "paper-guided" in doc
    assert "failed-run debugging" in doc
    assert "mcp_real_data_demo.py" in doc
    assert "run_next_experiment_from_review" in doc
    assert "run_client_patch_experiment" in doc
