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
    assert "compatibility_check.status == compatible" in doc
    assert "execution_metadata" in doc
    assert "wall time" in doc
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
    assert "apply_client_code_patch" in doc
    assert "change_proposal" in doc
    assert "test_command" in doc
    assert "task_patch_only" in doc
    assert "include_final_review" in doc
    assert "loop_decision" in doc
    assert "mcp_reproduction_demo.py" in doc
    assert "invalid_required_files" in doc
    assert "ml-loop check" in doc
    assert "ml-loop init-skills" in doc
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
    assert "apply_client_code_patch" in doc
    assert "mcp_provider_quality_benchmark.py" in doc
    assert "mcp_real_task_code_benchmark.py" in doc
    assert "mcp_reproduction_demo.py" in doc


def test_chinese_product_overview_documents_product_shape() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    setup_doc = (PROJECT_ROOT / "docs" / "mcp-client-setup.md").read_text(encoding="utf-8")
    doc = (PROJECT_ROOT / "docs" / "product-overview-cn.md").read_text(encoding="utf-8")

    assert "docs/product-overview-cn.md" in readme
    assert "docs/product-overview-cn.md" in setup_doc
    assert "ML Research Loop 中文产品说明" in doc
    assert "Codex、Claude" in doc
    assert "ml-intern" in doc
    assert "autoresearch" in doc
    assert "experiment tree" in doc
    assert "reproduction" in doc
    assert "execution_metadata" in doc
    assert "compatibility_check" in doc
    assert "preview MCP product" in doc


def test_autonomous_research_product_docs_are_present() -> None:
    product_doc = PROJECT_ROOT / "docs/product/autonomous-research-product-cn.md"
    proof_matrix = PROJECT_ROOT / "docs/evidence/autonomous-product-proof-matrix-cn.md"

    for path in [product_doc, proof_matrix]:
        text = path.read_text(encoding="utf-8")
        assert "成熟稳定自动科研产品" in text
        assert "不能宣称" in text
        assert "本地 proof" in text
        assert "官方 benchmark" in text

    roadmap = (PROJECT_ROOT / "docs" / "development-roadmap-cn.md").read_text(
        encoding="utf-8"
    )
    overview = (PROJECT_ROOT / "docs" / "product-overview-cn.md").read_text(
        encoding="utf-8"
    )

    for text in [roadmap, overview]:
        assert "docs/product/autonomous-research-product-cn.md" in text
        assert "docs/evidence/autonomous-product-proof-matrix-cn.md" in text
        assert "目标高于 preview 推广目标" in text
        assert "本地 proof 当" in text


def test_real_paper_reproduction_pilot_docs_are_present() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    overview = (PROJECT_ROOT / "docs/product/autonomous-research-product-cn.md").read_text(
        encoding="utf-8"
    )
    proof_matrix = (
        PROJECT_ROOT / "docs/evidence/autonomous-product-proof-matrix-cn.md"
    ).read_text(encoding="utf-8")
    pilot = (
        PROJECT_ROOT / "docs/reproduction-pilot/memflow-single-paper-pilot-cn.md"
    ).read_text(encoding="utf-8")
    template = (
        PROJECT_ROOT / "docs/reproduction-pilot/reproduction-case-template-cn.md"
    ).read_text(encoding="utf-8")
    pilot_index = json.loads(
        (PROJECT_ROOT / "docs/evidence/real-paper-pilot-index.json").read_text(
            encoding="utf-8"
        )
    )
    claims_map = json.loads(
        (PROJECT_ROOT / "docs/evidence/public-claims-map.json").read_text(
            encoding="utf-8"
        )
    )
    proof_manifest = json.loads(
        (
            PROJECT_ROOT / "proof_runs/real-paper-pilot/memflow/proof-manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert "docs/reproduction-pilot/memflow-single-paper-pilot-cn.md" in readme
    assert "docs/reproduction-pilot/reproduction-case-template-cn.md" in readme
    assert "docs/evidence/real-paper-pilot-index.json" in readme
    assert "单篇真实论文复现试点" in overview
    assert "真实论文试点" in proof_matrix
    assert "proof_runs/real-paper-pilot/memflow/proof-manifest.json" in proof_matrix
    for text in [pilot, template]:
        assert "official_scores_claimed=false" in text
        assert "bounded claim" in text
        assert "proof" in text
    for flag in [
        "--select-only",
        "--probe-only",
        "--run-baseline",
        "--run-iteration",
        "--archive-proof",
    ]:
        assert flag in template
    assert pilot_index["official_scores_claimed"] is False
    assert pilot_index["entries"][0]["claim_strength"] == "local_public_data"
    assert claims_map["official_scores_claimed"] is False
    assert claims_map["public_claims"][0]["proof_matrix_entry"] == "Real paper pilot"
    assert proof_manifest["official_scores_claimed"] is False
    assert proof_manifest["artifact_sha256"]["dataset_provenance"]
    assert proof_manifest["artifact_sha256"]["human_review_report"]
    assert proof_manifest["review_status"] == "approved_with_limitations"
    assert proof_manifest["artifact_sha256"]["iteration_comparison"]


def test_institution_pilot_docs_are_present() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "docs" / "institution-pilot-guide-cn.md").read_text(
        encoding="utf-8"
    )
    template = (
        PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE" / "pilot_feedback.yml"
    ).read_text(encoding="utf-8")
    examples = [
        PROJECT_ROOT / "examples" / "pilot" / "student-byte-lm" / "README.md",
        PROJECT_ROOT / "examples" / "pilot" / "reproduction-mini" / "README.md",
        PROJECT_ROOT / "examples" / "pilot" / "lab-benchmark" / "README.md",
    ]

    assert "docs/institution-pilot-guide-cn.md" in readme
    assert "pilot_feedback.yml" in readme
    for phrase in [
        "30 分钟本科实验",
        "2 小时硕博论文复现 Mini Lab",
        "1 天实验室 Benchmark Trial",
        "数据安全注意事项",
        "失败反馈模板",
        "预期输入/输出 Artifact",
    ]:
        assert phrase in guide
    for field in [
        "用户角色",
        "客户端",
        "OS",
        "Python version",
        "demo command",
        "failure log",
        "redacted feedback bundle path",
        "是否愿意访谈",
    ]:
        assert field in template
    for path in examples:
        text = path.read_text(encoding="utf-8")
        assert "适合对象" in text
        assert "运行命令" in text
        assert "预期输出" in text
        assert "常见失败" in text
        assert "应提交的反馈文件" in text


def test_chinese_project_overview_documents_current_architecture() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    doc = (PROJECT_ROOT / "docs" / "project-overview-cn.md").read_text(encoding="utf-8")

    assert "docs/project-overview-cn.md" in readme
    assert "项目整体说明" in doc
    assert "ml-intern" in doc
    assert "autoresearch" in doc
    assert "MCP + Skills" in doc
    assert "Codex/Claude" in doc
    assert "AIDE" in doc
    assert "PaperBench" in doc
    assert "scripts/release_check.py --json" in doc
    assert "docs/development-roadmap-cn.md" in doc


def test_chinese_development_roadmap_documents_next_work() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    todos = (PROJECT_ROOT / "docs" / "productization-todos.md").read_text(encoding="utf-8")
    roadmap = (PROJECT_ROOT / "docs" / "development-roadmap-cn.md").read_text(
        encoding="utf-8"
    )

    assert "docs/development-roadmap-cn.md" in readme
    assert "P7: MCP + Skills 产品层" in roadmap
    assert "ml-research-loop-planner" in roadmap
    assert "ml-research-loop-reproduction" in roadmap
    assert "ml-research-loop-experiment-optimizer" in roadmap
    assert "P8: 真实研究检索质量" in roadmap
    assert "P9: 自动实验智能" in roadmap
    assert "P10: 发布和分发" in roadmap
    assert "P7: MCP + Skills Product Layer" in todos


def test_release_distribution_docs_cover_beta_stable_and_onboarding() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    setup_doc = (PROJECT_ROOT / "docs" / "mcp-client-setup.md").read_text(encoding="utf-8")
    release_notes = (PROJECT_ROOT / "docs" / "release-notes.md").read_text(encoding="utf-8")
    compatibility = (PROJECT_ROOT / "docs" / "client-compatibility-matrix.md").read_text(
        encoding="utf-8"
    )
    mcp_examples = (PROJECT_ROOT / "examples" / "mcp" / "README.md").read_text(
        encoding="utf-8"
    )

    assert "docs/release-notes.md" in readme
    assert "docs/client-compatibility-matrix.md" in readme
    assert "examples/mcp/README.md" in readme
    assert "ml-loop init-mcp-config" in setup_doc
    assert "ml-loop init-skills" in setup_doc
    assert "pip install -e \".[dev]\"" in setup_doc
    assert "2026-04-30.preview.v1" in release_notes
    assert "migration_required" in release_notes
    assert "beta release gate" in release_notes
    assert "stable release gate" in release_notes
    assert "Codex" in compatibility
    assert "Claude Code" in compatibility
    assert "Claude Desktop" in compatibility
    assert "contract_version" in compatibility
    assert "ml-loop init-mcp-config --client codex" in mcp_examples
    assert "ml-loop init-skills --client codex" in mcp_examples
    assert "scripts/mcp_client_acceptance.py" in mcp_examples
    assert "scripts/mcp_golden_path.py" in mcp_examples
