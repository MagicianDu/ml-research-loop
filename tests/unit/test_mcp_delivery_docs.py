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
    assert "Codex" in doc
    assert "Claude Code" in doc
    assert "Claude Desktop" in doc
    assert "research_task -> read_paper -> propose_hypotheses" in doc
    assert "run_hypothesis_experiment -> review_research_results" in doc
