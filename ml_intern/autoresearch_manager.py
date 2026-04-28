"""
autoresearch_manager.py — manages autoresearch sub-agent lifecycle from ml-intern.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lib.task_protocol import (
    TaskDefinition,
    TaskResult,
    write_task,
    read_progress,
    read_result,
    acquire_task_lock,
    release_task_lock,
    MetricDirection,
    WORKSPACE_ROOT,
)


def _spawn_autoresearch_subagent(task_id: str, workspace: Path) -> dict:
    """Spawn the actual autoresearch sub-agent via sessions_spawn.
    
    Gracefully handles environments where OpenClaw runtime is not available
    (e.g., standalone testing). In that case, logs a warning and returns
    a dummy session info dict.
    """
    try:
        from openclaw import sessions_spawn
    except ImportError:
        import warnings
        warnings.warn(
            f"openclaw.sessions_spawn not available (outside OpenClaw runtime?). "
            f"Task {task_id} will be created but sub-agent will not spawn."
        )
        return {"session_key": None, "session": None}

    workdir = workspace / "workdir" / task_id
    workdir.mkdir(parents=True, exist_ok=True)

    task_prompt = f"""你是 AutoResearch 研究员。任务ID: {task_id}

请读取 task.json，执行 ML 研究实验。
工作目录: {workdir}/

首先确保 task.json 在 tasks/ 目录下。
然后执行 scripts/autoresearch_run.py，参数: max_experiments=10, experiment_duration=300

研究过程中定期更新 results/{task_id}-progress.json 进度文件。
完成后将最终结果写入 results/{task_id}.json
"""

    session = sessions_spawn(
        label=f"autoresearch-{task_id}",
        mode="session",
        runtime="subagent",
        task=task_prompt,
    )
    return {"session_key": session.session_key, "session": session}


def _query_subagent_status(session_key: str) -> dict:
    """Query the status of a running sub-agent session."""
    try:
        from openclaw import sessions_list
    except ImportError:
        return {"session_key": session_key, "status": "unknown", "last_message": "openclaw not available"}

    try:
        sessions = sessions_list(search=session_key, limit=5, includeLastMessage=True)
        for s in sessions.get("sessions", []):
            if s.get("sessionKey") == session_key or session_key in str(s.get("sessionKey", "")):
                last = s.get("lastMessage", "")
                status = "running"
                if "completed" in last.lower() or "done" in last.lower():
                    status = "completed"
                elif "error" in last.lower():
                    status = "error"
                return {
                    "session_key": session_key,
                    "status": status,
                    "label": s.get("label", ""),
                    "last_message": last[:200] if last else "",
                    "derived_title": s.get("derivedTitle", ""),
                }
        return {"session_key": session_key, "status": "unknown", "last_message": ""}
    except Exception as e:
        return {"session_key": session_key, "status": "error", "error": str(e), "last_message": ""}


@dataclass
class AutoResearchConfig:
    """Configuration for launching an autoresearch sub-agent."""
    task_id: str
    objective: str
    dataset_path: str
    metric_name: str
    metric_direction: str  # "minimize" or "maximize"
    metric_target: Optional[float] = None
    max_experiments: int = 50
    max_duration_minutes: int = 120
    experiment_duration_seconds: int = 300
    hyperparameter_space: dict = None
    focus_areas: list = None
    forbidden_changes: list = None
    base_train_py_path: str = None


class AutoResearchManager:
    """
    Manages autoresearch sub-agent lifecycle from ml-intern.

    Usage:
        manager = AutoResearchManager()
        task_id = manager.launch(config)
        # ... later ...
        status = manager.get_status(task_id)
        result = manager.get_result(task_id)
        manager.cancel(task_id)
    """

    def __init__(self, workspace_root: Path = WORKSPACE_ROOT):
        self.workspace = workspace_root
        self.active_tasks: dict[str, dict] = {}

    def launch(self, config: AutoResearchConfig) -> str:
        """
        Launch an autoresearch sub-agent for the given task.

        Steps:
        1. Create TaskDefinition and write to tasks/<task_id>.json
        2. Acquire task lock
        3. Spawn sub-agent (via sessions_spawn in actual ml-intern integration)
        4. Return task_id for monitoring

        Returns:
            task_id: string identifier for the launched task
        """
        task_id = config.task_id

        # Build hyperparameter space dataclasses
        from lib.task_protocol import (
            DatasetConfig, MetricConfig, HyperparamSpace,
            BudgetConfig, BaseCodeConfig,
        )

        hyperparam_space = {}
        if config.hyperparameter_space:
            for name, spec in config.hyperparameter_space.items():
                hyperparam_space[name] = HyperparamSpace(**spec)

        # Determine base train.py path
        if config.base_train_py_path:
            train_py_url = f"file://{config.base_train_py_path}"
        else:
            train_py_url = f"file://{self.workspace}/base/train_base.py"

        # Build task definition
        task_def = TaskDefinition(
            task_id=task_id,
            objective=config.objective,
            dataset=DatasetConfig(
                name="dataset",
                path=config.dataset_path,
            ),
            metric=MetricConfig(
                name=config.metric_name,
                direction=MetricDirection(config.metric_direction),
                threshold=config.metric_target,
            ),
            hyperparameter_space=hyperparam_space,
            budget=BudgetConfig(
                max_experiments=config.max_experiments,
                max_duration_minutes=config.max_duration_minutes,
                experiment_duration_seconds=config.experiment_duration_seconds,
            ),
            base_code=BaseCodeConfig(
                train_py_url=train_py_url,
                prepare_py_url=f"file://{self.workspace}/base/prepare.py",
            ),
        )

        # Write task definition
        write_task(task_def)

        # Acquire lock (prevent duplicate runs)
        lock_path = acquire_task_lock(task_id)

        # Spawn sub-agent
        session_info = _spawn_autoresearch_subagent(task_id, self.workspace)
        session_key = session_info["session_key"]
        subagent_launched = session_key is not None

        if not subagent_launched:
            release_task_lock(task_id)

        # Store active task info
        self.active_tasks[task_id] = {
            "config": config,
            "lock_path": str(lock_path),
            "launched_at": time.time(),
            "session_key": session_key,
            "subagent_launched": subagent_launched,
        }

        return task_id

    def monitor(self, session_key: str) -> dict:
        """
        Monitor a running autoresearch sub-agent session.

        Returns:
            dict with keys: status, progress_pct, best_val, experiments_completed, errors
        """
        # Query sub-agent status
        agent_status = _query_subagent_status(session_key)

        # Try to find task_id from active_tasks by session_key
        task_id = None
        for tid, info in self.active_tasks.items():
            if info.get("session_key") == session_key:
                task_id = tid
                break

        if task_id is None:
            return {
                "status": "unknown",
                "progress_pct": 0.0,
                "best_val": None,
                "experiments_completed": 0,
                "errors": ["session_key not found in active tasks"],
                "agent_status": agent_status,
            }

        # Read progress from results file
        try:
            progress = read_progress(task_id)
            return {
                "status": progress.get("status", agent_status.get("status", "running")),
                "progress_pct": progress.get("progress_pct", 0.0),
                "best_val": progress.get("best_val"),
                "best_params": progress.get("best_params"),
                "experiments_completed": progress.get("experiment_index", 0),
                "errors": [progress.get("error")] if progress.get("error") else [],
                "agent_status": agent_status,
            }
        except FileNotFoundError:
            # No progress file yet — use agent status
            return {
                "status": agent_status.get("status", "starting"),
                "progress_pct": 0.0,
                "best_val": None,
                "experiments_completed": 0,
                "errors": [],
                "agent_status": agent_status,
            }

    def get_status(self, task_id: str) -> dict:
        """
        Get current status of an autoresearch task.
        Returns progress dict from results/<task_id>-progress.json.
        """
        try:
            progress = read_progress(task_id)
            return {
                "task_id": task_id,
                "status": progress.get("status", "unknown"),
                "experiment_index": progress.get("experiment_index", 0),
                "max_experiments": progress.get("max_experiments", 0),
                "best_val": progress.get("best_val"),
                "best_params": progress.get("best_params"),
                "progress_pct": progress.get("progress_pct", 0.0),
                "elapsed_minutes": progress.get("elapsed_minutes"),
                "error": progress.get("error"),
            }
        except FileNotFoundError:
            return {"task_id": task_id, "status": "pending"}

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """
        Get final result of a completed task.
        Returns None if result is not yet available.
        """
        try:
            return read_result(task_id)
        except FileNotFoundError:
            return None

    def cancel(self, task_id: str) -> bool:
        """
        Cancel a running task.
        Releases lock and marks task as cancelled.
        """
        try:
            release_task_lock(task_id)
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
            return True
        except Exception:
            return False

    def wait_for_completion(
        self,
        task_id: str,
        timeout_seconds: Optional[int] = None,
        poll_interval_seconds: int = 30,
    ) -> TaskResult:
        """
        Wait for task to complete (blocking).
        Returns TaskResult when complete or timeout reached.
        """
        start = time.time()
        while True:
            result = self.get_result(task_id)
            if result is not None:
                return result

            if timeout_seconds and (time.time() - start) > timeout_seconds:
                raise TimeoutError(f"Task {task_id} did not complete within {timeout_seconds}s")

            time.sleep(poll_interval_seconds)

    def list_active_tasks(self) -> list[str]:
        """Return list of active task IDs."""
        return list(self.active_tasks.keys())


# ─── Convenience function for ml-intern tool ───────────────────────────────────

def create_autoresearch_task(
    task_id: str,
    objective: str,
    dataset_path: str,
    metric_name: str = "val_bpb",
    metric_direction: str = "minimize",
    metric_target: Optional[float] = None,
    max_experiments: int = 50,
    max_duration_minutes: int = 120,
    experiment_duration_seconds: int = 300,
    hyperparameter_space: dict = None,
    base_train_py_path: str = None,
) -> str:
    """
    Convenience function to create and launch an autoresearch task.

    This is the main entry point for ml-intern's run_autoresearch tool.
    """
    config = AutoResearchConfig(
        task_id=task_id,
        objective=objective,
        dataset_path=dataset_path,
        metric_name=metric_name,
        metric_direction=metric_direction,
        metric_target=metric_target,
        max_experiments=max_experiments,
        max_duration_minutes=max_duration_minutes,
        experiment_duration_seconds=experiment_duration_seconds,
        hyperparameter_space=hyperparameter_space or {
            "lr": {"type": "log_uniform", "min": 1e-5, "max": 1e-2},
            "depth": {"type": "choice", "values": [4, 6, 8, 10, 12]},
            "dim": {"type": "choice", "values": [128, 256, 384, 512]},
        },
        base_train_py_path=base_train_py_path,
    )

    manager = AutoResearchManager()
    return manager.launch(config)
