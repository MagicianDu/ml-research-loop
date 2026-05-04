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
