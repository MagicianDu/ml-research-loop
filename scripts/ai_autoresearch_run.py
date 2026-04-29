#!/usr/bin/env python3
# scripts/ai_autoresearch_run.py
"""
AI-driven autoresearch experiment loop.

Usage:
    python scripts/ai_autoresearch_run.py --task-config tasks/<task_id>.json

This script:
1. Loads the task definition
2. Sets up workdir (train.py, prepare.py, program.md)
3. Runs AI-driven experiment loop: analyze → propose → execute → train → evaluate
4. Uses LLM (MiniMax or Mock) to propose meaningful changes instead of random sampling

Unlike autoresearch_run.py which uses random sampling, this uses:
- ResearchAnalyzer: analyzes train.py + history + trends
- ChangeProposer: calls LLM to propose specific changes
- ChangeExecutor: applies changes to train.py with validation
"""

from __future__ import annotations

import argparse
import os
import re
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
from lib.llm_providers import LLMProvider, MiniMaxProvider, MockLLMProvider, OpenAIProvider
from lib.metrics import select_metric_value
from lib.result_summary import build_result_summary
from lib.runtime import resolve_python_executable
from lib.research_components import (
    ResearchAnalyzer,
    ChangeProposer,
    ChangeExecutor,
    ExecutionResult,
)
from scripts.generate_program_md import generate_program_md


# ─── Constants ────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent.parent.resolve()

SEARCH_REGION_START = "# ======= AUTORESEARCH SEARCH REGION START ======="
SEARCH_REGION_END = "# ======= AUTORESEARCH SEARCH REGION END ======="
DEFAULT_EXPERIMENT_DURATION = 300

METRIC_PREFIXES = ("val_", "metric_", "loss_", "bpb", "ppl", "acc", "f1", "precision", "recall")

MAX_LLM_CALLS_PER_EXPERIMENT = 3


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI-driven autoresearch experiment loop",
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
    parser.add_argument("--verbose", action="store_true",
                        help="Print verbose progress")
    parser.add_argument("--mock", action="store_true",
                        help="Use MockLLMProvider instead of real LLM")
    parser.add_argument("--mock-response", type=str, default=None,
                        help="JSON string for mock LLM response")
    parser.add_argument("--llm-provider", choices=["minimax", "openai"], default="minimax",
                        help="Server-side LLM provider for non-mock mode")
    parser.add_argument("--llm-model", type=str, default=None,
                        help="Optional model name for the selected LLM provider")
    return parser.parse_args()


def build_llm_provider(args: argparse.Namespace) -> LLMProvider:
    """Build the configured LLM provider without making an API call."""
    if args.mock:
        mock_response = {
            "change_type": "hyperparam",
            "target": "DEPTH",
            "current_value": "4",
            "proposed_value": "10",
            "reason": "depth 越大性能越好",
            "confidence": 0.9,
        }
        if args.mock_response:
            mock_response = json.loads(args.mock_response)
        return MockLLMProvider(mock_response)

    if args.llm_provider == "openai":
        return OpenAIProvider(model=args.llm_model or OpenAIProvider.MODEL)

    return MiniMaxProvider(model=args.llm_model or MiniMaxProvider.MODEL)


# ─── Workdir Setup ────────────────────────────────────────────────────────────

def setup_workdir(task: TaskDefinition, workspace: Path) -> None:
    """Initialize workdir: copy train_base.py, symlink prepare.py, generate program.md."""
    workspace.mkdir(parents=True, exist_ok=True)

    base_train = _ROOT / "base" / "train_base.py"
    if not base_train.exists():
        raise FileNotFoundError(f"Base train template not found: {base_train}")
    shutil.copy2(base_train, workspace / "train.py")

    base_prepare = _ROOT / "base" / "prepare.py"
    prepare_link = workspace / "prepare.py"
    if not prepare_link.exists():
        if base_prepare.exists():
            os.symlink(base_prepare.resolve(), prepare_link)

    program_content = generate_program_md(task)
    (workspace / "program.md").write_text(program_content, encoding="utf-8")


# ─── Training Execution ───────────────────────────────────────────────────────

def run_training(
    workspace: Path,
    experiment_id: str,
    duration_seconds: int,
    verbose: bool = False,
) -> dict:
    """Run train.py and parse metrics from stdout."""
    log_file = workspace / "logs" / f"{experiment_id}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        resolve_python_executable(_ROOT),
        "train.py",
    ]
    env = {**os.environ, "AUTORESEARCH_EXP_ID": experiment_id}

    if verbose:
        print(f"[{experiment_id}] Starting: {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd, cwd=str(workspace), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
    except Exception as e:
        raise TrainingFailedError(f"Failed to start train.py: {e}") from e

    start_time = time.monotonic()
    timed_out = False
    try:
        stdout, _ = proc.communicate(timeout=duration_seconds)
        actual_duration = time.monotonic() - start_time
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, _ = proc.communicate()
        actual_duration = duration_seconds
        timed_out = True
        if verbose:
            print(f"[{experiment_id}] Timeout after {actual_duration:.1f}s — killed")

    log_file.write_text(stdout, encoding="utf-8")
    if timed_out:
        raise TrainingFailedError(f"train.py timed out after {actual_duration:.1f}s")
    if proc.returncode:
        raise TrainingFailedError(
            f"train.py exited with exit code {proc.returncode}. See log: {log_file}"
        )

    metrics = parse_training_output(stdout)
    metrics["actual_duration_seconds"] = actual_duration

    if verbose:
        val = metrics.get("val_bpb", metrics.get("val", "N/A"))
        print(f"[{experiment_id}] Done in {actual_duration:.1f}s — val={val}")

    return metrics


def parse_training_output(stdout: str) -> dict:
    """Parse validation metrics from training stdout."""
    metrics = {}

    for line in stdout.splitlines():
        line = line.strip()
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


# ─── Checkpoint Helper ────────────────────────────────────────────────────────

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
    """Save checkpoint after a failed/skipped experiment."""
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


# ─── AI Experiment Loop ────────────────────────────────────────────────────────

def run_ai_experiment_loop(
    task: TaskDefinition,
    workspace: Path,
    max_experiments: Optional[int],
    max_duration_minutes: Optional[int],
    experiment_duration_seconds: int,
    llm_provider: LLMProvider,
    verbose: bool = False,
) -> TaskResult:
    """
    AI-driven experiment loop: analyze → propose → execute → train → evaluate.

    Replaces random sampling with:
    - ResearchAnalyzer: reads train.py + experiments.json
    - ChangeProposer: calls LLM to get change proposal
    - ChangeExecutor: applies change to train.py
    """
    max_experiments = max_experiments or task.budget.max_experiments
    max_duration_minutes = max_duration_minutes or task.budget.max_duration_minutes

    # ── Checkpoint: 检测任务是否已完成 ──────────────────────────────────────
    checkpoint_mgr = CheckpointManager(task.task_id)
    result_file = RESULTS_DIR / f"{task.task_id}.json"
    if result_file.exists():
        if verbose:
            print("[checkpoint] 任务已完成，直接返回历史结果")
        return read_result(task.task_id)

    # ── Checkpoint: 检测是否有可恢复的 checkpoint ─────────────────────────
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

    # ── Initialize AI components ─────────────────────────────────────────────
    analyzer = ResearchAnalyzer(workspace, task.task_id)
    proposer = ChangeProposer(
        llm_provider,
        metric_name=task.metric.name,
        metric_direction=task.metric.direction.value,
    )
    executor = ChangeExecutor(workspace)

    store = ExperimentStore(
        task_id=task.task_id,
        workdir=workspace,
        direction=task.metric.direction.value
    ).load()

    reporter = ProgressReporter(task_id=task.task_id)
    reporter.init(max_experiments=max_experiments)

    minimize = task.metric.direction.value == "minimize"
    best_experiment_id: Optional[str] = None

    start_time = time.monotonic()

    if verbose:
        print(f"[ai_autoresearch_run] Starting AI loop for task={task.task_id}")
        print(f"[ai_autoresearch_run] max_experiments={max_experiments}, max_duration={max_duration_minutes}min")
        print(f"[ai_autoresearch_run] LLM provider: {llm_provider.name}")

    try:
        for exp_idx in range(start_idx, max_experiments):
            elapsed_seconds = time.monotonic() - start_time
            elapsed_minutes = elapsed_seconds / 60.0

            if elapsed_minutes > max_duration_minutes:
                if verbose:
                    print(f"[ai_autoresearch_run] Time budget exceeded at {elapsed_minutes:.1f}min")
                alert_mgr.send_alert(
                    alert_type=AlertType.BUDGET_EXCEEDED,
                    message=f"时间预算 {max_duration_minutes}min 已耗尽",
                    severity=AlertSeverity.LOW,
                    experiment_index=exp_idx + 1,
                    context={"max_duration_minutes": max_duration_minutes, "elapsed_minutes": elapsed_minutes},
                    recommended_action="如需继续，可增加 max_duration_minutes",
                )
                break

            experiment_id = f"exp-{exp_idx + 1:03d}"

            if experiment_id in completed_ids:
                if verbose:
                    print(f"[{experiment_id}] 跳过（已在存档中）")
                continue

            if verbose:
                print(f"\n[{experiment_id}] === AI Experiment {exp_idx + 1}/{max_experiments} ===")

            # ── Phase 1: Analyze ────────────────────────────────────────────
            if verbose:
                print(f"[{experiment_id}] [Phase 1/5] Analyzing context...")

            try:
                analyze_result = analyzer.analyze()
                if verbose:
                    print(f"[{experiment_id}] Analysis complete. Focus: {analyze_result.focus_suggestion[:80]}...")
            except Exception as e:
                if verbose:
                    print(f"[{experiment_id}] Analysis failed: {e} — skipping experiment")
                store.add_experiment(
                    experiment_id=experiment_id,
                    params={},
                    metrics={},
                    accepted=False,
                    error=f"Analysis failed: {e}",
                )
                _save_checkpoint_after_exp(
                    checkpoint_mgr, task, store, workspace, experiment_id,
                    best_val, best_params, exp_idx, verbose,
                )
                continue

            # ── Phase 2: Propose (LLM) ─────────────────────────────────────
            if verbose:
                print(f"[{experiment_id}] [Phase 2/5] Proposing change with LLM...")

            proposal = None
            for attempt in range(MAX_LLM_CALLS_PER_EXPERIMENT):
                try:
                    proposal = proposer.propose(analyze_result, attempt=attempt)
                    if proposal and proposal.confidence >= 0.4:
                        break
                except Exception as e:
                    if verbose:
                        print(f"[{experiment_id}] LLM attempt {attempt + 1} failed: {e}")

            if not proposal:
                if verbose:
                    print(f"[{experiment_id}] LLM proposal failed, using random fallback")
                # Fallback: record failure but continue
                store.add_experiment(
                    experiment_id=experiment_id,
                    params={},
                    metrics={},
                    accepted=False,
                    error="LLM proposal failed after all attempts",
                )
                _save_checkpoint_after_exp(
                    checkpoint_mgr, task, store, workspace, experiment_id,
                    best_val, best_params, exp_idx, verbose,
                )
                continue

            if verbose:
                print(f"[{experiment_id}] Proposed: {proposal.change_type} {proposal.target} "
                      f"{proposal.current_value}→{proposal.proposed_value} "
                      f"(confidence={proposal.confidence:.2f}, reason: {proposal.reason[:60]}...)")

            # ── Phase 3: Execute ─────────────────────────────────────────────
            if verbose:
                print(f"[{experiment_id}] [Phase 3/5] Executing change...")

            try:
                exec_result = executor.execute(proposal)
            except Exception as e:
                if verbose:
                    print(f"[{experiment_id}] Execute failed: {e}")
                exec_result = ExecutionResult(
                    success=False,
                    error=str(e),
                    rollback=False,
                )

            if not exec_result.success:
                if verbose:
                    print(f"[{experiment_id}] Execute failed: {exec_result.error} — skipping experiment")
                store.add_experiment(
                    experiment_id=experiment_id,
                    params={proposal.target: proposal.proposed_value},
                    metrics={},
                    accepted=False,
                    error=f"Execute failed: {exec_result.error}",
                )
                _save_checkpoint_after_exp(
                    checkpoint_mgr, task, store, workspace, experiment_id,
                    best_val, best_params, exp_idx, verbose,
                )
                continue

            if verbose:
                cr = exec_result.change_record
                print(f"[{experiment_id}] Applied change: {cr['target']}={cr['from']}→{cr['to']}")

            # ── Phase 4: Train ───────────────────────────────────────────────
            if verbose:
                print(f"[{experiment_id}] [Phase 4/5] Running training...")

            training_error = None
            try:
                metrics = run_training(
                    workspace=workspace,
                    experiment_id=experiment_id,
                    duration_seconds=experiment_duration_seconds,
                    verbose=verbose,
                )
            except Exception as e:
                if verbose:
                    print(f"[{experiment_id}] Training failed: {e}")
                training_error = str(e)
                metrics = {}
                alert_mgr.send_alert(
                    alert_type=AlertType.TASK_CRASH,
                    message=f"训练崩溃: {training_error}",
                    severity=AlertSeverity.HIGH,
                    experiment_index=exp_idx + 1,
                    context={"experiment_id": experiment_id, "error": training_error},
                    recommended_action="检查 train.py 是否有语法错误或运行时异常",
                )

            # ── Phase 5: Snapshot ────────────────────────────────────────────
            try:
                snapshot_code(task.task_id, experiment_id, workspace)
            except Exception as e:
                if verbose:
                    print(f"[{experiment_id}] Snapshot failed: {e} (non-fatal)")

            # ── Phase 6: Evaluate ──────────────────────────────────────────
            if verbose:
                print(f"[{experiment_id}] [Phase 5/5] Evaluating...")

            metric_name = task.metric.name
            current_val = select_metric_value(metrics, metric_name)

            accepted = False
            if current_val is not None:
                if best_val is None:
                    accepted = True
                elif minimize:
                    accepted = current_val < best_val
                else:
                    accepted = current_val > best_val

            if accepted:
                best_val = current_val
                best_params = {proposal.target: proposal.proposed_value}
                best_experiment_id = experiment_id

            # ── Record experiment ───────────────────────────────────────────
            store.add_experiment(
                experiment_id=experiment_id,
                params={proposal.target: proposal.proposed_value},
                metrics=metrics,
                accepted=accepted,
                duration_seconds=metrics.get("actual_duration_seconds"),
                error=training_error,
                change_record=exec_result.change_record,
                llm_info={
                    "model": llm_provider.name,
                    "proposal_attempts": len(proposer.proposal_history),
                    "proposal": {
                        "change_type": proposal.change_type,
                        "target": proposal.target,
                        "current_value": proposal.current_value,
                        "proposed_value": proposal.proposed_value,
                        "reason": proposal.reason,
                        "confidence": proposal.confidence,
                    } if proposal else None,
                },
            )

            # ── Report progress ────────────────────────────────────────────
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

            # ── Doom loop detection ─────────────────────────────────────────
            if reporter._stuck_streak >= reporter.DOOM_LOOP_THRESHOLD:
                recent_exp_ids = reporter._recent_experiments[-reporter.DOOM_LOOP_THRESHOLD:]
                if all(not accepted for _, accepted in recent_exp_ids):
                    exp_ids = [eid for eid, _ in recent_exp_ids]
                    alert_mgr.send_alert(
                        alert_type=AlertType.DOOM_LOOP,
                        message=(
                            f"连续 {reporter.DOOM_LOOP_THRESHOLD} 次实验被拒绝，"
                            f"搜索可能陷入局部最优或参数空间不当。"
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

            # ── Save checkpoint ─────────────────────────────────────────────
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
            print("[ai_autoresearch_run] Interrupted by user")
        status = TaskStatus.FAILED
        error_msg = "Interrupted by user"
    except Exception as e:
        if verbose:
            print(f"[ai_autoresearch_run] Unexpected error: {e}")
        status = TaskStatus.FAILED
        error_msg = str(e)
    else:
        status = TaskStatus.COMPLETED
        error_msg = None

    # ── Write final result ───────────────────────────────────────────────────

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
        print(f"\n[ai_autoresearch_run] Loop finished. Status={status.value}")
        print(f"[ai_autoresearch_run] Best: {best_val} with {best_params}")

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

    # Setup LLM provider
    llm_provider = build_llm_provider(args)

    # Run AI experiment loop
    result = run_ai_experiment_loop(
        task=task_def,
        workspace=workspace,
        max_experiments=args.max_experiments,
        max_duration_minutes=args.max_duration,
        experiment_duration_seconds=args.experiment_duration,
        llm_provider=llm_provider,
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
