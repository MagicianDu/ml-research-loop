# Phase 3 — 生产级可靠性方案

> **角色**：Architect（架构师）
> **日期**：2026-04-27
> **背景**：Phase 1 完成 ml-intern 集成，Phase 3 解决生产级可靠性的四个核心问题：checkpoint、多任务并发、异常恢复、告警机制

---

## 0. 现状分析

### 0.1 当前架构

```
autoresearch_run.py（单实例脚本）
├── ExperimentStore      → workdir/experiments.json（实验记录）
├── ProgressReporter     → results/<task_id>-progress.json（实时进度）
├── snapshot_code()      → snapshots/<task_id>/<exp_id>/（train.py 快照）
└── run_training()       → 执行 train.py，解析 metrics
```

### 0.2 当前问题清单

| 问题 | 现状 | 影响 |
|------|------|------|
| Checkpoint 不完整 | 只快照 train.py，无 model.pt | 模型权重丢失 |
| kill -9 无法恢复 | 无进程状态持久化 | 训练中途被 kill 后全部重来 |
| 单实例运行 | autoresearch_run.py 只能单跑一个 task | 多个实验任务需排队 |
| 无告警机制 | doom_loop_warning 字段写了但无人知晓 | 连续失败无法及时通知 |
| 无并发控制 | sessions_spawn 无数量限制 | 机器资源被打满 |

---

## 1. Checkpoint 设计

### 1.1 三层 Checkpoint 架构

```
checkpoints/<task_id>/
├── task_definition.json      # 任务定义快照（只读存档）
├── experiments.json          # 实验记录（与 workdir 同步）
├── best/
│   ├── model.pt              # 最佳模型权重（由 train.py 输出）
│   ├── train.py              # 最佳超参对应的 train.py
│   └── metadata.json          # best 模型元信息
└── runs/
    ├── run-001/
    │   ├── experiments.json   # 该轮次的实验记录
    │   └── model.pt           # （如有）
    └── run-002/
```

**说明**：
- `checkpoints/<task_id>/` 是任务的检查点根目录
- 每次进入 `run_experiment_loop()` 前，先检查是否存在 checkpoint，决定是从头开始还是续跑
- `best/model.pt` 由 train.py 训练结束时显式保存（需要改造 train.py）

### 1.2 Checkpoint 存档内容

| 文件 | 来源 | 存档时机 | 说明 |
|------|------|----------|------|
| `task_definition.json` | tasks/<task_id>.json | 任务启动时 | 只读，标识任务身份 |
| `experiments.json` | workdir/experiments.json | 每次实验结束后 | ExperimentStore 自动持久化 |
| `best/model.pt` | train.py 输出 | 每次新最佳模型出现时 | 需要 train.py 支持 torch.save |
| `best/train.py` | workdir/train.py | 每次新最佳模型出现时 | 保存产生最佳结果的代码 |
| `train.py` | workdir/train.py | 每次实验结束后 | 通用存档，不依赖是否最佳 |

**关键实现：train.py 必须输出 model.pt**

在 `train.py` 的 SEARCH REGION 或训练结束位置添加：

```python
# 在训练结束时（early-stop 或完成全部 epoch）
import os, torch
model_path = os.path.join(os.environ.get("OUTPUT_DIR", "."), "model.pt")
torch.save(model.state_dict(), model_path)
print(f"[RESULT] model_saved={model_path}")
```

### 1.3 存档时机

```
每次实验结束后（ExperimentStore.add_experiment() 之后）:
    │
    ├─► 1. ExperimentStore.save()       → experiments.json（已有）
    │
    ├─► 2. 若本次是新的 best_val:
    │       ├─► copy(workdir/train.py, checkpoints/best/train.py)
    │       ├─► if model.pt exists: copy(checkpoints/best/model.pt)
    │       └─► write(best/metadata.json, {...})
    │
    └─► 3. checkpoint_manager.save_checkpoint()
              ├─► copy task_definition.json
              ├─► copy experiments.json
              └─► write checkpoint_manifest.json（包含存档时间、run_id）
```

### 1.4 恢复流程

```python
def run_experiment_loop_with_checkpoint(task, workspace, ...):
    checkpoint_root = CHECKPOINTS_DIR / task.task_id

    # ── 检测点 1：任务是否已完全完成 ──────────────────────────────
    result_file = RESULTS_DIR / f"{task.task_id}.json"
    if result_file.exists():
        print(f"[checkpoint] 任务已完成，直接返回历史结果")
        return read_result(task.task_id)

    # ── 检测点 2：是否有可恢复的 checkpoint ──────────────────────
    checkpoint_manifest = checkpoint_root / "checkpoint_manifest.json"
    if checkpoint_manifest.exists():
        manifest = json.loads(checkpoint_manifest.read_text())
        completed_experiments = manifest.get("completed_experiment_ids", [])
        last_experiment_index = manifest.get("last_experiment_index", -1)
        best_val_so_far = manifest.get("best_val")
        best_params_so_far = manifest.get("best_params")
        print(f"[checkpoint] 找到存档，将从 exp {last_experiment_index + 1} 继续"
              f"（已完成 {len(completed_experiments)} 个实验）")
    else:
        completed_experiments = []
        last_experiment_index = -1
        best_val_so_far = None
        best_params_so_far = None

    # ── 恢复 best 模型权重（如果有）────────────────────────────────
    best_model_path = checkpoint_root / "best" / "model.pt"
    if best_model_path.exists():
        # 将 model.pt 链接到当前 workdir，供 train.py 加载
        pass  # 取决于 train.py 是否支持 resume

    # ── 从断点继续实验循环 ───────────────────────────────────────
    for exp_idx in range(last_experiment_index + 1, max_experiments):
        experiment_id = f"exp-{exp_idx + 1:03d}"
        if experiment_id in completed_experiments:
            continue  # 跳过已完成的实验

        # ... 正常执行实验 ...
        # 每次实验结束后调用 checkpoint_manager.save_checkpoint()
```

### 1.5 CheckpointManager 核心接口

```python
# lib/checkpoint_manager.py

CHECKPOINTS_DIR = WORKSPACE_ROOT / "checkpoints"

class CheckpointManager:
    """管理任务级别的 checkpoint 存档与恢复。"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.checkpoint_root = CHECKPOINTS_DIR / task_id
        self.best_dir = self.checkpoint_root / "best"
        self.runs_dir = self.checkpoint_root / "runs"

    # ── 存档 ────────────────────────────────────────────────────

    def save_checkpoint(
        self,
        experiment_id: str,
        experiments_json: dict,
        workdir: Path,
        is_new_best: bool = False,
        best_val: Optional[float] = None,
        best_params: Optional[dict] = None,
    ) -> None:
        """
        每次实验结束后调用，保存 checkpoint。

        Args:
            experiment_id: 当前实验 ID（如 exp-003）
            experiments_json: ExperimentStore 序列化的 dict
            workdir: 当前 workdir 路径
            is_new_best: 本次是否产生了新的最佳模型
            best_val: 当前最佳指标值
            best_params: 当前最佳超参
        """
        # 1. 保存 experiments.json 快照
        run_dir = self.runs_dir / f"run-{self._next_run_id()}"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "experiments.json").write_text(
            json.dumps(experiments_json, indent=2), encoding="utf-8"
        )

        # 2. 保存当前 train.py（通用存档）
        train_py = workdir / "train.py"
        if train_py.exists():
            shutil.copy2(train_py, run_dir / "train.py")

        # 3. 若本次是新的 best，存档 best 模型
        if is_new_best and best_val is not None:
            self.best_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(train_py, self.best_dir / "train.py")

            model_pt = workdir / "model.pt"
            if model_pt.exists():
                shutil.copy2(model_pt, self.best_dir / "model.pt")

            # 写入 best 元信息
            (self.best_dir / "metadata.json").write_text(
                json.dumps({
                    "experiment_id": experiment_id,
                    "best_val": best_val,
                    "best_params": best_params,
                    "saved_at": now_iso(),
                }, indent=2), encoding="utf-8"
            )

        # 4. 更新 checkpoint manifest
        self._update_manifest(
            experiment_id=experiment_id,
            completed_experiments=self._get_completed_ids(run_dir),
            best_val=best_val,
            best_params=best_params,
        )

    def save_task_definition(self, task_def: TaskDefinition) -> None:
        """存档任务定义（任务启动时调用）。"""
        self.checkpoint_root.mkdir(parents=True, exist_ok=True)
        (self.checkpoint_root / "task_definition.json").write_text(
            json.dumps(task_def.to_dict(), indent=2, encoding="utf-8"),
            encoding="utf-8",
        )

    # ── 恢复 ────────────────────────────────────────────────────

    def get_latest_checkpoint(self) -> Optional[dict]:
        """返回最新 checkpoint 的 manifest，无存档则返回 None。"""
        manifest_path = self.checkpoint_root / "checkpoint_manifest.json"
        if not manifest_path.exists():
            return None
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def get_best_model_path(self) -> Optional[Path]:
        """返回最佳模型路径，无则返回 None。"""
        p = self.best_dir / "model.pt"
        return p if p.exists() else None

    # ── 辅助 ────────────────────────────────────────────────────

    def _next_run_id(self) -> str:
        """返回下一个 run 目录编号。"""
        if not self.runs_dir.exists():
            return "001"
        existing = sorted(self.runs_dir.iterdir())
        if not existing:
            return "001"
        last = existing[-1].name  # e.g. "run-003"
        num = int(last.split("-")[1]) + 1
        return f"{num:03d}"

    def _update_manifest(self, ...) -> None:
        """原子上写 checkpoint_manifest.json。"""
        ...

    def _get_completed_ids(self, run_dir: Path) -> list[str]:
        """从 experiments.json 中提取已完成 experiment_id 列表。"""
        ...
```

---

## 2. 多任务并发设计

### 2.1 目标

- 支持同时运行多个独立的 AutoResearch 任务
- 每个任务拥有独立 workdir
- 全局限制并发数量（`max_concurrent_tasks`），保护机器资源

### 2.2 架构图

```
┌──────────────────────────────────────────────────────────────────────┐
│                      AutoResearchManager                             │
│                                                                      │
│   launch(config) ───────────────────────────────────────────────┐  │
│   ┌──────────────────────────────────────────────────────────┐  │  │
│   │  1. Check active_tasks count < max_concurrent_tasks      │  │  │
│   │  2. 创建独立 workdir: workdir/<task_id>/                 │  │  │
│   │  3. setup_workdir()（复制 train_base.py 等）             │  │  │
│   │  4. CheckpointManager.save_task_definition()              │  │  │
│   │  5. sessions_spawn(sub-agent)                            │  │  │
│   │  6. 注册到 active_tasks                                  │  │  │
│   └──────────────────────────────────────────────────────────┘  │  │
│   get_status(task_id) ────────────────────────────────────────┐  │  │
│   get_result(task_id)  ──────────────────────────────────────┤  │  │
│   cancel(task_id)      ──────────────────────────────────────┤  │  │
│   list_active_tasks() ───────────────────────────────────────┤  │  │
│   wait_all()           ──────────────────────────────────────┘  │  │
│                                                                      │
│   active_tasks: dict[str, ActiveTaskInfo]                           │
│   max_concurrent_tasks: int（默认 2）                                │
└──────────────────────────────────────────────────────────────────────┘
         │
         │ sessions_spawn (per task)
         ▼
   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
   │ Sub-Agent Task1 │    │ Sub-Agent Task2 │    │ Sub-Agent ...   │
   │ workdir/task_1/ │    │ workdir/task_2/ │    │ workdir/task_N/ │
   └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
            │                      │                      │
            ▼                      ▼                      ▼
   results/task_1.json      results/task_2.json      results/task_N.json
   checkpoints/task_1/      checkpoints/task_2/      checkpoints/task_N/
```

### 2.3 AutoResearchManager 并发改造

```python
@dataclass
class ActiveTaskInfo:
    task_id: str
    config: AutoResearchConfig
    session_key: str
    launched_at: float
    workdir: Path
    checkpoint_manager: CheckpointManager


class AutoResearchManager:
    def __init__(
        self,
        workspace_root: Path = WORKSPACE_ROOT,
        max_concurrent_tasks: int = 2,
    ):
        self.workspace = workspace_root
        self.max_concurrent_tasks = max_concurrent_tasks
        self.active_tasks: dict[str, ActiveTaskInfo] = {}

    def launch(self, config: AutoResearchConfig) -> str:
        # ── 并发数量检查 ────────────────────────────────────────
        if len(self.active_tasks) >= self.max_concurrent_tasks:
            raise RuntimeError(
                f"并发上限已达（{self.max_concurrent_tasks}）。"
                f"当前活跃任务: {list(self.active_tasks.keys())}。"
                f"请等待任务完成后重试。"
            )

        task_id = config.task_id

        # ── 为任务创建独立 workdir ───────────────────────────────
        workdir = self.workspace / "workdir" / task_id
        workdir.mkdir(parents=True, exist_ok=True)

        # ── 设置 workdir（复制 train_base.py 等）─────────────────
        # 调用 setup_workdir()（见 autoresearch_run.py）
        from scripts.autoresearch_run import setup_workdir
        task_def = self._build_task_definition(config)
        setup_workdir(task_def, workdir)

        # ── 初始化 CheckpointManager 并存档任务定义 ──────────────
        checkpoint_mgr = CheckpointManager(task_id)
        checkpoint_mgr.save_task_definition(task_def)

        # ── 写入 tasks/<task_id>.json ───────────────────────────
        write_task(task_def)

        # ── 获取任务锁 ──────────────────────────────────────────
        lock_path = acquire_task_lock(task_id)

        # ── Spawn sub-agent ────────────────────────────────────
        session_info = _spawn_autoresearch_subagent(task_id, workdir)
        session_key = session_info["session_key"]

        # ── 注册活跃任务 ─────────────────────────────────────────
        self.active_tasks[task_id] = ActiveTaskInfo(
            task_id=task_id,
            config=config,
            session_key=session_key,
            launched_at=time.time(),
            workdir=workdir,
            checkpoint_manager=checkpoint_mgr,
        )

        return task_id

    def get_status(self, task_id: str) -> dict:
        """Get status — 优先从 CheckpointManager 读取。"""
        # 1. 查 CheckpointManager（磁盘数据，最可靠）
        cp = CheckpointManager(task_id)
        latest = cp.get_latest_checkpoint()
        if latest:
            return {**latest, "source": "checkpoint"}

        # 2. 查 ProgressReporter（实时进度）
        try:
            return {**read_progress(task_id), "source": "progress"}
        except FileNotFoundError:
            pass

        # 3. 查 active_tasks（内存数据）
        if task_id in self.active_tasks:
            return {"task_id": task_id, "status": "running", "source": "memory"}

        return {"task_id": task_id, "status": "unknown"}

    def on_task_complete(self, task_id: str) -> None:
        """Sub-agent 或 wait_for_completion 完成后调用，清理活跃记录。"""
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]

    def list_active_tasks(self) -> list[dict]:
        """返回所有活跃任务的状态概览。"""
        return [
            {
                "task_id": info.task_id,
                "session_key": info.session_key,
                "elapsed_seconds": time.time() - info.launched_at,
                "workdir": str(info.workdir),
            }
            for info in self.active_tasks.values()
        ]
```

### 2.4 并发限制机制

| 策略 | 实现 | 说明 |
|------|------|------|
| 硬上限 | `max_concurrent_tasks` | 超过则 `launch()` 抛出 `RuntimeError` |
| 软上限（推荐） | 任务队列 | `launch()` 时若已达上限，加入队列而不是报错 |
| 资源感知 | 可监控 CPU/内存 | Phase 4 扩展方向 |

**软上限实现（任务队列）**：

```python
from collections import deque
from dataclasses import dataclass

@dataclass
class QueuedTask:
    config: AutoResearchConfig
    queued_at: float

class AutoResearchManager:
    def __init__(self, max_concurrent_tasks: int = 2):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_queue: deque[QueuedTask] = deque()
        self.active_tasks: dict[str, ActiveTaskInfo] = {}

    def launch(self, config: AutoResearchConfig) -> str:
        if len(self.active_tasks) >= self.max_concurrent_tasks:
            # 加入队列而不是报错
            self.task_queue.append(QueuedTask(config=config, queued_at=time.time()))
            return config.task_id  # 仍然返回 task_id，可供后续查询

        return self._do_launch(config)

    def _do_launch(self, config: AutoResearchConfig) -> str:
        """执行实际的 launch 逻辑（同 2.3 节）。"""
        ...

    def on_task_complete(self, task_id: str) -> None:
        """任务完成后，检查队列并启动下一个任务。"""
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]

        if self.task_queue:
            next_task = self.task_queue.popleft()
            self._do_launch(next_task.config)
```

### 2.5 sub-agent 任务提示词（sessions_spawn 时传入）

```python
task_prompt = f"""你是 AutoResearch 研究员。任务ID: {task_id}

工作目录: {workdir}/

关键要求：
1. **Checkpoint 支持**：每次实验结束后调用 CheckpointManager 保存存档
2. **中断恢复**：启动时检查 checkpoints/{task_id}/ 是否存在，若存在则从断点继续
3. **独立运行**：每个任务的 workdir 隔离，不要依赖其他任务的目录
4. **超时控制**：单次实验超时 {experiment_duration_seconds}s
5. **doom_loop 检测**：连续 5 次实验被拒绝时，写入告警并停止

执行步骤：
1. 检查 checkpoints/{task_id}/checkpoint_manifest.json 是否存在
   - 若存在：从 last_experiment_index + 1 继续执行
   - 若不存在：初始化新任务
2. 执行 scripts/autoresearch_run.py
3. 完成后将最终结果写入 results/{task_id}.json
"""
```

---

## 3. 异常恢复设计

### 3.1 异常分类

| 类型 | 触发条件 | 处理策略 |
|------|----------|----------|
| `kill -9` | 进程被强制终止 | 下次启动时从 checkpoint 恢复 |
| OOM | 进程内存不足被系统 kill | 同上 |
| 训练崩溃 | train.py 抛出异常 | 实验记录标记为 failed，继续下一个 |
| doom_loop | 连续 5 次实验被拒绝 | 停止搜索，写入告警 |
| 超时 | 实验超过 experiment_duration_seconds | 杀掉进程，标记超时 |
| disk full | 磁盘空间不足 | 立即停止，写入告警 |

### 3.2 恢复流程状态机

```
                    ┌─────────────────────────────────────────────────┐
                    │                   start                         │
                    └──────────────────────┬──────────────────────────┘
                                           ▼
                    ┌─────────────────────────────────────────────────┐
                    │  check result.json exists?                       │
                    │  (任务是否已完成)                                  │
                    └──────────────────────┬──────────────────────────┘
                                    YES   │   NO
                    ┌──────────────────────┴──────────────────────────┐
                    │  RETURN completed result                          │
                    │  (直接返回，不重复执行)                            │
                    └─────────────────────────────────────────────────┘
                                           NO
                                           ▼
                    ┌─────────────────────────────────────────────────┐
                    │  check checkpoint_manifest.json exists?         │
                    │  (是否有可恢复的存档)                             │
                    └──────────────────────┬──────────────────────────┘
                                    YES   │   NO
                    ┌──────────────────────┴──────────────────────────┐
                    │  LOAD checkpoint                                │
                    │  - last_experiment_index                        │
                    │  - best_val / best_params                       │
                    │  - completed_experiment_ids                      │
                    │  RESTORE experiments.json from latest run/       │
                    └──────────────────────┬──────────────────────────┘
                                           ▼
                    ┌─────────────────────────────────────────────────┐
                    │  RUN experiment loop from (last_index + 1)     │
                    │  (跳过已完成实验，继续剩余实验)                    │
                    └──────────────────────┬──────────────────────────┘
                                           ▼
                    ┌─────────────────────────────────────────────────┐
                    │  experiment completed normally?                │
                    │  - save_checkpoint() after each experiment      │
                    │  - update experiments.json                      │
                    └──────────────────────┬──────────────────────────┘
                                    YES   │   NO (exception)
                    ┌──────────────────────┴──────────────────────────┐
                    │  on_exception(experiment_id, error)             │
                    │  - store.add_experiment(accepted=False, error)  │
                    │  - reporter.fail(error) if fatal                │
                    │  - if doom_loop: stop & alert                   │
                    │  - else: continue to next experiment            │
                    └──────────────────────┬──────────────────────────┘
                                           ▼
                    ┌─────────────────────────────────────────────────┐
                    │  all experiments done or budget exceeded?      │
                    │  write_result() + checkpoint complete marker   │
                    └─────────────────────────────────────────────────┘
```

### 3.3 kill -9 恢复核心代码

```python
# autoresearch_run.py 的 run_experiment_loop_with_checkpoint()

def run_experiment_loop_with_checkpoint(
    task: TaskDefinition,
    workspace: Path,
    max_experiments: Optional[int] = None,
    max_duration_minutes: Optional[int] = None,
    experiment_duration_seconds: int = DEFAULT_EXPERIMENT_DURATION,
    verbose: bool = False,
) -> TaskResult:
    max_experiments = max_experiments or task.budget.max_experiments
    max_duration_minutes = max_duration_minutes or task.budget.max_duration_minutes

    checkpoint_mgr = CheckpointManager(task.task_id)

    # ── 检测点：是否已完成？ ────────────────────────────────────
    result_file = RESULTS_DIR / f"{task.task_id}.json"
    if result_file.exists():
        if verbose:
            print(f"[checkpoint] 任务已完成，直接返回")
        return read_result(task.task_id)

    # ── 检测点：是否有 checkpoint 可恢复？ ─────────────────────
    manifest = checkpoint_mgr.get_latest_checkpoint()
    if manifest:
        last_exp_idx = manifest["last_experiment_index"]
        completed_ids = set(manifest.get("completed_experiment_ids", []))
        best_val = manifest.get("best_val")
        best_params = manifest.get("best_params")
        if verbose:
            print(f"[checkpoint] 恢复执行：从 exp-{last_exp_idx + 1:03d} 开始，"
                  f"已完成 {len(completed_ids)} 个实验")
    else:
        last_exp_idx = -1
        completed_ids = set()
        best_val = None
        best_params = None
        # 初始化 checkpoint 目录
        checkpoint_mgr.save_task_definition(task)

    # ── 恢复或初始化 ExperimentStore ───────────────────────────
    store = ExperimentStore(task_id=task.task_id, workdir=workspace,
                            direction=task.metric.direction.value)
    if manifest:
        # 从最新的 run 目录恢复 experiments.json
        store = _restore_from_checkpoint(checkpoint_mgr, store, workspace)
    else:
        store.load()

    # ── 主实验循环（从断点继续）────────────────────────────────
    minimize = task.metric.direction.value == "minimize"

    for exp_idx in range(last_exp_idx + 1, max_experiments):
        experiment_id = f"exp-{exp_idx + 1:03d}"

        # 跳过已完成的实验（断点恢复）
        if experiment_id in completed_ids:
            if verbose:
                print(f"[{experiment_id}] 跳过（已在存档中）")
            continue

        # ... 正常执行实验 ...
        # 1. sample → 2. modify → 3. train → 4. snapshot → 5. record

        # ── 实验结束后：Checkpoint 保存 ──────────────────────────
        is_new_best = _updated_best(
            new_val=current_val, best_val=best_val, direction=minimize
        )

        checkpoint_mgr.save_checkpoint(
            experiment_id=experiment_id,
            experiments_json={
                "best_val": store.best_val,
                "best_params": store.best_params,
                "experiments": store.experiments,
            },
            workdir=workspace,
            is_new_best=is_new_best,
            best_val=store.best_val,
            best_params=store.best_params,
        )

        if is_new_best:
            best_val = store.best_val
            best_params = store.best_params

    # ── 写入最终结果 ───────────────────────────────────────────
    result = TaskResult(...)
    write_result(result)
    return result
```

### 3.4 ExperimentStore 恢复逻辑

```python
def _restore_from_checkpoint(
    checkpoint_mgr: CheckpointManager,
    store: ExperimentStore,
    workspace: Path,
) -> ExperimentStore:
    """从 checkpoint 恢复 ExperimentStore 的最新状态。"""
    manifest = checkpoint_mgr.get_latest_checkpoint()
    if not manifest:
        return store

    # 找到最新的 run 目录
    runs = sorted(checkpoint_mgr.runs_dir.iterdir())
    if not runs:
        return store

    latest_run = runs[-1]
    experiments_file = latest_run / "experiments.json"

    if experiments_file.exists():
        data = json.loads(experiments_file.read_text(encoding="utf-8"))
        store.best_val = data.get("best_val")
        store.best_params = data.get("best_params")
        store.best_experiment_id = data.get("best_experiment_id")
        store.experiments = data.get("experiments", [])
        store.save()  # 恢复到 workdir/experiments.json

    return store
```

---

## 4. 告警机制设计

### 4.1 告警类型与触发条件

| 告警类型 | 触发条件 | 优先级 | 说明 |
|----------|----------|--------|------|
| `doom_loop` | `stuck_streak >= 5` 且近 5 次实验全部被拒绝 | 🔴 高 | 搜索陷入局部最优或参数空间不当 |
| `task_crash` | 任意实验抛出未捕获异常（非超时） | 🔴 高 | train.py 崩溃或 OOM |
| `task_timeout` | `experiment_duration_seconds * 1.1` 内未完成 | 🟡 中 | 单次实验响应超时 |
| `budget_exceeded` | `elapsed_minutes >= max_duration_minutes` | 🟢 低 | 时间预算耗尽 |
| `disk_low` | 磁盘剩余空间 < 1GB | 🔴 高 | 存档可能失败 |
| `subagent_dead` | sub-agent session 状态变为 dead/error | 🔴 高 | 需人工干预 |
| `metric_stalled` | 连续 10 次实验 best_val 无改善 | 🟡 中 | 收敛到平台期 |

### 4.2 告警通知格式

所有告警统一写入 `results/<task_id>-alerts.json`：

```json
{
  "task_id": "task_abc123",
  "alerts": [
    {
      "alert_id": "alert-001",
      "type": "doom_loop",
      "severity": "high",
      "triggered_at": "2026-04-27T10:30:00Z",
      "experiment_index": 8,
      "message": "连续 5 次实验被拒绝，搜索可能陷入局部最优。"
                  "最近实验: exp-004, exp-005, exp-006, exp-007, exp-008。",
      "context": {
        "stuck_streak": 5,
        "recent_experiment_ids": ["exp-004", "exp-005", "exp-006", "exp-007", "exp-008"],
        "best_val": 0.91,
        "best_params": {"lr": 0.001, "depth": 8}
      },
      "recommended_action": "调整超参数空间或增加 experiment_duration_seconds"
    },
    {
      "alert_id": "alert-002",
      "type": "task_crash",
      "severity": "high",
      "triggered_at": "2026-04-27T10:35:00Z",
      "experiment_index": 9,
      "message": "train.py 崩溃。错误: CUDA out of memory。",
      "context": {
        "experiment_id": "exp-009",
        "error_type": "RuntimeError",
        "error_message": "CUDA out of memory"
      },
      "recommended_action": "减小 batch_size 或 dim"
    }
  ],
  "summary": {
    "total_alerts": 2,
    "high_severity": 2,
    "medium_severity": 0,
    "low_severity": 0,
    "most_recent_at": "2026-04-27T10:35:00Z"
  }
}
```

### 4.3 AlertManager 核心实现

```python
# lib/alert_manager.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
import uuid

class AlertSeverity(str, Enum):
    HIGH = "high"      # 🔴 需立即处理
    MEDIUM = "medium"  # 🟡 需关注
    LOW = "low"        # 🟢 通知


class AlertType(str, Enum):
    DOOM_LOOP = "doom_loop"
    TASK_CRASH = "task_crash"
    TASK_TIMEOUT = "task_timeout"
    BUDGET_EXCEEDED = "budget_exceeded"
    DISK_LOW = "disk_low"
    SUBAGENT_DEAD = "subagent_dead"
    METRIC_STALLED = "metric_stalled"


@dataclass
class Alert:
    alert_id: str
    type: AlertType
    severity: AlertSeverity
    triggered_at: str
    experiment_index: int
    message: str
    context: dict = field(default_factory=dict)
    recommended_action: str = ""


@dataclass
class AlertManifest:
    task_id: str
    alerts: list[Alert] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict: ...


class AlertManager:
    """
    统一管理任务告警。
    告警写入 results/<task_id>-alerts.json。
    可扩展：支持飞书 webhook / email。
    """

    # 触发阈值（可配置）
    DOOM_LOOP_THRESHOLD = 5
    STALL_THRESHOLD = 10

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.alerts_file = RESULTS_DIR / f"{task_id}-alerts.json"
        self._manifest = AlertManifest(task_id=task_id)

    def trigger(
        self,
        alert_type: AlertType,
        experiment_index: int,
        message: str,
        context: Optional[dict] = None,
        recommended_action: str = "",
    ) -> Alert:
        """触发一个新告警。"""
        severity = self._severity_for(alert_type)
        alert = Alert(
            alert_id=f"alert-{uuid.uuid4().hex[:8]}",
            type=alert_type,
            severity=severity,
            triggered_at=datetime.now(timezone.utc).isoformat(),
            experiment_index=experiment_index,
            message=message,
            context=context or {},
            recommended_action=recommended_action,
        )
        self._manifest.alerts.append(alert)
        self._save()
        return alert

    def _severity_for(self, alert_type: AlertType) -> AlertSeverity:
        mapping = {
            AlertType.DOOM_LOOP: AlertSeverity.HIGH,
            AlertType.TASK_CRASH: AlertSeverity.HIGH,
            AlertType.TASK_TIMEOUT: AlertSeverity.MEDIUM,
            AlertType.BUDGET_EXCEEDED: AlertSeverity.LOW,
            AlertType.DISK_LOW: AlertSeverity.HIGH,
            AlertType.SUBAGENT_DEAD: AlertSeverity.HIGH,
            AlertType.METRIC_STALLED: AlertSeverity.MEDIUM,
        }
        return mapping.get(alert_type, AlertSeverity.MEDIUM)

    def _save(self) -> None:
        self._manifest.summary = {
            "total_alerts": len(self._manifest.alerts),
            "high_severity": sum(
                1 for a in self._manifest.alerts if a.severity == AlertSeverity.HIGH
            ),
            "medium_severity": sum(
                1 for a in self._manifest.alerts if a.severity == AlertSeverity.MEDIUM
            ),
            "low_severity": sum(
                1 for a in self._manifest.alerts if a.severity == AlertSeverity.LOW
            ),
            "most_recent_at": self._manifest.alerts[-1].triggered_at
                               if self._manifest.alerts else None,
        }
        self.alerts_file.parent.mkdir(parents=True, exist_ok=True)
        self.alerts_file.write_text(
            json.dumps(self._manifest.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def has_high_alert(self) -> bool:
        """检查是否有未处理的高优先级告警。"""
        return any(
            a.severity == AlertSeverity.HIGH
            for a in self._manifest.alerts
        )
```

### 4.4 ProgressReporter 集成 AlertManager

在 `ProgressReporter.report()` 中，当检测到 doom_loop 时触发告警：

```python
class ProgressReporter:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self._alert_mgr = AlertManager(task_id)  # 新增

    def report(self, ...):
        # ... 现有 doom_loop 检测逻辑 ...
        doom_loop_warning = (...)

        if doom_loop_warning:
            self._alert_mgr.trigger(
                alert_type=AlertType.DOOM_LOOP,
                experiment_index=experiment_index,
                message=(
                    f"连续 {self.DOOM_LOOP_THRESHOLD} 次实验被拒绝，"
                    f"搜索可能陷入局部最优或参数空间不当。"
                    f"最近实验: {recent_exp_ids}。"
                ),
                context={
                    "stuck_streak": self._stuck_streak,
                    "recent_experiment_ids": recent_exp_ids,
                    "best_val": best_val,
                    "best_params": best_params,
                },
                recommended_action=(
                    "建议：1) 扩大超参数搜索范围；"
                    "2) 增加 experiment_duration_seconds；"
                    "3) 调整 base train.py 的初始化策略。"
                ),
            )
```

### 4.5 告警通知扩展

#### 4.5.1 飞书 Webhook（Phase 4 优先级）

```python
# lib/notifiers/feishu_webhook.py

FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL")

def send_feishu_alert(alert: Alert, task_id: str) -> None:
    """发送高优先级告警到飞书。"""
    if not FEISHU_WEBHOOK_URL:
        return

    import requests
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text",
                          "content": f"🚨 ML研究告警 [{alert.severity.value.upper()}]"},
                "template": "red" if alert.severity == AlertSeverity.HIGH else "orange",
            },
            "elements": [
                {"tag": "markdown", "content": f"**任务 ID**: `{task_id}`"},
                {"tag": "markdown", "content": f"**告警类型**: {alert.type.value}"},
                {"tag": "markdown", "content": f"**实验序号**: {alert.experiment_index}"},
                {"tag": "markdown", "content": alert.message},
                {"tag": "markdown",
                 "content": f"> 建议: {alert.recommended_action}"},
            ],
        },
    }
    requests.post(FEISHU_WEBHOOK_URL, json=payload, timeout=5)
```

#### 4.5.2 Email 通知（Phase 4 优先级）

```python
# lib/notifiers/email_notifier.py

def send_email_alert(manifest: AlertManifest) -> None:
    """发送告警汇总邮件。"""
    import smtplib, os
    from email.mime.text import MIMEText

    if not os.environ.get("SMTP_HOST"):
        return

    msg = MIMEText(json.dumps(manifest.to_dict(), indent=2))
    msg["Subject"] = f"[Alert] Task {manifest.task_id}: {manifest.summary['high_severity']} high-severity issues"
    # ... smtplib.sendmail() ...
```

### 4.6 实现优先级

| 优先级 | 功能 | 工作量 | 说明 |
|--------|------|--------|------|
| **P0** | Checkpoint 存档与恢复 | 中 | 核心可靠性功能 |
| **P0** | AlertManager + alerts.json | 低 | 为后续扩展打基础 |
| **P0** | doom_loop 触发告警 | 低 | ProgressReporter 已有字段 |
| **P1** | AutoResearchManager 并发队列 | 中 | 多任务支持 |
| **P1** | 任务重启自动检测恢复 | 低 | 利用 checkpoint 实现 |
| **P2** | 磁盘空间监控告警 | 低 | 扩展 AlertManager |
| **P2** | sub-agent 心跳检测 | 中 | 检测 session 异常 |
| **P3** | 飞书 Webhook | 低 | 依赖 P0/P1 |
| **P3** | Email 通知 | 低 | 依赖 P0/P1 |

---

## 5. train.py 改造要求

为支持 checkpoint，train.py 需做以下改造：

### 5.1 模型保存

```python
# 在训练结束时（所有 epoch 完成后，或 early-stop 时）
import os, torch

# 保存最佳模型
model_path = os.path.join(os.environ.get("OUTPUT_DIR", "."), "model.pt")
torch.save(model.state_dict(), model_path)
print(f"[RESULT] model_saved={model_path}")
```

### 5.2 SEARCH REGION 扩展

train.py 的 SEARCH REGION 应包含所有可调超参数：

```python
# ======= AUTORESEARCH SEARCH REGION START =======
# Auto-generated hyperparameters
LR = 0.001
BATCH_SIZE = 32
DIM = 256
DEPTH = 8
WEIGHT_DECAY = 1e-4
# ======= AUTORESEARCH SEARCH REGION END =======
```

---

## 6. 文件结构（Phase 3 完成后）

```
ml-research-loop/
├── ml_intern/
│   ├── autoresearch_manager.py   # P1: 并发队列改造
│   └── tools/
│       └── run_autoresearch.py
├── lib/
│   ├── task_protocol.py          # (已有)
│   ├── experiment_store.py        # (已有)
│   ├── progress_reporter.py       # P0: 集成 AlertManager
│   ├── checkpoint_manager.py      # P0: 新增
│   ├── alert_manager.py          # P0: 新增
│   └── notifiers/
│       ├── __init__.py
│       ├── feishu_webhook.py      # P3: 新增
│       └── email_notifier.py     # P3: 新增
├── scripts/
│   ├── autoresearch_run.py        # P0: checkpoint 集成
│   ├── sample_hyperparams.py     # (已有)
│   └── generate_program_md.py    # (已有)
├── tasks/                         # (已有)
├── results/                       # (已有)
│   ├── <task_id>.json            # 最终结果
│   ├── <task_id>-progress.json   # 实时进度
│   └── <task_id>-alerts.json     # P0: 告警记录
├── workdir/                       # (已有)
│   └── <task_id>/
│       ├── experiments.json       # 实验记录
│       ├── train.py
│       └── model.pt               # (train.py 输出)
├── checkpoints/                   # P0: 新增
│   └── <task_id>/
│       ├── checkpoint_manifest.json
│       ├── task_definition.json
│       ├── experiments.json
│       ├── best/
│       │   ├── model.pt
│       │   ├── train.py
│       │   └── metadata.json
│       └── runs/
│           ├── run-001/
│           └── run-002/
├── base/
│   ├── train_base.py              # P0: 添加 model.pt 保存逻辑
│   └── prepare.py
└── docs/
    ├── ml-intern-集成方案.md      # (已有)
    └── Phase3-可靠性设计.md        # (本文档)
```

---

## 7. 关键风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| train.py 不输出 model.pt | checkpoint 无模型权重 | 用 snapshots 存档 train.py 作为替代，model.pt 作为增强 |
| checkpoint 保存过于频繁 | 磁盘 IO 成为瓶颈 | 只在实验结束后存档，不在训练中途 |
| sessions_spawn 进程僵死 | sub-agent 无法完成 | 添加 session 心跳检测，超时后标记 dead |
| 并发任务数过高 | CPU/GPU 显存 OOM | `max_concurrent_tasks` 默认设为 2（可配置） |
| experiments.json 损坏 | 无法恢复 | 使用原子写入（temp file + rename） |
