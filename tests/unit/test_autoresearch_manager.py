from ml_intern.autoresearch_manager import AutoResearchConfig, AutoResearchManager


def _patch_workspace(monkeypatch, tmp_path):
    from lib import task_protocol

    monkeypatch.setattr(task_protocol, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(task_protocol, "TASKS_DIR", tmp_path / "tasks")
    monkeypatch.setattr(task_protocol, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(task_protocol, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(task_protocol, "SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(task_protocol, "WORKDIR_DIR", tmp_path / "workdir")


def test_launch_releases_task_lock_when_subagent_not_spawned(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ml_intern.autoresearch_manager._spawn_autoresearch_subagent",
        lambda task_id, workspace: {"session_key": None, "session": None},
    )
    manager = AutoResearchManager(workspace_root=tmp_path)
    config = AutoResearchConfig(
        task_id="demo",
        objective="minimize val_bpb",
        dataset_path="missing.bin",
        metric_name="val_bpb",
        metric_direction="minimize",
    )

    task_id = manager.launch(config)

    assert task_id == "demo"
    assert (tmp_path / "tasks" / "demo.json").exists()
    assert not (tmp_path / "tasks" / "demo.lock").exists()
    assert manager.active_tasks["demo"]["session_key"] is None
    assert manager.active_tasks["demo"]["subagent_launched"] is False
