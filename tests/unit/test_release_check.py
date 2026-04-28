from __future__ import annotations

import json
from pathlib import Path

from scripts import release_check


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_release_check_builds_make_independent_commands() -> None:
    commands = release_check.build_release_commands(
        python="python3",
        project_root=PROJECT_ROOT,
        skip_golden_path=False,
    )
    labels = [command.label for command in commands]

    assert labels == [
        "ruff",
        "pytest",
        "mcp-stdio-smoke",
        "mcp-golden-path",
    ]
    assert all(command.argv[0] == "python3" or command.argv[0].endswith("ruff") for command in commands)
    assert not any("make" in part for command in commands for part in command.argv)


def test_release_check_json_summary_marks_failed_command() -> None:
    result = release_check.CheckResult(
        label="pytest",
        returncode=1,
        duration_seconds=0.12,
        stdout="failed",
    )

    payload = json.loads(release_check.render_summary([result]))

    assert payload["status"] == "failed"
    assert payload["checks"][0]["label"] == "pytest"
    assert payload["checks"][0]["returncode"] == 1


def test_release_check_doc_lists_required_commands() -> None:
    doc = (PROJECT_ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")

    assert "python3 scripts/release_check.py" in doc
    assert "scripts/mcp_golden_path.py" in doc
    assert "pytest tests/ -q" in doc
    assert "ruff check" in doc
