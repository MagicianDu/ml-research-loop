from __future__ import annotations

import json
from pathlib import Path

from scripts import fresh_checkout_check


def test_fresh_checkout_check_builds_public_checkout_commands(tmp_path: Path) -> None:
    checkout, commands = fresh_checkout_check.build_commands(
        repo_url="https://github.com/MagicianDu/ml-research-loop.git",
        ref="v0.1.0-preview",
        python="/usr/bin/python3",
        workdir=tmp_path,
        skip_golden_path=False,
    )

    labels = [command.label for command in commands]

    assert checkout == tmp_path / "ml-research-loop"
    assert labels == [
        "git-clone",
        "create-venv",
        "install",
        "mcp-client-acceptance",
        "render-codex-config",
        "skills-dry-run",
        "mcp-golden-path",
    ]
    assert commands[0].argv == [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        "v0.1.0-preview",
        "https://github.com/MagicianDu/ml-research-loop.git",
        str(checkout),
    ]
    assert commands[2].argv[:4] == [
        str(checkout / ".venv" / "bin" / "python"),
        "-m",
        "pip",
        "install",
    ]
    assert commands[3].argv[-2:] == ["--project-root", str(checkout)]
    assert commands[4].argv[0] == str(checkout / ".venv" / "bin" / "ml-loop")
    assert commands[6].argv[1].endswith("scripts/mcp_golden_path.py")


def test_fresh_checkout_check_summary_marks_failed_command(tmp_path: Path) -> None:
    payload = json.loads(
        fresh_checkout_check.render_summary(
            repo_url="repo",
            ref="main",
            checkout=tmp_path / "ml-research-loop",
            results=[
                fresh_checkout_check.FreshResult(
                    label="git-clone",
                    returncode=0,
                    duration_seconds=1.0,
                    stdout="ok\n",
                ),
                fresh_checkout_check.FreshResult(
                    label="install",
                    returncode=1,
                    duration_seconds=2.0,
                    stdout="\n".join(str(index) for index in range(30)),
                ),
            ],
        )
    )

    assert payload["status"] == "failed"
    assert payload["checks"][1]["label"] == "install"
    assert payload["checks"][1]["returncode"] == 1
    assert payload["checks"][1]["stdout_tail"].splitlines()[0] == "10"
