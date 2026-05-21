from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = PROJECT_ROOT / "skills"

SKILL_NAMES = [
    "ml-research-loop-planner",
    "ml-research-loop-reproduction",
    "ml-research-loop-experiment-optimizer",
    "ml-research-loop-operator",
]


def read_skill(name: str) -> str:
    return (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")


def frontmatter_value(text: str, key: str) -> str:
    for line in text.splitlines():
        prefix = f"{key}: "
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    raise AssertionError(f"missing frontmatter key: {key}")


def test_skill_packages_have_minimal_valid_structure() -> None:
    for name in SKILL_NAMES:
        skill_dir = SKILLS_ROOT / name
        skill_md = skill_dir / "SKILL.md"

        assert skill_md.exists(), name
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert frontmatter_value(text, "name") == name
        assert frontmatter_value(text, "description").startswith("Use when")
        assert len(frontmatter_value(text, "description")) < 500
        assert not (skill_dir / "README.md").exists()


def test_planner_skill_covers_manifest_first_and_main_workflows() -> None:
    text = read_skill("ml-research-loop-planner")

    for required in [
        "get_service_manifest",
        "research_task",
        "read_paper",
        "propose_hypotheses",
        "run_hypothesis_experiment",
        "review_research_results",
        "research_evidence_gate",
        "run_fasttext_binary_baseline",
        "run_fasttext_patch_round",
        "write_fasttext_patch_round_proof_bundle",
        "run_fasttext_multi_proposal_loop",
        "write_fasttext_release_proof_bundle",
        "build_proposal_context",
        "validate_client_proposal_contract",
        "write_proposal_reflection",
        "improvement_report",
        "release-proof-bundle.tar.gz",
        "human confirmation",
        "run_ai_autoresearch",
        "get_benchmark_harness_probe",
        "write_benchmark_proof_archive",
        "get_hf_external_eval_targets",
        "write_hf_external_eval_plan",
        "write_smol_worldcup_live_verification",
        "write_smol_worldcup_prompt_leakage_audit",
        "run_smol_worldcup_local_baseline",
        "run_smol_worldcup_model_eval",
        "prepare_official_mle_bench_workspace",
        "grade_official_mle_bench_submission",
        "run_official_mle_bench_round",
        "run_official_mle_bench_patch_round",
        "write_official_mle_bench_patch_round_proof_bundle",
        "prepare_paperbench_codex_review_bundle",
        "write_paperbench_codex_review_report",
        "Research Memory Layer",
        "artifact provenance",
        "Memory suggestions never execute directly",
    ]:
        assert required in text


def test_reproduction_skill_covers_paperbench_style_flow() -> None:
    text = read_skill("ml-research-loop-reproduction")

    for required in [
        "read_paper",
        "research_task",
        "reproduction_spec",
        "required_files",
        "rubric",
        "grade_report",
        "mcp_reproduction_demo.py",
        "invalid_required_files",
        "prepare_paperbench_codex_review_bundle",
        "write_paperbench_codex_review_report",
        "run_fasttext_binary_baseline",
        "run_fasttext_patch_round",
        "write_fasttext_patch_round_proof_bundle",
        "run_fasttext_multi_proposal_loop",
        "write_fasttext_release_proof_bundle",
        "improvement-report.json",
        "proof-manifest.json",
        "client-handoff.json",
        "multi-round-report.json",
        "rollback_summary",
        "Research Memory Layer",
        "memory card",
    ]:
        assert required in text


def test_experiment_optimizer_skill_covers_patch_loop_safety() -> None:
    text = read_skill("ml-research-loop-experiment-optimizer")

    for required in [
        "review_research_results",
        "experiment_tree",
        "metric_stop_policy",
        "failure_diagnostics",
        "run_next_experiment_from_review",
        "run_client_patch_experiment",
        "apply_client_code_patch",
        "run_fasttext_patch_round",
        "write_fasttext_patch_round_proof_bundle",
        "run_fasttext_multi_proposal_loop",
        "write_fasttext_release_proof_bundle",
        "build_proposal_context",
        "validate_client_proposal_contract",
        "write_proposal_reflection",
        "patch-proposal.json",
        "proof-manifest.json",
        "release-proof-bundle.sha256",
        "client-handoff.json",
        "rollback",
        "loop_decision",
        "stale",
        "syntax/test failure",
        "metric regression",
        "Research Memory Layer",
        "memory suggestions",
    ]:
        assert required in text


def test_operator_skill_covers_install_acceptance_and_artifacts() -> None:
    text = read_skill("ml-research-loop-operator")

    for required in [
        "Codex",
        "Claude",
        "get_service_manifest",
        "mcp_client_acceptance.py",
        "scripts/release_check.py --json",
        "list_runtime_artifacts",
        "archive_runtime_artifacts",
        "clean_runtime_artifacts",
        "ML_RESEARCH_LOOP_ALLOWED_ROOTS",
        "get_benchmark_harness_probe",
        "plan_benchmark_proof_run",
        "write_benchmark_proof_setup_bundle",
        "write_benchmark_proof_publication_bundle",
        "write_benchmark_proof_archive",
        "get_hf_external_eval_targets",
        "write_hf_external_eval_plan",
        "write_smol_worldcup_live_verification",
        "write_smol_worldcup_prompt_leakage_audit",
        "run_smol_worldcup_local_baseline",
        "run_smol_worldcup_model_eval",
        "prepare_official_mle_bench_workspace",
        "grade_official_mle_bench_submission",
        "run_official_mle_bench_round",
        "run_official_mle_bench_patch_round",
        "write_official_mle_bench_patch_round_proof_bundle",
        "prepare_paperbench_codex_review_bundle",
        "write_paperbench_codex_review_report",
        "run_fasttext_binary_baseline",
        "run_fasttext_patch_round",
        "write_fasttext_patch_round_proof_bundle",
        "run_fasttext_multi_proposal_loop",
        "write_fasttext_release_proof_bundle",
        "improvement-report.json",
        "human-review-report.json",
        "client-handoff.json",
        "release-review-checklist.md",
    ]:
        assert required in text


def test_skill_installation_docs_are_linked() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    setup_doc = (PROJECT_ROOT / "docs" / "mcp-client-setup.md").read_text(
        encoding="utf-8"
    )
    project_doc = (PROJECT_ROOT / "docs" / "project-overview-cn.md").read_text(
        encoding="utf-8"
    )
    skill_doc = (PROJECT_ROOT / "docs" / "skills-setup-cn.md").read_text(
        encoding="utf-8"
    )
    todos = (PROJECT_ROOT / "docs" / "productization-todos.md").read_text(
        encoding="utf-8"
    )

    assert "docs/skills-setup-cn.md" in readme
    assert "docs/skills-setup-cn.md" in setup_doc
    assert "docs/skills-setup-cn.md" in project_doc
    assert "skills/ml-research-loop-planner/SKILL.md" in skill_doc
    assert "ml-loop init-skills --client codex" in skill_doc
    assert "ml-loop init-skills --client claude" in skill_doc
    assert "skill_contracts" in skill_doc
    assert "recommended_skills" in skill_doc
    assert "~/.codex/skills" in skill_doc
    assert "~/.claude/skills" in skill_doc
    assert "P7: MCP + Skills Product Layer" in todos
    assert "- [x] Add Codex/Claude skills for the main research loop." in todos
    assert "- [x] Add focused reproduction and experiment optimization skills." in todos
    assert "- [x] Add operator skill and installation docs." in todos
