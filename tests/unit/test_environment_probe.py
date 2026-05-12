from __future__ import annotations

from pathlib import Path

from lib.environment_probe import probe_research_environment


def test_probe_reports_missing_required_files(tmp_path: Path) -> None:
    payload = probe_research_environment(
        workspace=tmp_path,
        required_files=["train.py", "data/train.csv"],
        required_commands=["python3"],
    )

    assert payload["status"] == "blocked"
    assert payload["missing_files"] == ["train.py", "data/train.csv"]
    assert payload["repair_plan"][0]["kind"] == "create_or_mount_file"
    assert payload["official_scores_claimed"] is False


def test_probe_blocks_required_files_that_escape_workspace(tmp_path: Path) -> None:
    outside_file = tmp_path.parent / "outside.txt"
    outside_file.write_text("outside\n", encoding="utf-8")

    payload = probe_research_environment(
        workspace=tmp_path,
        required_files=["../outside.txt", str(outside_file), "."],
        required_commands=[],
    )

    assert payload["status"] == "blocked"
    assert payload["invalid_required_files"] == [
        "../outside.txt",
        str(outside_file),
        ".",
    ]
    assert payload["missing_files"] == []
    assert any(entry["kind"] == "fix_required_file_path" for entry in payload["repair_plan"])


def test_probe_reports_ready_workspace(tmp_path: Path) -> None:
    (tmp_path / "train.py").write_text("print('ok')\n", encoding="utf-8")

    payload = probe_research_environment(
        workspace=tmp_path,
        required_files=["train.py"],
        required_commands=["python3"],
    )

    assert payload["status"] == "ready"
    assert payload["missing_files"] == []
    assert payload["missing_commands"] == []
    assert payload["workspace"] == str(tmp_path.resolve())


def test_probe_reports_missing_command(tmp_path: Path) -> None:
    payload = probe_research_environment(
        workspace=tmp_path,
        required_files=[],
        required_commands=["definitely-not-a-real-research-command"],
    )

    assert payload["status"] == "blocked"
    assert payload["missing_commands"] == ["definitely-not-a-real-research-command"]
    assert any(entry["kind"] == "install_command" for entry in payload["repair_plan"])


def test_probe_detects_secret_risk_files_without_blocking(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("TOKEN=value\n", encoding="utf-8")
    (tmp_path / "api_KEY.txt").write_text("value\n", encoding="utf-8")

    payload = probe_research_environment(
        workspace=tmp_path,
        required_files=[],
        required_commands=[],
    )

    assert payload["status"] == "ready"
    assert payload["secret_risk_files"] == [".env", "api_KEY.txt"]
    assert any(entry["kind"] == "redact_or_ignore_secret_file" for entry in payload["repair_plan"])
