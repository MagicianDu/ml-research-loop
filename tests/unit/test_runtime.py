import sys

import pytest

from lib.runtime import resolve_python_executable


def test_resolve_python_uses_env_override(tmp_path, monkeypatch):
    fake_python = tmp_path / "python"
    fake_python.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_python.chmod(0o755)
    monkeypatch.setenv("ML_RESEARCH_LOOP_PYTHON", str(fake_python))

    assert resolve_python_executable(tmp_path) == str(fake_python)


def test_resolve_python_rejects_non_executable_env_override(tmp_path, monkeypatch):
    fake_python = tmp_path / "python"
    fake_python.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_python.chmod(0o644)
    monkeypatch.setenv("ML_RESEARCH_LOOP_PYTHON", str(fake_python))

    with pytest.raises(RuntimeError, match="not executable"):
        resolve_python_executable(tmp_path)


def test_resolve_python_falls_back_to_sys_executable_when_venv_not_executable(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("ML_RESEARCH_LOOP_PYTHON", raising=False)
    venv_python = tmp_path / ".venv" / "bin" / "python3"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")
    venv_python.chmod(0o644)

    assert resolve_python_executable(tmp_path) == sys.executable
