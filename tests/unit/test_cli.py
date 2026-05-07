import json
from pathlib import Path

from scripts.cli import build_parser, main


SKILL_NAMES = [
    "ml-research-loop-planner",
    "ml-research-loop-reproduction",
    "ml-research-loop-experiment-optimizer",
    "ml-research-loop-operator",
]


def test_parser_has_run_status_result_subcommands():
    parser = build_parser()

    run_args = parser.parse_args(["run", "--task-config", "tasks/demo.json"])
    status_args = parser.parse_args(["status", "demo"])
    result_args = parser.parse_args(["result", "demo"])
    check_args = parser.parse_args(["check", "--json"])
    artifacts_args = parser.parse_args(["artifacts", "list", "--runtime-root", "/tmp/runtime"])
    init_args = parser.parse_args(["init-mcp-config", "--client", "codex"])
    skills_args = parser.parse_args(["init-skills", "--client", "codex"])
    feedback_args = parser.parse_args([
        "feedback-bundle",
        "--runtime-root",
        "/tmp/runtime",
        "--task-id",
        "demo",
    ])
    benchmark_readiness_args = parser.parse_args(["benchmark", "readiness", "--json"])
    benchmark_smoke_args = parser.parse_args([
        "benchmark",
        "smoke",
        "--runtime-root",
        "/tmp/runtime",
        "--json",
    ])
    benchmark_probe_args = parser.parse_args(["benchmark", "probe", "--json"])
    benchmark_proof_plan_args = parser.parse_args(["benchmark", "proof-plan", "--json"])
    benchmark_setup_bundle_args = parser.parse_args([
        "benchmark",
        "setup-bundle",
        "--output-dir",
        "/tmp/proof-setup",
        "--json",
    ])
    benchmark_publication_args = parser.parse_args([
        "benchmark",
        "publication-bundle",
        "--manifest",
        "/tmp/proof/manifest.json",
        "--artifact-root",
        "/tmp/proof/artifacts",
        "--output-dir",
        "/tmp/proof/publication",
        "--json",
    ])
    benchmark_archive_args = parser.parse_args([
        "benchmark",
        "archive-proof",
        "--manifest",
        "/tmp/proof/manifest.json",
        "--artifact-root",
        "/tmp/proof/artifacts",
        "--output-dir",
        "/tmp/proof/archive",
        "--json",
    ])
    benchmark_mle_workspace_args = parser.parse_args([
        "benchmark",
        "mle-workspace",
        "--competition-id",
        "spooky-author-identification",
        "--prepared-competition-dir",
        "/tmp/mlebench-data/spooky-author-identification",
        "--runtime-root",
        "/tmp/runtime",
        "--json",
    ])
    benchmark_mle_grade_args = parser.parse_args([
        "benchmark",
        "mle-grade",
        "--competition-id",
        "spooky-author-identification",
        "--submission",
        "/tmp/workspace/submission.csv",
        "--data-dir",
        "/tmp/mlebench-data",
        "--mlebench",
        "/tmp/venv/bin/mlebench",
        "--output-dir",
        "/tmp/reports",
        "--json",
    ])
    benchmark_mle_round_args = parser.parse_args([
        "benchmark",
        "mle-round",
        "--competition-id",
        "spooky-author-identification",
        "--workspace",
        "/tmp/workspace",
        "--data-dir",
        "/tmp/mlebench-data",
        "--mlebench",
        "/tmp/venv/bin/mlebench",
        "--output-dir",
        "/tmp/reports",
        "--python",
        "python3",
        "--round-id",
        "round-001",
        "--json",
    ])
    benchmark_mle_patch_round_args = parser.parse_args([
        "benchmark",
        "mle-patch-round",
        "--competition-id",
        "spooky-author-identification",
        "--workspace",
        "/tmp/workspace",
        "--data-dir",
        "/tmp/mlebench-data",
        "--mlebench",
        "/tmp/venv/bin/mlebench",
        "--output-dir",
        "/tmp/reports",
        "--patch-file",
        "/tmp/patch.diff",
        "--python",
        "python3",
        "--round-id",
        "round-002",
        "--json",
    ])
    benchmark_mle_patch_proof_args = parser.parse_args([
        "benchmark",
        "mle-patch-proof",
        "--patch-round-report",
        "/tmp/reports/round-002/patch-round-report.json",
        "--output-dir",
        "/tmp/proof",
        "--json",
    ])
    benchmark_paperbench_codex_bundle_args = parser.parse_args([
        "benchmark",
        "paperbench-codex-review-bundle",
        "--run-dir",
        "/tmp/paperbench/runs/group/rice_123",
        "--paper-dir",
        "/tmp/frontier-evals/project/paperbench/data/papers/rice",
        "--output-dir",
        "/tmp/review-bundle",
        "--json",
    ])
    benchmark_paperbench_codex_report_args = parser.parse_args([
        "benchmark",
        "paperbench-codex-review-report",
        "--bundle",
        "/tmp/review-bundle/codex-review-bundle.json",
        "--review-file",
        "/tmp/codex-review.json",
        "--output-dir",
        "/tmp/review-report",
        "--json",
    ])
    demo_list_args = parser.parse_args(["demo", "list"])
    demo_init_args = parser.parse_args([
        "demo",
        "init",
        "--template",
        "byte-lm-smoke",
        "--runtime-root",
        "/tmp/runtime",
    ])

    assert run_args.command == "run"
    assert status_args.command == "status"
    assert result_args.command == "result"
    assert check_args.command == "check"
    assert artifacts_args.command == "artifacts"
    assert artifacts_args.artifact_command == "list"
    assert init_args.command == "init-mcp-config"
    assert init_args.client == "codex"
    assert skills_args.command == "init-skills"
    assert skills_args.client == "codex"
    assert feedback_args.command == "feedback-bundle"
    assert feedback_args.task_id == "demo"
    assert benchmark_readiness_args.command == "benchmark"
    assert benchmark_readiness_args.benchmark_command == "readiness"
    assert benchmark_smoke_args.benchmark_command == "smoke"
    assert str(benchmark_smoke_args.runtime_root) == "/tmp/runtime"
    assert benchmark_probe_args.benchmark_command == "probe"
    assert benchmark_proof_plan_args.benchmark_command == "proof-plan"
    assert benchmark_setup_bundle_args.benchmark_command == "setup-bundle"
    assert str(benchmark_setup_bundle_args.output_dir) == "/tmp/proof-setup"
    assert benchmark_publication_args.benchmark_command == "publication-bundle"
    assert str(benchmark_publication_args.manifest) == "/tmp/proof/manifest.json"
    assert benchmark_archive_args.benchmark_command == "archive-proof"
    assert str(benchmark_archive_args.output_dir) == "/tmp/proof/archive"
    assert benchmark_mle_workspace_args.benchmark_command == "mle-workspace"
    assert benchmark_mle_workspace_args.competition_id == "spooky-author-identification"
    assert str(benchmark_mle_workspace_args.runtime_root) == "/tmp/runtime"
    assert benchmark_mle_grade_args.benchmark_command == "mle-grade"
    assert str(benchmark_mle_grade_args.submission) == "/tmp/workspace/submission.csv"
    assert benchmark_mle_round_args.benchmark_command == "mle-round"
    assert str(benchmark_mle_round_args.workspace) == "/tmp/workspace"
    assert benchmark_mle_round_args.round_id == "round-001"
    assert benchmark_mle_patch_round_args.benchmark_command == "mle-patch-round"
    assert str(benchmark_mle_patch_round_args.patch_file) == "/tmp/patch.diff"
    assert benchmark_mle_patch_round_args.round_id == "round-002"
    assert benchmark_mle_patch_proof_args.benchmark_command == "mle-patch-proof"
    assert str(benchmark_mle_patch_proof_args.patch_round_report) == (
        "/tmp/reports/round-002/patch-round-report.json"
    )
    assert str(benchmark_mle_patch_proof_args.output_dir) == "/tmp/proof"
    assert (
        benchmark_paperbench_codex_bundle_args.benchmark_command
        == "paperbench-codex-review-bundle"
    )
    assert str(benchmark_paperbench_codex_bundle_args.run_dir).endswith("rice_123")
    assert (
        benchmark_paperbench_codex_report_args.benchmark_command
        == "paperbench-codex-review-report"
    )
    assert str(benchmark_paperbench_codex_report_args.review_file) == "/tmp/codex-review.json"
    assert demo_list_args.command == "demo"
    assert demo_list_args.demo_command == "list"
    assert demo_init_args.demo_command == "init"
    assert demo_init_args.template == "byte-lm-smoke"


def test_status_command_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.cli.AutoResearchManager.get_status",
        lambda self, task_id: {"task_id": task_id, "status": "running"},
    )

    exit_code = main(["status", "demo"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "running"


def test_check_command_invokes_release_check(monkeypatch):
    captured = {}

    def fake_call(cmd, cwd=None):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return 0

    monkeypatch.setattr("scripts.cli.subprocess.call", fake_call)

    exit_code = main(["check", "--json", "--skip-demos", "--python", "python3"])

    assert exit_code == 0
    assert captured["cmd"][-4:] == [
        "--python",
        "python3",
        "--skip-golden-path",
        "--json",
    ]
    assert "release_check.py" in captured["cmd"][1]


def test_artifacts_list_command_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.cli.mcp_service.list_runtime_artifacts_tool",
        lambda arguments: {"runtime_root": arguments["runtime_root"], "task_ids": ["demo"]},
    )

    exit_code = main(["artifacts", "list", "--runtime-root", "/tmp/runtime"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"runtime_root": "/tmp/runtime", "task_ids": ["demo"]}


def test_init_mcp_config_prints_codex_config(tmp_path, capsys):
    project_root = tmp_path / "ml-research-loop"
    site_packages = project_root / ".venv" / "lib" / "python3.11" / "site-packages"
    site_packages.mkdir(parents=True)

    exit_code = main([
        "init-mcp-config",
        "--client",
        "codex",
        "--project-root",
        str(project_root),
        "--python",
        "/opt/python/bin/python3",
    ])

    text = capsys.readouterr().out
    assert exit_code == 0
    assert "[mcp_servers.mlResearchLoop]" in text
    assert 'command = "/opt/python/bin/python3"' in text
    assert f'args = ["{project_root / "scripts" / "mcp_server.py"}"]' in text
    assert f'cwd = "{project_root}"' in text
    assert f"PYTHONPATH = \"{project_root}:{site_packages}\"" in text
    assert 'ML_RESEARCH_LOOP_PYTHON = "/opt/python/bin/python3"' in text


def test_init_mcp_config_writes_claude_code_json(tmp_path):
    project_root = tmp_path / "ml-research-loop"
    project_root.mkdir()
    output = tmp_path / "claude-code.json"

    exit_code = main([
        "init-mcp-config",
        "--client",
        "claude-code",
        "--project-root",
        str(project_root),
        "--python",
        "/opt/python/bin/python3",
        "--output",
        str(output),
    ])

    assert exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    server = payload["mcpServers"]["ml-research-loop"]
    assert server["type"] == "stdio"
    assert server["command"] == "/opt/python/bin/python3"
    assert server["args"] == [str(project_root / "scripts" / "mcp_server.py")]
    assert server["env"]["PYTHONPATH"] == str(project_root)
    assert server["env"]["ML_RESEARCH_LOOP_PYTHON"] == "/opt/python/bin/python3"


def test_init_mcp_config_refuses_to_overwrite_without_force(tmp_path):
    project_root = tmp_path / "ml-research-loop"
    project_root.mkdir()
    output = tmp_path / "codex.toml"
    output.write_text("existing", encoding="utf-8")

    exit_code = main([
        "init-mcp-config",
        "--client",
        "codex",
        "--project-root",
        str(project_root),
        "--output",
        str(output),
    ])

    assert exit_code == 1
    assert output.read_text(encoding="utf-8") == "existing"


def test_init_skills_copies_repo_skills_to_target_root(tmp_path, capsys):
    target_root = tmp_path / "codex-skills"

    exit_code = main([
        "init-skills",
        "--client",
        "codex",
        "--target-root",
        str(target_root),
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "installed"
    assert payload["client"] == "codex"
    assert payload["target_root"] == str(target_root.resolve())
    assert [item["name"] for item in payload["skills"]] == SKILL_NAMES
    for name in SKILL_NAMES:
        assert (target_root / name / "SKILL.md").exists()


def test_init_skills_refuses_to_overwrite_without_force(tmp_path, capsys):
    target_root = tmp_path / "claude-skills"
    existing_skill = target_root / "ml-research-loop-planner"
    existing_skill.mkdir(parents=True)
    existing_file = existing_skill / "SKILL.md"
    existing_file.write_text("custom", encoding="utf-8")

    exit_code = main([
        "init-skills",
        "--client",
        "claude",
        "--target-root",
        str(target_root),
    ])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Refusing to overwrite existing skill" in captured.err
    assert existing_file.read_text(encoding="utf-8") == "custom"


def test_init_skills_force_overwrites_existing_skill(tmp_path, capsys):
    target_root = tmp_path / "codex-skills"
    existing_skill = target_root / "ml-research-loop-planner"
    existing_skill.mkdir(parents=True)
    (existing_skill / "SKILL.md").write_text("custom", encoding="utf-8")

    exit_code = main([
        "init-skills",
        "--client",
        "codex",
        "--target-root",
        str(target_root),
        "--force",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "installed"
    assert (
        target_root / "ml-research-loop-planner" / "SKILL.md"
    ).read_text(encoding="utf-8").startswith("---\n")


def test_init_skills_dry_run_reports_default_target_root(monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: Path("/Users/tester"))

    codex_exit = main(["init-skills", "--client", "codex", "--dry-run"])
    codex_payload = json.loads(capsys.readouterr().out)
    claude_exit = main(["init-skills", "--client", "claude", "--dry-run"])
    claude_payload = json.loads(capsys.readouterr().out)

    assert codex_exit == 0
    assert claude_exit == 0
    assert codex_payload["target_root"] == "/Users/tester/.codex/skills"
    assert claude_payload["target_root"] == "/Users/tester/.claude/skills"


def test_feedback_bundle_command_prints_output_paths(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        "scripts.cli.build_feedback_bundle",
        lambda **kwargs: {
            "bundle_version": "test",
            "runtime": {"runtime_root": str(kwargs["runtime_root"])},
        },
    )
    monkeypatch.setattr(
        "scripts.cli.write_feedback_bundle",
        lambda bundle, output_dir: {
            "status": "written",
            "json_path": str(output_dir / "feedback-bundle.json"),
            "markdown_path": str(output_dir / "feedback-bundle.md"),
            "bundle": bundle,
        },
    )

    exit_code = main([
        "feedback-bundle",
        "--runtime-root",
        str(tmp_path / "runtime"),
        "--output-dir",
        str(tmp_path / "bundle"),
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["bundle"]["runtime"]["runtime_root"] == str(tmp_path / "runtime")


def test_benchmark_readiness_command_prints_manifest_payload(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.cli.build_benchmark_readiness",
        lambda: {"status": "compatibility_ready", "adapters": []},
    )

    exit_code = main(["benchmark", "readiness", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == {"status": "compatibility_ready", "adapters": []}


def test_benchmark_smoke_command_invokes_smoke_script(monkeypatch, tmp_path):
    captured = {}

    def fake_call(cmd, cwd=None):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return 0

    monkeypatch.setattr("scripts.cli.subprocess.call", fake_call)

    exit_code = main([
        "benchmark",
        "smoke",
        "--runtime-root",
        str(tmp_path / "runtime"),
        "--python",
        "/opt/python/bin/python3",
        "--json",
    ])

    assert exit_code == 0
    assert captured["cmd"][0] == "/opt/python/bin/python3"
    assert captured["cmd"][1].endswith("scripts/benchmark_adapter_smoke.py")
    assert captured["cmd"][2:] == [
        "--runtime-root",
        str(tmp_path / "runtime"),
        "--json",
    ]


def test_benchmark_probe_command_prints_harness_probe(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.cli.build_official_harness_probe",
        lambda **kwargs: {"status": "needs_setup", "read_only": True},
    )

    exit_code = main(["benchmark", "probe", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == {"status": "needs_setup", "read_only": True}


def test_benchmark_proof_plan_command_prints_plan(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.cli.build_official_harness_probe",
        lambda **kwargs: {"status": "needs_setup", "read_only": True},
    )
    monkeypatch.setattr(
        "scripts.cli.build_public_proof_plan",
        lambda probe: {"status": "blocked", "harness_probe": probe},
    )

    exit_code = main(["benchmark", "proof-plan", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == {
        "status": "blocked",
        "harness_probe": {"status": "needs_setup", "read_only": True},
    }


def test_benchmark_setup_bundle_command_writes_bundle(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        "scripts.cli.build_official_harness_probe",
        lambda **kwargs: {"status": "needs_setup", "read_only": True},
    )
    monkeypatch.setattr(
        "scripts.cli.build_public_proof_plan",
        lambda probe: {"status": "blocked", "harness_probe": probe},
    )
    monkeypatch.setattr(
        "scripts.cli.build_official_proof_setup_bundle",
        lambda proof_plan: {"read_only": True, "proof_plan": proof_plan},
    )
    monkeypatch.setattr(
        "scripts.cli.write_official_proof_setup_bundle",
        lambda bundle, output_dir: {
            "status": "written",
            "json_path": str(output_dir / "official-proof-setup.json"),
        },
    )

    exit_code = main([
        "benchmark",
        "setup-bundle",
        "--output-dir",
        str(tmp_path / "proof-setup"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["json_path"].endswith("official-proof-setup.json")


def test_benchmark_publication_bundle_command_writes_bundle(monkeypatch, tmp_path, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"benchmark_name": "mle_bench"}', encoding="utf-8")
    monkeypatch.setattr(
        "scripts.cli.build_proof_publication_bundle",
        lambda artifact_manifest, artifact_root: {
            "read_only": True,
            "artifact_root": str(artifact_root),
            "artifact_manifest": artifact_manifest,
        },
    )
    monkeypatch.setattr(
        "scripts.cli.write_proof_publication_bundle",
        lambda bundle, output_dir: {
            "status": "written",
            "json_path": str(output_dir / "proof-publication.json"),
        },
    )

    exit_code = main([
        "benchmark",
        "publication-bundle",
        "--manifest",
        str(manifest),
        "--artifact-root",
        str(tmp_path / "artifacts"),
        "--output-dir",
        str(tmp_path / "publication"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["json_path"].endswith("proof-publication.json")


def test_benchmark_archive_proof_command_writes_archive(monkeypatch, tmp_path, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"benchmark_name": "mle_bench"}', encoding="utf-8")
    monkeypatch.setattr(
        "scripts.cli.build_proof_archive_bundle",
        lambda artifact_manifest, artifact_root: {
            "status": "archivable",
            "artifact_root": str(artifact_root),
            "artifact_manifest": artifact_manifest,
        },
    )
    monkeypatch.setattr(
        "scripts.cli.write_proof_archive_bundle",
        lambda bundle, artifact_root, output_dir: {
            "status": "written",
            "json_path": str(output_dir / "proof-archive.json"),
        },
    )

    exit_code = main([
        "benchmark",
        "archive-proof",
        "--manifest",
        str(manifest),
        "--artifact-root",
        str(tmp_path / "artifacts"),
        "--output-dir",
        str(tmp_path / "archive"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["json_path"].endswith("proof-archive.json")


def test_benchmark_mle_workspace_command_writes_agent_workspace(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(
        "scripts.cli.materialize_official_mle_agent_workspace",
        lambda **kwargs: {
            "status": "ready_for_agent",
            "competition_id": kwargs["competition_id"],
            "workspace": str(kwargs["runtime_root"] / "benchmark-workspaces"),
        },
    )

    exit_code = main([
        "benchmark",
        "mle-workspace",
        "--competition-id",
        "spooky-author-identification",
        "--prepared-competition-dir",
        str(tmp_path / "mlebench-data" / "spooky-author-identification"),
        "--runtime-root",
        str(tmp_path / "runtime"),
        "--workspace-name",
        "spooky-debug",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "ready_for_agent"
    assert payload["competition_id"] == "spooky-author-identification"


def test_benchmark_mle_grade_command_runs_official_grade_sample(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(
        "scripts.cli.grade_official_mle_submission",
        lambda **kwargs: {
            "status": "graded",
            "competition_id": kwargs["competition_id"],
            "report": {"score": 1.23},
            "official_scores_claimed": False,
        },
    )

    exit_code = main([
        "benchmark",
        "mle-grade",
        "--competition-id",
        "spooky-author-identification",
        "--submission",
        str(tmp_path / "workspace" / "submission.csv"),
        "--data-dir",
        str(tmp_path / "mlebench-data"),
        "--mlebench",
        str(tmp_path / "venv" / "bin" / "mlebench"),
        "--output-dir",
        str(tmp_path / "reports"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "graded"
    assert payload["official_scores_claimed"] is False


def test_benchmark_mle_round_command_runs_solver_and_grade(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(
        "scripts.cli.run_official_mle_solver_round",
        lambda **kwargs: {
            "status": "graded",
            "competition_id": kwargs["competition_id"],
            "workspace": str(kwargs["workspace"]),
            "round_id": kwargs["round_id"],
            "grade": {"report": {"score": 1.23}},
            "official_scores_claimed": False,
        },
        raising=False,
    )

    exit_code = main([
        "benchmark",
        "mle-round",
        "--competition-id",
        "spooky-author-identification",
        "--workspace",
        str(tmp_path / "workspace"),
        "--data-dir",
        str(tmp_path / "mlebench-data"),
        "--mlebench",
        str(tmp_path / "venv" / "bin" / "mlebench"),
        "--output-dir",
        str(tmp_path / "rounds"),
        "--python",
        "python3",
        "--round-id",
        "round-001",
        "--timeout-seconds",
        "10",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "graded"
    assert payload["round_id"] == "round-001"
    assert payload["official_scores_claimed"] is False


def test_benchmark_mle_patch_round_command_applies_patch_then_runs_round(
    monkeypatch,
    tmp_path,
    capsys,
):
    patch_file = tmp_path / "patch.diff"
    patch_file.write_text("--- a/solve.py\n+++ b/solve.py\n@@ -1,1 +1,1 @@\n-old\n+new\n")
    monkeypatch.setattr(
        "scripts.cli.mcp_service.run_official_mle_bench_patch_round_tool",
        lambda arguments: {
            "status": "graded",
            "competition_id": arguments["competition_id"],
            "round_id": arguments["round_id"],
            "patch_execution": {"status": "applied"},
            "round": {"status": "graded"},
            "loop_decision": {"recommended_next_action": "continue"},
            "official_scores_claimed": False,
        },
    )

    exit_code = main([
        "benchmark",
        "mle-patch-round",
        "--competition-id",
        "spooky-author-identification",
        "--workspace",
        str(tmp_path / "workspace"),
        "--data-dir",
        str(tmp_path / "mlebench-data"),
        "--mlebench",
        str(tmp_path / "venv" / "bin" / "mlebench"),
        "--output-dir",
        str(tmp_path / "rounds"),
        "--patch-file",
        str(patch_file),
        "--python",
        "python3",
        "--round-id",
        "round-002",
        "--timeout-seconds",
        "10",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "graded"
    assert payload["patch_execution"]["status"] == "applied"
    assert payload["round"]["status"] == "graded"
    assert payload["official_scores_claimed"] is False


def test_benchmark_mle_patch_proof_command_writes_bundle(
    monkeypatch,
    tmp_path,
    capsys,
):
    patch_round_report = tmp_path / "patch-round-report.json"
    patch_round_report.write_text('{"status": "graded"}', encoding="utf-8")
    monkeypatch.setattr(
        "scripts.cli.write_official_mle_patch_round_proof_bundle",
        lambda *, patch_round_report, output_dir: {
            "status": "written",
            "patch_round_report": str(patch_round_report),
            "manifest_path": str(output_dir / "manifest.json"),
            "archive": {"bundle": {"status": "archivable"}},
            "official_scores_claimed": False,
        },
    )

    exit_code = main([
        "benchmark",
        "mle-patch-proof",
        "--patch-round-report",
        str(patch_round_report),
        "--output-dir",
        str(tmp_path / "proof"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["official_scores_claimed"] is False
    assert payload["archive"]["bundle"]["status"] == "archivable"


def test_benchmark_paperbench_codex_review_bundle_command_writes_bundle(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(
        "scripts.cli.write_paperbench_codex_review_bundle",
        lambda *, run_dir, paper_dir, output_dir: {
            "status": "written",
            "bundle_path": str(output_dir / "codex-review-bundle.json"),
            "prompt_path": str(output_dir / "codex-review-prompt.md"),
            "bundle": {
                "paper_id": paper_dir.name,
                "judge_type": "codex_assisted",
                "official_scores_claimed": False,
                "paperbench_score": None,
                "source_run": str(run_dir),
            },
        },
    )

    exit_code = main([
        "benchmark",
        "paperbench-codex-review-bundle",
        "--run-dir",
        str(tmp_path / "runs" / "rice_123"),
        "--paper-dir",
        str(tmp_path / "papers" / "rice"),
        "--output-dir",
        str(tmp_path / "codex-review"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["bundle"]["judge_type"] == "codex_assisted"
    assert payload["bundle"]["official_scores_claimed"] is False
    assert payload["bundle"]["paperbench_score"] is None


def test_benchmark_paperbench_codex_review_report_command_writes_report(
    monkeypatch,
    tmp_path,
    capsys,
):
    review_file = tmp_path / "codex-review.json"
    review_file.write_text(
        json.dumps({"summary": "reviewed", "codex_review_score": 0.5}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "scripts.cli.write_paperbench_codex_review_report",
        lambda *, bundle_path, review_payload, output_dir: {
            "status": "written",
            "json_path": str(output_dir / "codex-review-report.json"),
            "markdown_path": str(output_dir / "codex-review-report.md"),
            "source_bundle": str(bundle_path),
            "report": {
                "judge_type": "codex_assisted",
                "official_scores_claimed": False,
                "paperbench_score": None,
                "codex_review_score": review_payload["codex_review_score"],
            },
        },
    )

    exit_code = main([
        "benchmark",
        "paperbench-codex-review-report",
        "--bundle",
        str(tmp_path / "codex-review-bundle.json"),
        "--review-file",
        str(review_file),
        "--output-dir",
        str(tmp_path / "codex-review-report"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["report"]["codex_review_score"] == 0.5
    assert payload["report"]["official_scores_claimed"] is False
    assert payload["report"]["paperbench_score"] is None


def test_demo_list_command_prints_templates(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.cli.list_demo_templates",
        lambda: [{"name": "byte-lm-smoke", "description": "demo"}],
    )

    exit_code = main(["demo", "list"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["templates"][0]["name"] == "byte-lm-smoke"


def test_demo_init_command_materializes_template(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        "scripts.cli.materialize_demo_template",
        lambda **kwargs: {
            "status": "initialized",
            "template": {"name": kwargs["template_name"]},
            "runtime_root": str(kwargs["runtime_root"]),
        },
    )

    exit_code = main([
        "demo",
        "init",
        "--template",
        "byte-lm-smoke",
        "--runtime-root",
        str(tmp_path / "runtime"),
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "initialized"
    assert payload["template"]["name"] == "byte-lm-smoke"
