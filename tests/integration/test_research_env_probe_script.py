from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_research_env_probe_script_outputs_blocked_json(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "research_env_probe.py"),
            "--workspace",
            str(tmp_path),
            "--required-file",
            "train.py",
            "--json",
        ],
        check=True,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)

    assert payload["status"] == "blocked"
    assert payload["workspace"] == str(tmp_path.resolve())
    assert payload["missing_files"] == ["train.py"]
    assert payload["repair_plan"][0]["path"] == "train.py"
