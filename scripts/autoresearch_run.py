#!/usr/bin/env python3
# scripts/autoresearch_run.py
"""
autoresearch_run.py — ml-research-loop main entry script.

Usage:
    python scripts/autoresearch_run.py --task-config tasks/<task_id>.json

This script:
1. Loads the task definition
2. Sets up workdir (train.py, prepare.py, program.md)
3. Runs the experiment loop: sample params → train → validate → accept/reject
4. Writes results/ and progress/
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import shutil
import subprocess
import sys
import time
import json
from pathlib import Path
from typing import Optional

from lib.task_protocol import (
    TaskDefinition,
    TaskResult,
    TaskStatus,
    read_task,
    read_result,
    write_result,
    snapshot_code,
    now_iso,
    WORKSPACE_ROOT,
    RESULTS_DIR,
)
from lib.experiment_store import ExperimentStore
from lib.progress_reporter import ProgressReporter
from lib.checkpoint_manager import CheckpointManager
from lib.alert_manager import AlertManager, AlertType, AlertSeverity
from lib.exceptions import TrainingFailedError
from lib.metrics import select_metric_value
from lib.result_summary import build_result_summary
from lib.runtime import resolve_python_executable
from scripts.generate_program_md import generate_program_md
from scripts.sample_hyperparams import sample_hyperparameters


# ─── Constants ────────────────────────────────────────────────────────────────

# Project root for finding base templates
_ROOT = Path(__file__).parent.parent.resolve()

SEARCH_REGION_START = "# ======= AUTORESEARCH SEARCH REGION START ======="
SEARCH_REGION_END = "# ======= AUTORESEARCH SEARCH REGION END ======="
DEFAULT_EXPERIMENT_DURATION = 300  # 5 minutes

METRIC_PREFIXES = ("val_", "metric_", "loss_", "bpb", "ppl", "acc", "f1", "precision", "recall")
METRIC_PREFIX_HINT = ", ".join(METRIC_PREFIXES)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Autoresearch experiment loop with external task config",
    )
    parser.add_argument("--task-config", type=str, required=True,
                        help="Path to task JSON definition")
    parser.add_argument("--workspace", type=str, default=None,
                        help="Working directory (default: workdir/<task_id>)")
    parser.add_argument("--max-experiments", type=int, default=None,
                        help="Override max_experiments from task config")
    parser.add_argument("--max-duration", type=int, default=None,
                        help="Override max_duration_minutes from task config")
    parser.add_argument("--experiment-duration", type=int, default=DEFAULT_EXPERIMENT_DURATION,
                        help="Experiment duration in seconds (default: 300)")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


# ─── Workdir Setup ────────────────────────────────────────────────────────────

def setup_workdir(task: TaskDefinition, workspace: Path) -> None:
    """Initialize workdir: copy train_base.py, symlink prepare.py, generate program.md."""
    workspace.mkdir(parents=True, exist_ok=True)

    # Copy train_base.py → workdir/train.py
    base_train = _ROOT / "base" / "train_base.py"
    if not base_train.exists():
        raise FileNotFoundError(f"Base train template not found: {base_train}")
    shutil.copy2(base_train, workspace / "train.py")

    # Symlink prepare.py
    base_prepare = _ROOT / "base" / "prepare.py"
    prepare_link = workspace / "prepare.py"
    if not prepare_link.exists():
        if base_prepare.exists():
            os.symlink(base_prepare.resolve(), prepare_link)

    # Generate program.md
    program_content = generate_program_md(task)
    (workspace / "program.md").write_text(program_content, encoding="utf-8")


# ─── Hyperparameter Modification ───────────────────────────────────────────────

def modify_train_hyperparams(train_py_path: Path, params: dict) -> None:
    """
    Update hyperparameters within the SEARCH REGION of train.py.

    Preserves any existing variables in the SEARCH REGION that are NOT being
    overridden by the sampled params. Only modifies lines that match
    `<VAR> = <value>` assignments.

    Expected format in train.py:
        # ======= AUTORESEARCH SEARCH REGION START =======
        LR = 0.001
        BATCH_SIZE = 32
        # ======= AUTORESEARCH SEARCH REGION END =======
    """
    content = train_py_path.read_text(encoding="utf-8")

    if SEARCH_REGION_START not in content or SEARCH_REGION_END not in content:
        raise ValueError(
            f"train.py missing search region markers. "
            f"Add '{SEARCH_REGION_START}' and '{SEARCH_REGION_END}' around hyperparameters."
        )

    # Extract the search region
    pattern = rf"({re.escape(SEARCH_REGION_START)}.*{__import__('re').escape(SEARCH_REGION_END)})"
    match = re.search(pattern, content, flags=re.DOTALL)
    if not match:
        raise ValueError("Could not extract SEARCH REGION from train.py")

    region_body = match.group(1)

    # Parse existing assignments from the region body
    existing_assignments = {}
    for line in region_body.splitlines():
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.+)", line.strip())
        if m:
            existing_assignments[m.group(1)] = line.strip()

    # Build new lines: start with header, add new/updated params, then any preserved lines
    new_lines = [
        "# Auto-generated hyperparameters",
    ]

    # Add all sampled params
    for key, value in sorted(params.items()):
        if isinstance(value, float):
            new_lines.append(f"{key.upper()} = {value:.6g}")
        else:
            new_lines.append(f"{key.upper()} = {value!r}")

    # Preserve existing constants that were in the region but not in params
    # (things like BATCH_SIZE, WINDOW_SIZE, WEIGHT_DECAY the AI didn't modify)
    for var_name, line in sorted(existing_assignments.items()):
        upper_name = var_name.upper()
        if upper_name not in {k.upper() for k in params}:
            new_lines.append(line)

    new_region_body = "\n".join(new_lines) + "\n"

    # Replace only the region body within the full content
    # Use a non-greedy match that respects the START/END delimiters
    inner_pattern = rf"(?<={re.escape(SEARCH_REGION_START)}).*(?={re.escape(SEARCH_REGION_END)})"
    new_content = re.sub(inner_pattern, "\n" + new_region_body, content, count=1, flags=re.DOTALL)

    train_py_path.write_text(new_content, encoding="utf-8")


# ─── Training Execution ───────────────────────────────────────────────────────

def run_training(
    workspace: Path,
    experiment_id: str,
    duration_seconds: int,
    data_path: str | None = None,
    verbose: bool = False,
) -> dict:
    """Run train.py and parse metrics from stdout."""
    log_file = workspace / "logs" / f"{experiment_id}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        resolve_python_executable(_ROOT),
        "train.py",  # relative path (cwd=workspace)
    ]
    env = {**os.environ, "AUTORESEARCH_EXP_ID": experiment_id}
    if data_path:
        env["DATA_PATH"] = data_path

    if verbose:
        print(f"[{experiment_id}] Starting: {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd, cwd=str(workspace), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            **_process_group_kwargs(),
        )
    except OSError as e:
        raise TrainingFailedError(f"training_startup_failed: failed to start train.py: {e}") from e

    start_time = time.monotonic()
    timed_out = False
    try:
        stdout, _ = proc.communicate(timeout=duration_seconds)
        actual_duration = time.monotonic() - start_time
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        stdout, _ = proc.communicate()
        actual_duration = duration_seconds
        timed_out = True
        if verbose:
            print(f"[{experiment_id}] Timeout after {actual_duration:.1f}s — killed")

    stdout = stdout or ""
    log_file.write_text(stdout, encoding="utf-8")
    if timed_out:
        raise TrainingFailedError(
            f"training_timeout: train.py timed out after {actual_duration:.1f}s; "
            "process tree killed"
        )
    if proc.returncode:
        raise TrainingFailedError(
            f"training_nonzero_exit: train.py exited with exit code {proc.returncode}. "
            f"See log: {log_file}"
        )

    metrics = parse_training_output(stdout)
    if not metrics:
        raise TrainingFailedError(
            "training_missing_metric: train.py produced no supported metric output. "
            f"Expected [RESULT] lines or JSON fields with prefixes: {METRIC_PREFIX_HINT}. "
            f"See log: {log_file}"
        )
    metrics["actual_duration_seconds"] = actual_duration

    if verbose:
        val = metrics.get("val_bpb", metrics.get("val", "N/A"))
        print(f"[{experiment_id}] Done in {actual_duration:.1f}s — val={val}")

    return metrics


def _process_group_kwargs() -> dict:
    """Start a child process group so timeout cleanup can kill grandchildren."""
    if os.name == "posix":
        return {"start_new_session": True}
    return {}


def _kill_process_tree(proc: subprocess.Popen[str]) -> None:
    """Best-effort process-tree kill for timed-out training runs."""
    if proc.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            return
        except ProcessLookupError:
            return
        except OSError:
            pass
    proc.kill()


def parse_training_output(stdout: str) -> dict:
    """Parse validation metrics from training stdout."""
    metrics = {}

    for line in stdout.splitlines():
        line = line.strip()
        # Format: [RESULT] key=value or key=value anywhere in line
        if "[RESULT]" in line or any(p in line for p in METRIC_PREFIXES):
            for match in re.findall(
                r"([a-zA-Z_][a-zA-Z0-9_]*)=([0-9.+-]+(?:[eE][+-]?\d+)?)", line
            ):
                key, val_str = match
                if not any(key.startswith(p) for p in METRIC_PREFIXES):
                    continue
                try:
                    metrics[key] = float(val_str)
                except ValueError:
                    pass

        # JSON block — extract only metric-prefixed keys
        if line.startswith("{") and line.endswith("}"):
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, (int, float)) and any(k.startswith(p) for p in METRIC_PREFIXES):
                            metrics[k] = float(v)
            except json.JSONDecodeError:
                pass

    return metrics


# ─── Checkpoint Helper ───────────────────────────────────────────────────────

def _save_checkpoint_after_exp(
    checkpoint_mgr: CheckpointManager,
    task: TaskDefinition,
    store: ExperimentStore,
    workspace: Path,
    experiment_id: str,
    best_val: Optional[float],
    best_params: Optional[dict],
    exp_idx: int,
    verbose: bool = False,
) -> None:
    """Save checkpoint after a failed/skipped experiment (no new best possible)."""
    is_new_best = (
        best_val is not None
        and store.best_val is not None
        and store.best_val == best_val
    )
    checkpoint_mgr.save_checkpoint(
        experiment_id=experiment_id,
        experiments_json=store.to_dict(),
        workdir=workspace,
        is_new_best=is_new_best,
        best_val=best_val,
        best_params=best_params,
    )


def _experiment_lineage(task: TaskDefinition, exp_idx: int) -> dict:
    """Return hypothesis metadata to attach to an experiment record."""
    if not task.hypotheses:
        return {}

    hypothesis = task.hypotheses[exp_idx % len(task.hypotheses)]
    return {
        key: value
        for key, value in {
            "hypothesis_id": hypothesis.get("hypothesis_id"),
            "hypothesis_title": hypothesis.get("title"),
        }.items()
        if value
    }


def sample_next_hyperparameters(task: TaskDefinition, store: ExperimentStore) -> dict:
    """Sample params using the current experiment history as search context."""
    experiment_history = list(store.experiments)
    sampling_constraints = getattr(task, "sampling_constraints", {}) or {}
    avoid_params = sampling_constraints.get("avoid_params", [])
    if isinstance(avoid_params, list):
        experiment_history.extend(
            {
                "params": params,
                "accepted": False,
                "error": "sampling_constraints.avoid_params",
            }
            for params in avoid_params
            if isinstance(params, dict)
        )
    return sample_hyperparameters(
        task.hyperparameter_space,
        experiment_history=experiment_history,
    )


# ─── Experiment Loop ──────────────────────────────────────────────────────────

def run_experiment_loop(
    task: TaskDefinition,
    workspace: Path,
    max_experiments: Optional[int] = None,
    max_duration_minutes: Optional[int] = None,
    experiment_duration_seconds: int = DEFAULT_EXPERIMENT_DURATION,
    verbose: bool = False,
) -> TaskResult:
    """Execute the full experiment loop with checkpoint and alert support."""
    max_experiments = max_experiments or task.budget.max_experiments
    max_duration_minutes = max_duration_minutes or task.budget.max_duration_minutes

    # ── Checkpoint: 检测任务是否已完成 ───────────────────────────────────────
    checkpoint_mgr = CheckpointManager(task.task_id)
    result_file = RESULTS_DIR / f"{task.task_id}.json"
    if result_file.exists():
        if verbose:
            print("[checkpoint] 任务已完成，直接返回历史结果")
        return read_result(task.task_id)

    # ── Checkpoint: 检测是否有可恢复的 checkpoint ──────────────────────────
    alert_mgr = AlertManager(task.task_id)

    if checkpoint_mgr.has_checkpoint(task.task_id):
        checkpoint_data = checkpoint_mgr.load_checkpoint(task.task_id)
        if checkpoint_data:
            completed_ids = set(checkpoint_data.get("completed_experiment_ids", []))
            last_exp_idx = checkpoint_data.get("last_experiment_index", -1)
            best_val = checkpoint_data.get("best_val")
            best_params = checkpoint_data.get("best_params")
            start_idx = last_exp_idx + 1
            if verbose:
                print(f"[checkpoint] 从 exp {start_idx + 1} 继续，已完成 {len(completed_ids)} 个实验")
        else:
            completed_ids = set()
            start_idx = 0
            best_val = None
            best_params = None
            checkpoint_mgr.save_task_definition(task)
    else:
        completed_ids = set()
        start_idx = 0
        best_val = None
        best_params = None
        checkpoint_mgr.save_task_definition(task)

    store = ExperimentStore(task_id=task.task_id, workdir=workspace, direction=task.metric.direction.value).load()
    reporter = ProgressReporter(task_id=task.task_id)
    reporter.init(max_experiments=max_experiments)

    minimize = task.metric.direction.value == "minimize"
    best_experiment_id: Optional[str] = None

    start_time = time.monotonic()

    if verbose:
        print(f"[autoresearch_run] Starting loop for task={task.task_id}")
        print(f"[autoresearch_run] max_experiments={max_experiments}, max_duration={max_duration_minutes}min")

    try:
        for exp_idx in range(start_idx, max_experiments):
            elapsed_seconds = time.monotonic() - start_time
            elapsed_minutes = elapsed_seconds / 60.0

            if elapsed_minutes > max_duration_minutes:
                if verbose:
                    print(f"[autoresearch_run] Time budget exceeded at {elapsed_minutes:.1f}min")
                # 触发超时告警
                alert_mgr.send_alert(
                    alert_type=AlertType.BUDGET_EXCEEDED,
                    message=f"时间预算 {max_duration_minutes}min 已耗尽，当前进度 {elapsed_minutes:.1f}min",
                    severity=AlertSeverity.LOW,
                    experiment_index=exp_idx + 1,
                    context={"max_duration_minutes": max_duration_minutes, "elapsed_minutes": elapsed_minutes},
                    recommended_action="如需继续，可增加 max_duration_minutes 或减少 max_experiments",
                )
                break

            experiment_id = f"exp-{exp_idx + 1:03d}"

            # 跳过已完成的实验（断点恢复）
            if experiment_id in completed_ids:
                if verbose:
                    print(f"[{experiment_id}] 跳过（已在存档中）")
                continue

            if verbose:
                print(f"\n[{experiment_id}] === Experiment {exp_idx + 1}/{max_experiments} ===")

            # 1. Sample hyperparameters
            try:
                params = sample_next_hyperparameters(task, store)
            except Exception as e:
                if verbose:
                    print(f"[{experiment_id}] Hyperparam sampling failed: {e} — skipping")
                store.add_experiment(
                    experiment_id=experiment_id, params={}, metrics={},
                    accepted=False, error=f"Hyperparam sampling failed: {e}",
                    **_experiment_lineage(task, exp_idx),
                )
                _save_checkpoint_after_exp(
                    checkpoint_mgr, task, store, workspace, experiment_id,
                    best_val, best_params, exp_idx, verbose,
                )
                continue

            # 2. Modify train.py
            try:
                modify_train_hyperparams(workspace / "train.py", params)
            except Exception as e:
                if verbose:
                    print(f"[{experiment_id}] Failed to modify train.py: {e} — skipping")
                store.add_experiment(
                    experiment_id=experiment_id, params=params, metrics={},
                    accepted=False, error=f"Failed to modify train.py: {e}",
                    **_experiment_lineage(task, exp_idx),
                )
                _save_checkpoint_after_exp(
                    checkpoint_mgr, task, store, workspace, experiment_id,
                    best_val, best_params, exp_idx, verbose,
                )
                continue

            # 3. Run training
            training_error = None
            try:
                metrics = run_training(
                    workspace=workspace,
                    experiment_id=experiment_id,
                    duration_seconds=experiment_duration_seconds,
                    data_path=task.dataset.path,
                    verbose=verbose,
                )
            except Exception as e:
                if verbose:
                    print(f"[{experiment_id}] Training failed: {e}")
                training_error = str(e)
                metrics = {}
                # 触发崩溃告警
                alert_mgr.send_alert(
                    alert_type=AlertType.TASK_CRASH,
                    message=f"训练崩溃: {training_error}",
                    severity=AlertSeverity.HIGH,
                    experiment_index=exp_idx + 1,
                    context={"experiment_id": experiment_id, "error": training_error},
                    recommended_action="检查 train.py 是否有语法错误或运行时异常，或减小超参数",
                )

            # 4. Snapshot code
            try:
                snapshot_code(task.task_id, experiment_id, workspace)
            except Exception as e:
                if verbose:
                    print(f"[{experiment_id}] Snapshot failed: {e} (non-fatal)")

            # 5. Get current metric value
            metric_name = task.metric.name
            current_val = select_metric_value(metrics, metric_name)

            # 6. Accept/Reject decision
            accepted = False
            if current_val is not None:
                if best_val is None:
                    accepted = True
                elif minimize:
                    accepted = current_val < best_val
                else:
                    accepted = current_val > best_val

            # 7. Update best
            if accepted:
                best_val = current_val
                best_params = params
                best_experiment_id = experiment_id

            # 8. Record experiment
            store.add_experiment(
                experiment_id=experiment_id,
                params=params,
                metrics=metrics,
                accepted=accepted,
                duration_seconds=metrics.get("actual_duration_seconds"),
                error=training_error,
                **_experiment_lineage(task, exp_idx),
            )

            # 9. Report progress
            reporter.report(
                experiment_index=exp_idx + 1,
                best_val=best_val,
                best_params=best_params,
                best_experiment_id=best_experiment_id,
                last_accepted=accepted,
                last_val=current_val,
                elapsed_minutes=elapsed_minutes,
                experiment_id=experiment_id,
            )

            # 10. Doom loop detection → 告警
            if reporter._stuck_streak >= reporter.DOOM_LOOP_THRESHOLD:
                recent_exp_ids = reporter._recent_experiments[-reporter.DOOM_LOOP_THRESHOLD:]
                if all(not accepted for _, accepted in recent_exp_ids):
                    exp_ids = [eid for eid, _ in recent_exp_ids]
                    alert_mgr.send_alert(
                        alert_type=AlertType.DOOM_LOOP,
                        message=(
                            f"连续 {reporter.DOOM_LOOP_THRESHOLD} 次实验被拒绝，"
                            f"搜索可能陷入局部最优或参数空间不当。"
                            f"最近实验: {exp_ids}。"
                        ),
                        severity=AlertSeverity.HIGH,
                        experiment_index=exp_idx + 1,
                        context={
                            "stuck_streak": reporter._stuck_streak,
                            "recent_experiment_ids": exp_ids,
                            "best_val": best_val,
                            "best_params": best_params,
                        },
                        recommended_action=(
                            "建议：1) 扩大超参数搜索范围；"
                            "2) 增加 experiment_duration_seconds；"
                            "3) 调整 base train.py 的初始化策略。"
                        ),
                    )
                    if verbose:
                        print("[ALERT] doom_loop detected — stopping search")
                    break

            # 11. Save checkpoint after each experiment
            is_new_best = (
                best_val is not None
                and store.best_val is not None
                and store.best_val == best_val
            )
            checkpoint_mgr.save_checkpoint(
                experiment_id=experiment_id,
                experiments_json=store.to_dict(),
                workdir=workspace,
                is_new_best=is_new_best,
                best_val=best_val,
                best_params=best_params,
            )

    except KeyboardInterrupt:
        if verbose:
            print("[autoresearch_run] Interrupted by user")
        status = TaskStatus.FAILED
        error_msg = "Interrupted by user"
    except Exception as e:
        if verbose:
            print(f"[autoresearch_run] Unexpected error: {e}")
        status = TaskStatus.FAILED
        error_msg = str(e)
    else:
        status = TaskStatus.COMPLETED
        error_msg = None

    # ─── Write final result ───────────────────────────────────────────────────

    total_duration_minutes = (time.monotonic() - start_time) / 60.0

    best_result_dict = None
    if best_experiment_id is not None:
        best_result_dict = {
            "experiment_id": best_experiment_id,
            "val": best_val,
            "params": best_params,
        }

    result = TaskResult(
        task_id=task.task_id,
        status=status,
        best_result=best_result_dict,
        experiments=store.experiments,
        summary=build_result_summary(store.experiments, total_duration_minutes),
        research_context=task.research_context,
        hypotheses=task.hypotheses,
        finished_at=now_iso(),
        error=error_msg,
    )

    write_result(result)
    reporter.complete(best_val=best_val, best_params=best_params)

    if verbose:
        print(f"\n[autoresearch_run] Loop finished. Status={status.value}")
        print(f"[autoresearch_run] Best: {best_val} with {best_params}")

    return result


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()

    # Load task definition
    task_config_path = Path(args.task_config)
    if not task_config_path.exists():
        print(f"ERROR: Task config not found: {task_config_path}", file=sys.stderr)
        return 1

    try:
        task_def = read_task(task_config_path.stem)
    except Exception:
        task_def_data = json.loads(task_config_path.read_text(encoding="utf-8"))
        task_def = TaskDefinition.from_dict(task_def_data)

    task_id = task_def.task_id

    # Determine workspace
    if args.workspace:
        workspace = Path(args.workspace)
    else:
        workspace = WORKSPACE_ROOT / "workdir" / task_id
    workspace.mkdir(parents=True, exist_ok=True)

    # Setup workdir
    setup_workdir(task_def, workspace)

    # Run experiment loop
    result = run_experiment_loop(
        task=task_def,
        workspace=workspace,
        max_experiments=args.max_experiments,
        max_duration_minutes=args.max_duration,
        experiment_duration_seconds=args.experiment_duration,
        verbose=args.verbose,
    )

    # Output results
    result_file = RESULTS_DIR / f"{task_id}.json"
    print(f"RESULT_FILE={result_file}", file=sys.stdout)
    print(f"STATUS={result.status.value}", file=sys.stdout)
    if result.best_result:
        print(f"BEST_VAL={result.best_result.get('val')}", file=sys.stdout)
    print(f"EXPERIMENTS={len(result.experiments)}", file=sys.stdout)

    return 0 if result.status == TaskStatus.COMPLETED else 1


if __name__ == "__main__":
    sys.exit(main())
