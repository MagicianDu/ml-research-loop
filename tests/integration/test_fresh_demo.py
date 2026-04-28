import json
import os
import subprocess
import sys
from pathlib import Path


def test_fresh_demo_runs_without_existing_checkpoint():
    root = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "ML_RESEARCH_LOOP_PYTHON": sys.executable,
        "PYTHONPATH": f"{root}:{root / '.venv' / 'lib' / 'python3.13' / 'site-packages'}",
    }

    results = []
    for _ in range(2):
        proc = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "fresh_demo.py"),
                "--max-experiments",
                "1",
                "--experiment-duration",
                "30",
            ],
            cwd=str(root),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
        )

        assert proc.returncode == 0, proc.stdout
        payload = json.loads(proc.stdout.splitlines()[-1])
        result_path = Path(payload["result_file"])
        assert payload["status"] == "completed"
        assert result_path.exists()
        results.append(payload)

    assert results[0]["runtime_root"] != results[1]["runtime_root"]
