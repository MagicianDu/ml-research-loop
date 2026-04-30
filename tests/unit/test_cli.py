import json

from scripts.cli import build_parser, main


def test_parser_has_run_status_result_subcommands():
    parser = build_parser()

    run_args = parser.parse_args(["run", "--task-config", "tasks/demo.json"])
    status_args = parser.parse_args(["status", "demo"])
    result_args = parser.parse_args(["result", "demo"])
    check_args = parser.parse_args(["check", "--json"])
    artifacts_args = parser.parse_args(["artifacts", "list", "--runtime-root", "/tmp/runtime"])

    assert run_args.command == "run"
    assert status_args.command == "status"
    assert result_args.command == "result"
    assert check_args.command == "check"
    assert artifacts_args.command == "artifacts"
    assert artifacts_args.artifact_command == "list"


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
