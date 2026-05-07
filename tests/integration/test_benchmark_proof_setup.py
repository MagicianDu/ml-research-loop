from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_benchmark_proof_setup_script_writes_read_only_bundle(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{PROJECT_ROOT}{os.pathsep}"
            f"{PROJECT_ROOT / '.venv' / 'lib' / 'python3.13' / 'site-packages'}"
        ),
    }
    output_dir = tmp_path / "proof-setup"

    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "benchmark_proof_setup.py"),
            "--output-dir",
            str(output_dir),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stdout
    payload = json.loads(proc.stdout.splitlines()[-1])
    assert payload["status"] == "written"
    assert Path(payload["json_path"]).exists()
    assert Path(payload["markdown_path"]).exists()
    assert Path(payload["env_example_path"]).exists()
    bundle = json.loads(Path(payload["json_path"]).read_text(encoding="utf-8"))
    assert bundle["read_only"] is True
    assert bundle["official_scores_claimed"] is False
