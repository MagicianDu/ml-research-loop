from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_mcp_real_data_demo_uses_local_dataset_file(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{PROJECT_ROOT}{os.pathsep}"
            f"{PROJECT_ROOT / '.venv' / 'lib' / 'python3.13' / 'site-packages'}"
        ),
        "ML_RESEARCH_LOOP_PYTHON": sys.executable,
        "ML_RESEARCH_LOOP_ALLOWED_ROOTS": str(tmp_path / "mcp-runtime"),
    }

    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "mcp_real_data_demo.py"),
            "--runtime-root",
            str(tmp_path / "mcp-runtime"),
            "--max-experiments",
            "1",
            "--experiment-duration",
            "30",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, proc.stdout
    payload = json.loads(proc.stdout.splitlines()[-1])

    assert payload["status"] == "completed"
    assert payload["data_source"] == "real_file"
    assert Path(payload["dataset_file"]).exists()
    assert payload["review"]["experiments"][0]["metrics"]["val_bpb"] > 0
