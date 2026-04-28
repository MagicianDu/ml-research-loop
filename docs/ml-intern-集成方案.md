# ml-intern × AutoResearch 集成方案

> **角色**：Architect（架构师）
> **日期**：2026-04-27
> **目标**：让 ml-intern（主 Agent）通过 smolagents ToolRouter 驱动 AutoResearch sub-agent

---

## 1. 整体架构

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         ml-intern (主 Agent)                               │
│                                                                      │
│   ToolRouter                                                          │
│   ┌─────────────────────────┐  ┌──────────────────────────┐           │
│   │  RunAutoresearchTool    │  │  GetAutoresearchStatusTool│          │
│   │  GetAutoresearchResultTool │ │  (optional future)       │           │
│   └─────────────────────────┘  └──────────────────────────┘           │
│           │                         │                                  │
└───────────│─────────────────────────│──────────────────────────────────┘
            │ tool call (同步/异步)      │ tool call (同步)
            ▼                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│               ml_intern/tools/run_autoresearch.py                    │
│                                                                    │
│  3 Tool 类（smolagents Tool 基类）                                   │
│  ┌────────────────────────────┐                                    │
│  │ RunAutoresearchTool        │──► create_autoresearch_task()        │
│  │ GetAutoresearchStatusTool │──► manager.get_status()              │
│  │ GetAutoresearchResultTool │──► manager.get_result()              │
│  └────────────────────────────┘                                    │
└────────────────────────────────────────────────────────────────────┘
            │
            ▼ (内部 spawn sub-agent)
┌──────────────────────────────────────────────────────────────────────┐
│               autoresearch_manager.py (AutoResearchManager)           │
│                                                                      │
│  1. write_task()     ──► tasks/<task_id>.json                        │
│  2. acquire_task_lock()                                               │
│  3. sessions_spawn() ──► AutoResearch sub-agent (异步,后台运行)        │
│  4. return task_id   ──► 主 Agent 立即收到响应                        │
│                                                                      │
│  进度文件：results/<task_id>-progress.json (子 agent 轮写)             │
│  结果文件：results/<task_id>.json (子 agent 完成时写入)               │
└──────────────────────────────────────────────────────────────────────┘
            │
            ▼ (sub-agent 执行)
┌──────────────────────────────────────────────────────────────────────┐
│                 AutoResearch Sub-Agent (sessions_spawn)              │
│                                                                      │
│  循环执行：                                                            │
│    1. sample_hyperparams.py 采样超参                                  │
│    2. 修改 train.py                                                   │
│    3. scripts/autoresearch_run.py 训练并记录指标                       │
│    4. 更新 results/<task_id>-progress.json                            │
│    5. 判断是否满足 early-stop 条件                                     │
│  完成后写入 results/<task_id>.json                                     │
└──────────────────────────────────────────────────────────────────────┘
```

### 数据流总结

| 阶段 | 动作 | 文件 |
|------|------|------|
| 1 | `RunAutoresearchTool.forward()` → `create_autoresearch_task()` | 写入 `tasks/<task_id>.json` |
| 2 | 子 Agent 启动，轮写进度 | 写入 `results/<task_id>-progress.json` |
| 3 | 主 Agent 通过 `GetAutoresearchStatusTool` 轮询进度 | 读取 `results/<task_id>-progress.json` |
| 4 | 子 Agent 完成，写入最终结果 | 写入 `results/<task_id>.json` |
| 5 | 主 Agent 通过 `GetAutoresearchResultTool` 读取结果 | 读取 `results/<task_id>.json` |

---

## 2. 现有代码分析

### 2.1 已有文件

| 文件 | 作用 |
|------|------|
| `ml_intern/autoresearch_manager.py` | AutoResearchManager：管理 sub-agent 生命周期、launch/monitor/get_status/get_result |
| `ml_intern/tools/run_autoresearch.py` | 现有工具定义（函数式），提供 `get_tool_spec()`, `run_autoresearch_handler()`, `get_autoresearch_status_handler()`, `get_autoresearch_result_handler()` |
| `lib/task_protocol.py` | TaskDefinition/TaskResult 数据类 + JSON 文件读写 |

### 2.2 当前问题

现有实现是**函数式**的（返回 dict spec + handler 函数），未使用 smolagents 的 `Tool` 基类。需要改造为真正的 smolagents Tool class。

### 2.3 smolagents Tool 基类核心要素

```python
from smolagents import Tool

class MyTool(Tool):
    name: str          # 工具名，LLM 调用用
    description: str    # 描述，供 LLM 理解何时调用
    inputs: dict        # JSON Schema 格式的输入定义
    output_type: str    # 输出类型，"string" | "integer" | "number" | "boolean" | "array" | "object"

    def forward(self, **kwargs) -> ...:
        # 实际执行逻辑
```

---

## 3. Tool 接口设计（完整代码）

### 3.1 `RunAutoresearchTool`

```python
# ml_intern/tools/run_autoresearch.py
# （在现有文件上追加或替换）

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Optional

from smolagents import Tool
from ml_intern.autoresearch_manager import (
    create_autoresearch_task,
    AutoResearchManager,
)

if TYPE_CHECKING:
    pass


class RunAutoresearchTool(Tool):
    """
    Launch an autonomous ML research loop to optimize a neural network training script.

    Uses a fixed time budget per experiment, single-file editing constraint,
    and metric-based acceptance criteria. Best for: architecture search,
    optimizer tuning, hyperparameter optimization on a fixed dataset.

    Returns a task_id for monitoring progress via get_autoresearch_status.
    After completion, use get_autoresearch_result to retrieve the best config.
    """

    name = "run_autoresearch"
    description = """
Run an autonomous experiment loop to optimize a neural network training script.

Uses a fixed time budget per experiment (default 5 minutes), single-file editing constraint,
and metric-based acceptance. Best for: architecture search, optimizer tuning,
hyperparameter optimization on a fixed dataset.

Returns a task_id for monitoring progress via get_autoresearch_status.
After completion, use get_autoresearch_result to retrieve the best config found.

Example:
    task_id = run_autoresearch(
        objective="minimize val_bpb on the TinyStories dataset",
        dataset_path="data/train_8192_256.bin",
        metric_name="val_bpb",
        metric_direction="minimize",
        metric_target=0.85,
        max_experiments=50,
        experiment_duration_seconds=300,
        hyperparameter_space={
            "lr": {"type": "log_uniform", "min": 1e-5, "max": 1e-2},
            "depth": {"type": "choice", "values": [4, 6, 8, 10, 12]},
        }
    )
    """
    inputs = {
        "objective": {
            "type": "string",
            "description": "Description of what to optimize, e.g. 'minimize val_bpb on TinyStories'",
            "required": True,
        },
        "dataset_path": {
            "type": "string",
            "description": "Path to training data binary file",
            "required": True,
        },
        "metric_name": {
            "type": "string",
            "description": "Name of metric to optimize (default: val_bpb)",
            "default": "val_bpb",
        },
        "metric_direction": {
            "type": "string",
            "description": "'minimize' or 'maximize' (default: minimize)",
            "enum": ["minimize", "maximize"],
            "default": "minimize",
        },
        "metric_target": {
            "type": "number",
            "description": "Target value for early stopping (optional). "
                          "When reached, the search stops early.",
        },
        "max_experiments": {
            "type": "integer",
            "description": "Maximum number of experiments (default: 50)",
            "default": 50,
        },
        "experiment_duration_seconds": {
            "type": "integer",
            "description": "Duration per individual experiment in seconds (default: 300 = 5 min)",
            "default": 300,
        },
        "max_duration_minutes": {
            "type": "integer",
            "description": "Maximum total runtime in minutes across all experiments (default: 120)",
            "default": 120,
        },
        "hyperparameter_space": {
            "type": "object",
            "description": "Search space definition as dict of param_name -> spec. "
                          "Spec format: {'type': 'log_uniform'|'uniform'|'choice', "
                          "'min': float, 'max': float} or {'type': 'choice', 'values': [...]}. "
                          "Example: {'lr': {'type': 'log_uniform', 'min': 1e-5, 'max': 1e-2}}",
        },
        "base_train_py_path": {
            "type": "string",
            "description": "Path to custom train.py base file (optional, "
                          "falls back to base/train_base.py)",
        },
        "task_id": {
            "type": "string",
            "description": "Custom task ID (optional, auto-generated if not provided). "
                          "Use if you need a predictable ID.",
        },
    }
    output_type = "string"  # Returns a JSON string containing task_id

    def forward(
        self,
        objective: str,
        dataset_path: str,
        metric_name: str = "val_bpb",
        metric_direction: str = "minimize",
        metric_target: Optional[float] = None,
        max_experiments: int = 50,
        experiment_duration_seconds: int = 300,
        max_duration_minutes: int = 120,
        hyperparameter_space: Optional[dict] = None,
        base_train_py_path: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """
        Launch the autoresearch loop.

        Args:
            objective: Description of what to optimize.
            dataset_path: Path to training data binary file.
            metric_name: Name of metric to optimize.
            metric_direction: 'minimize' or 'maximize'.
            metric_target: Target value for early stopping (optional).
            max_experiments: Max number of experiments.
            experiment_duration_seconds: Duration per experiment.
            max_duration_minutes: Total time budget across all experiments.
            hyperparameter_space: Search space definition.
            base_train_py_path: Custom base train.py path.
            task_id: Custom task ID (optional).

        Returns:
            JSON string with task_id and launch status.
        """
        if task_id is None:
            task_id = f"task_{uuid.uuid4().hex[:8]}"

        result_task_id = create_autoresearch_task(
            task_id=task_id,
            objective=objective,
            dataset_path=dataset_path,
            metric_name=metric_name,
            metric_direction=metric_direction,
            metric_target=metric_target,
            max_experiments=max_experiments,
            max_duration_minutes=max_duration_minutes,
            experiment_duration_seconds=experiment_duration_seconds,
            hyperparameter_space=hyperparameter_space,
            base_train_py_path=base_train_py_path,
        )

        return json.dumps({
            "task_id": result_task_id,
            "status": "launched",
            "message": (
                f"Autoresearch task {result_task_id} launched. "
                f"Monitor via get_autoresearch_status(task_id='{result_task_id}'). "
                f"Results via get_autoresearch_result(task_id='{result_task_id}')."
            ),
        })
```

### 3.2 `GetAutoresearchStatusTool`

```python
class GetAutoresearchStatusTool(Tool):
    """
    Get the current status of a running autoresearch task.

    Returns progress information including:
    - current experiment index and total
    - best metric value achieved so far
    - best hyperparameters found
    - elapsed time
    - error message if failed

    Call this repeatedly to track progress of a running task.
    """

    name = "get_autoresearch_status"
    description = """
Get the current status of a running autoresearch task.

Returns progress information including:
- current experiment index and total
- best metric value achieved so far
- best hyperparameters found
- elapsed time
- error message if failed

Call this repeatedly to track progress. Status values:
- 'pending': task created but sub-agent not started
- 'running': experiments in progress
- 'completed': all experiments done, result available
- 'failed': task failed with error
- 'budget_exceeded': max_experiments or max_duration reached
    """
    inputs = {
        "task_id": {
            "type": "string",
            "description": "The task_id returned by run_autoresearch",
            "required": True,
        },
    }
    output_type = "string"  # Returns JSON string

    def forward(self, task_id: str) -> str:
        """
        Get current status of an autoresearch task.

        Args:
            task_id: The task_id returned by run_autoresearch.

        Returns:
            JSON string with task status, progress, best_val, etc.
        """
        manager = AutoResearchManager()
        status = manager.get_status(task_id)
        return json.dumps(status, indent=2)
```

### 3.3 `GetAutoresearchResultTool`

```python
class GetAutoresearchResultTool(Tool):
    """
    Get the final result of a completed autoresearch task.

    Returns the best experiment found, including:
    - best metric value and hyperparameters
    - total experiments run
    - experiment history summary

    Only call this after task status shows 'completed' or 'budget_exceeded'.
    Use get_autoresearch_status to check if results are ready.
    """

    name = "get_autoresearch_result"
    description = """
Get the final result of a completed autoresearch task.

Returns the best experiment found, including:
- best metric value and hyperparameters
- total experiments run
- experiment history summary

Only call after task status shows 'completed' or 'budget_exceeded'.
Use get_autoresearch_status first to check if results are ready.
    """
    inputs = {
        "task_id": {
            "type": "string",
            "description": "The task_id returned by run_autoresearch",
            "required": True,
        },
    }
    output_type = "string"  # Returns JSON string

    def forward(self, task_id: str) -> str:
        """
        Get final result of a completed autoresearch task.

        Args:
            task_id: The task_id returned by run_autoresearch.

        Returns:
            JSON string with best result, or 'not_ready' if not yet available.
        """
        manager = AutoResearchManager()
        result = manager.get_result(task_id)

        if result is None:
            return json.dumps({
                "task_id": task_id,
                "status": "not_ready",
                "message": (
                    "Result not yet available. "
                    "Check again later or call get_autoresearch_status to confirm completion."
                ),
            })

        return json.dumps(result.to_dict(), indent=2)
```

---

## 4. ml-intern 集成方式

### 4.1 Tool 注册

在 ml-intern 初始化时注册 tools：

```python
# ml_intern/tool_router.py (或初始化文件)

from ml_intern.tools.run_autoresearch import (
    RunAutoresearchTool,
    GetAutoresearchStatusTool,
    GetAutoresearchResultTool,
)

def register_autoresearch_tools(router):
    """Register all autoresearch tools with the ToolRouter."""
    router.register(RunAutoresearchTool())
    router.register(GetAutoresearchStatusTool())
    router.register(GetAutoresearchResultTool())
```

### 4.2 异步调用设计（关键）

`RunAutoresearchTool.forward()` 是**同步**的（立即返回 task_id），但实际的 ML 训练运行是**异步**的（通过 `sessions_spawn` 在后台运行 sub-agent）。这是关键设计：

```
主 Agent 调用链：

1. run_autoresearch(objective=..., dataset_path=...)   ← 同步，立即返回
   │
   └─► create_autoresearch_task()                       ← 同步
        │
        ├─► 写入 tasks/<task_id>.json                    ← 同步
        ├─► acquire_task_lock()                          ← 同步
        └─► sessions_spawn(sub-agent)                    ← 异步启动，返回 task_id
             │
             │  (子 agent 在后台运行，轮写 progress 文件)
             │
2. get_autoresearch_status(task_id="...")               ← 同步轮询
   │
   └─► manager.get_status(task_id)                     ← 读 results/<task_id>-progress.json
             │
3. (重复步骤 2 直到 status == 'completed')
             │
4. get_autoresearch_result(task_id="...")                ← 同步
   │
   └─► manager.get_result(task_id)                     ← 读 results/<task_id>.json
```

**为什么这样设计：**
- `forward()` 同步返回 task_id → LLM 立即拿到 session key，可以继续其他工作
- sub-agent 在后台运行，不阻塞主 Agent 的推理
- 通过轮询 `get_autoresearch_status` 来追踪进度

### 4.3 LLM 调用示例（伪代码）

```
用户：
  "在 TinyStories 数据集上搜索最优学习率和深度组合"

ml-intern 内部：
  ToolCall: run_autoresearch(
    objective="minimize val_bpb on TinyStories",
    dataset_path="data/train_8192_256.bin",
    metric_name="val_bpb",
    metric_direction="minimize",
    max_experiments=50,
    hyperparameter_space={
      "lr": {"type": "log_uniform", "min": 1e-5, "max": 1e-2},
      "depth": {"type": "choice", "values": [4, 6, 8, 10, 12]},
    }
  )
  → 返回: {"task_id": "task_a1b2c3d4", "status": "launched", ...}

  [主 Agent 继续其他工作，或轮询状态]

  ToolCall: get_autoresearch_status(task_id="task_a1b2c3d4")
  → 返回: {"task_id": "...", "status": "running", "experiment_index": 12,
           "best_val": 0.91, "best_params": {"lr": 0.003, "depth": 8}, ...}

  [继续轮询...]

  ToolCall: get_autoresearch_status(task_id="task_a1b2c3d4")
  → 返回: {"task_id": "...", "status": "completed", ...}

  ToolCall: get_autoresearch_result(task_id="task_a1b2c3d4")
  → 返回: {"task_id": "...", "status": "completed",
           "best_result": {"val_bpb": 0.87, "params": {"lr": 0.0031, "depth": 10}},
           "experiments": [...], ...}
```

---

## 5. 调用流程图

```
ml-intern
   │
   ├─► RunAutoresearchTool.forward()
   │        │
   │        ├─► create_autoresearch_task()
   │        │     ├─► TaskDefinition 组装
   │        │     ├─► write_task() ──► tasks/<task_id>.json
   │        │     └─► sessions_spawn() ──► [后台] AutoResearch Sub-Agent
   │        │
   │        └─► return {"task_id": "xxx", "status": "launched"}
   │
   ├─► [继续其他工作]
   │
   ├─► GetAutoresearchStatusTool.forward(task_id)
   │        │
   │        └─► manager.get_status()
   │              └─► read_progress() ─► results/<task_id>-progress.json
   │                   (由 sub-agent 轮写)
   │              └─► return {status, experiment_index, best_val, ...}
   │
   ├─► [轮询直到 completed/budget_exceeded/failed]
   │
   └─► GetAutoresearchResultTool.forward(task_id)
            │
            └─► manager.get_result()
                  └─► read_result() ─► results/<task_id>.json
                  └─► return TaskResult (best_result, experiments, summary)
```

---

## 6. 文件结构

```
ml-research-loop/
├── ml_intern/
│   ├── __init__.py
│   ├── autoresearch_manager.py     # AutoResearchManager, create_autoresearch_task()
│   └── tools/
│       ├── __init__.py
│       └── run_autoresearch.py     # 3个 Tool 类（本文设计）
├── lib/
│   ├── task_protocol.py            # TaskDefinition, TaskResult, JSON I/O
│   └── ...
├── scripts/
│   ├── autoresearch_run.py         # 子 agent 执行脚本
│   └── ...
├── tasks/                          # tasks/<task_id>.json
├── results/                        # results/<task_id>.json
│                                    # results/<task_id>-progress.json
└── docs/
    └── ml-intern-集成方案.md        # 本文档
```

---

## 7. 注意事项

### 7.1 smolagents Tool 基类要求

- 必须有 `name`, `description`, `inputs`, `output_type` 属性
- `inputs` 必须符合 JSON Schema 格式（`type`, `description`, `required`, `default`, `enum`）
- `forward()` 方法接收命名参数，参数名必须与 `inputs` 中的 key 对应
- default 参数在 `inputs` 中声明后，`forward()` 方法签名中也要有 default

### 7.2 异步 vs 同步

| 操作 | 同步/异步 | 原因 |
|------|-----------|------|
| `RunAutoresearchTool.forward()` | **同步** | 立即返回 task_id，不阻塞主 Agent |
| sub-agent 实际训练 | **异步** | sessions_spawn 在后台运行 |
| `GetAutoresearchStatusTool.forward()` | **同步** | 读取 progress 文件，立即返回 |
| `GetAutoresearchResultTool.forward()` | **同步** | 读取 result 文件，立即返回 |

### 7.3 进度文件轮写机制

- sub-agent 每轮实验结束后调用 `write_progress()` 更新 `results/<task_id>-progress.json`
- 主 Agent 通过轮询 `get_autoresearch_status` 获取进度
- 不使用 callback/事件机制——轮询足够简单且可靠

### 7.4 错误处理

| 场景 | 处理 |
|------|------|
| 任务文件已存在 | `TaskLockError` → `ValueError` |
| 进度文件不存在 | `get_status()` 返回 `{"status": "pending"}` |
| 结果文件不存在 | `get_result()` 返回 `{"status": "not_ready"}` |
| sub-agent 异常退出 | `get_status()` 中 `agent_status` 包含 error 信息 |
| 超时（wait_for_completion） | 抛出 `TimeoutError` |

### 7.5 session_key 和 task_id

- `task_id` 是用户视角的任务标识（写入 tasks/ results/ 目录）
- `session_key` 是 `sessions_spawn` 返回的子 agent session 标识（用于监控）
- `AutoResearchManager.active_tasks` 字典维护 task_id → session_key 的映射

### 7.6 潜在改进方向（不影响当前设计）

1. **wait_for_completion Tool**：提供阻塞等待工具（通过 `yieldMs` 在 exec 中实现）
2. **取消任务 Tool**：显式调用 `manager.cancel(task_id)`
3. **事件订阅**：用 OpenClaw cron/event 机制替代轮询
4. **并发限制**：限制同时运行的 sub-agent 数量（通过 `AutoResearchManager` 计数）
