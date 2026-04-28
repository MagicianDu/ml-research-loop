import json
import os
import subprocess
import sys
from pathlib import Path


def test_autoresearch_cli_smoke(tmp_path):
    root = Path(__file__).resolve().parents[2]
    task_dir = tmp_path / "tasks"
    task_dir.mkdir()
    task_file = task_dir / "smoke.json"
    task_file.write_text(
        json.dumps(
            {
                "task_id": "smoke",
                "objective": "minimize val_bpb on synthetic data",
                "dataset": {"name": "synthetic", "path": "missing.bin"},
                "metric": {"name": "val_bpb", "direction": "minimize", "threshold": 0.0},
                "hyperparameter_space": {
                    "depth": {"type": "choice", "values": [4]},
                    "dim": {"type": "choice", "values": [64]},
                    "batch_size": {"type": "choice", "values": [2]},
                    "window_size": {"type": "choice", "values": [64]},
                },
                "budget": {
                    "max_experiments": 1,
                    "max_duration_minutes": 2,
                    "experiment_duration_seconds": 30,
                },
                "base_code": {
                    "train_py_url": f"file://{root / 'base' / 'train_base.py'}",
                    "prepare_py_url": f"file://{root / 'base' / 'prepare.py'}",
                },
            }
        ),
        encoding="utf-8",
    )

    env = {
        **os.environ,
        "ML_RESEARCH_LOOP_ROOT": str(tmp_path),
        "ML_RESEARCH_LOOP_PYTHON": sys.executable,
        "PYTHONPATH": f"{root}:{root / '.venv' / 'lib' / 'python3.13' / 'site-packages'}",
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "autoresearch_run.py"),
            "--task-config",
            str(task_file),
            "--workspace",
            str(tmp_path / "workdir" / "smoke"),
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
    result_file = tmp_path / "results" / "smoke.json"
    assert result_file.exists()
    result = json.loads(result_file.read_text(encoding="utf-8"))
    assert result["status"] == "completed"
    assert result["summary"]["total_experiments"] == 1
