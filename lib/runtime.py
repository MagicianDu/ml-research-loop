"""Runtime helpers for local ml-research-loop execution."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _is_executable(path: Path) -> bool:
    return path.exists() and path.is_file() and os.access(path, os.X_OK)


def resolve_python_executable(project_root: Path) -> str:
    """Resolve the Python executable used to launch per-experiment train.py."""
    override = os.environ.get("ML_RESEARCH_LOOP_PYTHON")
    if override:
        override_path = Path(override).expanduser()
        if not _is_executable(override_path):
            raise RuntimeError(f"ML_RESEARCH_LOOP_PYTHON is not executable: {override_path}")
        return str(override_path)

    venv_python = project_root / ".venv" / "bin" / "python3"
    if _is_executable(venv_python):
        return str(venv_python)

    return sys.executable
