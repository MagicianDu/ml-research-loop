from lib.task_protocol import TaskResult, TaskStatus
from codex_plugin.codex_adapter import MLResearchLoopCodexAdapter


def test_get_results_reads_task_result_object(monkeypatch):
    result = TaskResult(
        task_id="demo",
        status=TaskStatus.COMPLETED,
        best_result={"experiment_id": "exp-001", "val": 0.42, "params": {"lr": 0.001}},
        summary={"total_experiments": 3, "total_duration_minutes": 1.2},
    )

    monkeypatch.setattr("codex_plugin.codex_adapter.read_result", lambda task_id: result)
    adapter = MLResearchLoopCodexAdapter()

    payload = adapter.get_ml_experiment_results("demo")

    assert payload["success"] is True
    assert payload["status"] == "completed"
    assert payload["best_val"] == 0.42
    assert payload["best_params"] == {"lr": 0.001}
    assert payload["total_experiments"] == 3
    assert payload["total_duration_minutes"] == 1.2


def test_get_results_reports_not_ready(monkeypatch):
    from lib.exceptions import ResultNotReadyError

    def raise_not_ready(task_id):
        raise ResultNotReadyError("not ready")

    monkeypatch.setattr("codex_plugin.codex_adapter.read_result", raise_not_ready)
    adapter = MLResearchLoopCodexAdapter()

    payload = adapter.get_ml_experiment_results("demo")

    assert payload["success"] is False
    assert payload["status"] == "not_ready"
