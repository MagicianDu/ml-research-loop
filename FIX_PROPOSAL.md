# ml-research-loop 代码修复方案

> 审查时间：2026-04-27
> 审查人：KANG (Developer subagent)
> 基于文档：ARCHITECTURE.md（IMPLEMENTATION_PLAN.md 不存在，以架构文档为准）

---

## 一、审查结果总览

| 模块 | 状态 | 严重程度 | 不一致项数量 |
|------|------|---------|-------------|
| scripts/autoresearch_run.py | ⚠️ | 中 | 3 |
| lib/task_protocol.py | ⚠️ | 中 | 6 |
| lib/experiment_store.py | ❌ | 高 | 2 |
| lib/progress_reporter.py | ⚠️ | 低 | 3 |
| ml_intern/autoresearch_manager.py | ⚠️ | 中 | 2 |
| base/train_base.py | ⚠️ | 高 | 2 |
| scripts/generate_program_md.py | ✅ | - | 0 |
| tests/unit/ | ⚠️ | 低 | 2 |
| 目录结构 | ⚠️ | 低 | 多项 |

---

## 二、详细一致性审查

### 2.1 目录结构对比

| 架构文档要求路径 | 实际路径 | 状态 |
|----------------|---------|------|
| `ml_intern/agent/core/autoresearch_manager.py` | `ml_intern/autoresearch_manager.py` | ⚠️ 路径不对 |
| `ml_intern/agent/core/tools.py` | `ml_intern/tools/run_autoresearch.py` | ⚠️ 路径不对 |
| `autoresearch/autoresearch_run.py` | `scripts/autoresearch_run.py` | ⚠️ 路径不对 |
| `autoresearch/train.py` | `workdir/<task_id>/train.py`（运行时生成） | ✅ 合理 |
| `autoresearch/prepare.py` | `base/prepare.py` | ⚠️ 路径不对 |
| `autoresearch/program.md` | `workdir/<task_id>/program.md`（运行时生成） | ✅ 合理 |
| `autoresearch/experiment_log.jsonl` | `workdir/experiments.json` | ⚠️ 格式不同 |
| `configs/program_templates/` | 不存在 | ❌ 缺失 |
| `configs/default_constraints.json` | 不存在 | ❌ 缺失 |

---

### 2.2 模块 A: `scripts/autoresearch_run.py`

**文件存在性：** ✅ 存在

**接口一致性：** ⚠️ 部分一致

**功能完整性：** ⚠️ 基本完整

**问题列表：**

#### 问题 A-1：`run_training` metric 解析逻辑过于宽泛
**类型：** 实现错误
**描述：** `parse_training_output` 使用宽泛的正则 `([a-zA-Z_][a-zA-Z0-9_]*)=([0-9.+-]+...)` 匹配所有 `key=value`，会将非 metric 字段（如 `step=10`）也错误地收入 `metrics` dict。
**根因：** 实现时未严格限定只解析 metric 相关字段
**影响：** `metrics.get(metric_name)` 在遇到干扰字段时可能返回错误值，导致 accept/reject 决策出错
**修复方案：**
```python
def parse_training_output(stdout: str) -> dict:
    """Parse validation metrics from training stdout."""
    metrics = {}
    # Only accept metrics with known prefixes
    METRIC_PREFIXES = ("val_", "metric_", "train_", "loss_", "bpb", "ppl", "acc")
    
    for line in stdout.splitlines():
        line = line.strip()
        # Format: [RESULT] key=value or key=value anywhere in line
        if "[RESULT]" in line or any(p in line for p in ("val_", "metric_")):
            for match in re.findall(
                r"([a-zA-Z_][a-zA-Z0-9_]*)=([0-9.+-]+(?:[eE][+-]?\d+)?)", line
            ):
                key, val_str = match
                # Only include if key starts with known metric prefix
                if not any(key.startswith(p) for p in METRIC_PREFIXES):
                    continue
                try:
                    metrics[key] = float(val_str)
                except ValueError:
                    pass

        # JSON block - only extract metric fields
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
```

#### 问题 A-2：`ExperimentStore` 未传入 metric direction，导致 minimize 硬编码
**类型：** 功能缺失
**描述：** `run_experiment_loop` 创建 `ExperimentStore(task_id=task.task_id, workdir=workspace)` 时未传入 `minimize` 方向。`ExperimentStore.add_experiment` 硬编码 `val < self.best_val` 判断，忽略 `task.metric.direction`。
**根因：** `ExperimentStore` 类设计缺陷，`add_experiment` 方法未接受 direction 参数
**影响：** 当任务目标是 maximize（如 val_accuracy）时，accept/reject 决策完全反向
**修复方案：** 见 Module C 的修复

#### 问题 A-3：未实现 `snapshot_code` 的目录层级正确创建
**类型：** 实现错误
**描述：** `autoresearch_run.py` 调用 `snapshot_code(task.task_id, experiment_id, workspace)` 写入 `snapshots/{task_id}/{experiment_id}/train.py`，但 `ExperimentStore.save()` 的临时文件写入同一 `workdir` 目录而非 `snapshots/`。`add_experiment` 里引用 `SNAPSHOTS_DIR / self.task_id / experiment_id`，但 `snapshot_code` 实际创建的是 `SNAPSHOTS_DIR / task_id / experiment_id`，路径有重叠但不一致。
**根因：** 两个函数独立写入 snapshots，设计上有隐含耦合但未统一
**影响：** 低——snapshot 功能本身能工作，只是设计略有混乱
**修复方案：** 保持现状即可，这是低优先级问题

---

### 2.3 模块 B: `lib/task_protocol.py`

**文件存在性：** ✅ 存在

**TaskDefinition 字段对比（方案 vs 实现）：**

| 方案字段 | 实现字段 | 状态 |
|---------|---------|------|
| `task_id` | `task_id` ✅ | |
| `created_at` | `created_at` ✅ | |
| `objective.type` | `objective: str` ⚠️ | objective 是简单字符串而非对象 |
| `objective.metric` | `metric: MetricConfig` ⚠️ | metric 名称在 MetricConfig 而非 objective |
| `objective.target` | `metric.threshold` ✅ | 映射正确 |
| `dataset.type` | `dataset: DatasetConfig` ⚠️ | 缺少 type 字段 |
| `dataset.path` | `dataset.path` ✅ | |
| `dataset.vocab_size` | ❌ 缺失 | |
| `dataset.max_seq_len` | ❌ 缺失 | |
| `constraints.max_time_per_run_minutes` | `budget.experiment_duration_seconds` ✅ | 字段名不同但语义等价 |
| `constraints.max_iterations` | `budget.max_experiments` ✅ | |
| `constraints.editable_files` | ❌ 缺失 | |
| `constraints.frozen_files` | ❌ 缺失 | |
| `constraints.metric_target` | `metric.threshold` ✅ | |
| `program_md_overrides.focus_areas` | ❌ 缺失 | |
| `program_md_overrides.forbidden_changes` | ❌ 缺失 | |
| `program_md_overrides.hints` | ❌ 缺失 | |
| `checkpoint_interval` | ❌ 缺失 | |
| `result_format` | ❌ 缺失 | |

#### 问题 B-1：`program_md_overrides` 缺失（focus_areas / forbidden_changes / hints）
**类型：** 功能缺失
**描述：** 方案要求 `TaskDefinition` 包含 `program_md_overrides` 字段，用于在生成 `program.md` 时注入 AI 的研究重点、禁止事项和提示。当前的 `generate_program_md` 没有这些来源。
**根因：** `TaskDefinition` 设计时遗漏了 `program_md_overrides`
**影响：** ml-intern 无法通过 `task-config` 下发 focus_areas/forbidden_changes/hints，导致 AI 研究方向缺少引导
**修复方案：**
```python
# 在 task_protocol.py 的 TaskDefinition 中添加：

@dataclass
class ProgramMdOverrides:
    focus_areas: list[str] = field(default_factory=list)
    forbidden_changes: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)

@dataclass
class TaskDefinition:
    ...
    program_md_overrides: ProgramMdOverrides = field(default_factory=ProgramMdOverrides)
    checkpoint_interval: int = 10
    editable_files: list[str] = field(default_factory=lambda: ["train.py"])
    frozen_files: list[str] = field(default_factory=lambda: ["prepare.py"])
```

#### 问题 B-2：`dataset` 缺少 `vocab_size` 和 `max_seq_len`
**类型：** 功能缺失
**描述：** Architecture 的 `dataset` spec 包含 `vocab_size` 和 `max_seq_len`，但 `DatasetConfig` 只有 `name`, `path`, `train_split`, `val_split`。
**根因：** `DatasetConfig` 设计不完整
**影响：** 训练脚本无法从 task config 知道 vocab size 和 seq len，必须依赖文件名解析（`data/train_{vocab}_{seqlen}.bin`）这种不可靠的方式
**修复方案：**
```python
@dataclass
class DatasetConfig:
    name: str
    path: str
    type: str = "binary"  # 新增
    vocab_size: int = 8192  # 新增
    max_seq_len: int = 1024  # 新增
    train_split: int = 0
    val_split: int = 0
```

#### 问题 B-3：`objective` 是简单字符串而非结构化对象
**类型：** 接口不一致
**描述：** 方案中 `objective.type` 和 `objective.metric` 是分开字段，当前 `objective: str` 是扁平的。不过 `MetricConfig` 已经包含 `name` 和 `direction`，所以 `objective` 的信息实际分散存在。
**根因：** 设计时为简化而合并字段
**影响：** 低——功能上等价的，只是结构不同
**修复方案：** 建议保持当前实现（简化），但需在文档中注明映射关系

#### 问题 B-4：`TaskResult.best_result` 结构过于简单
**类型：** 功能缺失
**描述：** 方案中 `best_result` 包含 `train_py_sha`, `metric`, `iteration`, `improvements` 等字段，实际只有 `experiment_id`, `val`, `params`。
**根因：** 实现时未完成完整字段
**影响：** 无法追踪改进历史（每次 iteration 的变化）
**修复方案：**
```python
@dataclass
class BestResult:
    experiment_id: str
    metric: float
    iteration: int
    params: dict
    improvements: list[dict] = field(default_factory=list)
    train_py_sha: Optional[str] = None

@dataclass
class TaskResult:
    ...
    best_result: Optional[BestResult] = None  # 而非 Optional[dict]
```

#### 问题 B-5：`progress_reporter.py` 缺少 `doom_loop_warning`、`stuck_streak`、`recent_experiments`
**类型：** 功能缺失
**描述：** 方案的 `ProgressReport` 包含 doom loop 检测相关字段，当前实现完全缺失。
**根因：** 实现时跳过了高级功能
**影响：** 无法检测连续失败并预警
**修复方案：** 见 Module D

#### 问题 B-6：`results/{task_id}.json` 缺少 `completed_at` → `finished_at` 映射正确但缺少 `statistics.total_wall_clock_minutes`、`success_rate`
**类型：** 功能缺失
**描述：** 方案中 `statistics` 包含 `total_wall_clock_minutes`、`success_rate`，当前 summary 只有基本计数。
**根因：** 实现时遗漏
**影响：** 结果报告缺少统计摘要
**修复方案：**
```python
# 在 autoresearch_run.py 的 run_experiment_loop 中，result.summary 补充：
summary={
    "total_experiments": len(store.experiments),
    "accepted": sum(1 for e in store.experiments if e.get("accepted")),
    "rejected": sum(1 for e in store.experiments if not e.get("accepted")),
    "failed": sum(1 for e in store.experiments if e.get("error")),
    "total_duration_minutes": round(total_duration_minutes, 1),
    "total_wall_clock_minutes": round(total_duration_minutes, 1),  # 新增（与上面等价）
    "success_rate": round(
        sum(1 for e in store.experiments if e.get("accepted")) / max(len(store.experiments), 1), 3
    ),  # 新增
},
```

---

### 2.4 模块 C: `lib/experiment_store.py`

**文件存在性：** ✅ 存在

#### 问题 C-1：`add_experiment` 硬编码 minimize 方向
**类型：** 实现错误（严重）
**描述：** `add_experiment` 中 `val < self.best_val` 硬编码为 minimize，但方案要求根据 `task.metric.direction` 决定是 minimize 还是 maximize。
**根因：** `ExperimentStore` 未存储 direction 信息，`add_experiment` 未接受 direction 参数
**影响：** maximize 任务会得到完全错误的 accept/reject 决策

**修复方案：**
```python
@dataclass
class ExperimentStore:
    task_id: str
    workdir: Path
    direction: str = "minimize"  # 新增：接受 "minimize" 或 "maximize"
    best_val: Optional[float] = None
    best_params: Optional[dict] = None
    best_experiment_id: Optional[str] = None
    experiments: list[dict] = field(default_factory=list)
    ...

    def add_experiment(
        self,
        experiment_id: str,
        params: dict,
        metrics: dict,
        accepted: bool,
        duration_seconds: Optional[float] = None,
        error: Optional[str] = None,
    ) -> bool:
        ...
        # Determine if this updates best
        val = metrics.get("val", metrics.get("val_bpb", None))
        updated = False

        if val is not None and accepted:
            if self.best_val is None:
                updated = True
            elif self.direction == "minimize":
                updated = val < self.best_val
            else:  # maximize
                updated = val > self.best_val

            if updated:
                self.best_val = val
                self.best_params = params
                self.best_experiment_id = experiment_id

        self.save()
        return updated
```

同时修改 `autoresearch_run.py` 中创建 ExperimentStore 的地方：
```python
# run_experiment_loop 中
minimize = task.metric.direction.value == "minimize"
store = ExperimentStore(
    task_id=task.task_id,
    workdir=workspace,
    direction=task.metric.direction.value,  # 新增
).load()
```

#### 问题 C-2：原子写入实现正确，但 `os.fdopen` + `fsync` 在 macOS 上可能不生效
**类型：** 实现警告
**描述：** `save()` 使用 `tempfile.mkstemp` + `os.fdopen` + `os.fsync` + `os.replace` 实现原子写入，但 macOS 的 APFS 上 `fsync` 可能不保证数据落盘（只是元数据同步）。对于实验记录这种中等重要性的数据可以接受。
**根因：** 平台兼容性问题
**影响：** 极低概率的数据丢失风险
**修复方案：** 可接受现状，或在关键任务前添加 `os.fsync(os.replace)` 的额外 fsync

---

### 2.5 模块 D: `lib/progress_reporter.py`

**文件存在性：** ✅ 存在

#### 问题 D-1：`ProgressReport` dataclass 字段不完整
**类型：** 功能缺失
**描述：** 缺少以下方案要求的字段：
- `doom_loop_warning: bool`
- `stuck_streak: int`
- `recent_experiments: list[dict]`
- `estimated_time_remaining_minutes: Optional[float]`
- `best_metric_so_far: float`（当前用 `best_val`）
- `best_iteration: int`（当前用 `best_experiment_id`）

**根因：** 实现时跳过了高级 doom-loop 检测功能
**影响：** ml-intern 无法收到 doom-loop 预警，可能浪费算力在无效搜索上

**修复方案：**
```python
@dataclass
class ProgressReport:
    task_id: str
    status: str  # "running" | "completed" | "failed"
    experiment_index: int
    max_experiments: int
    best_val: Optional[float] = None
    best_params: Optional[dict] = None
    best_experiment_id: Optional[str] = None
    last_accepted: bool = False
    last_val: Optional[float] = None
    progress_pct: float = 0.0
    elapsed_minutes: Optional[float] = None
    error: Optional[str] = None
    # 新增字段
    doom_loop_warning: bool = False
    stuck_streak: int = 0
    recent_experiments: list = field(default_factory=list)
    estimated_time_remaining_minutes: Optional[float] = None
    best_metric_so_far: Optional[float] = None
    best_iteration: Optional[int] = None
```

#### 问题 D-2：缺少 doom_loop 检测逻辑
**类型：** 功能缺失
**描述：** `ProgressReporter` 未实现连续 rejected 实验的计数和 doom-loop 预警。
**根因：** 实现时未包含此功能
**影响：** 同 D-1

**修复方案：**
```python
class ProgressReporter:
    def __init__(self, task_id: str):
        ...
        self._streak = 0  # 新增

    def report(self, ...):
        ...
        # Doom loop detection: 5+ consecutive rejects
        self._streak = (self._streak + 1) if not last_accepted else 0
        doom_warning = self._streak >= 5
        
        recent = reporter._recent_experiments[-5:] if hasattr(reporter, '_recent_experiments') else []
        
        # Estimate remaining time
        if elapsed_minutes and experiment_index > 0:
            avg_time = elapsed_minutes / experiment_index
            remaining = avg_time * (self._max_experiments - experiment_index)
        else:
            remaining = None
        
        self._write(ProgressReport(
            ...
            doom_loop_warning=doom_warning,
            stuck_streak=self._streak,
            recent_experiments=recent,
            estimated_time_remaining_minutes=remaining,
            best_metric_so_far=best_val,
            best_iteration=...,  # 需要从 experiment_id 提取
        ))
```

---

### 2.6 模块 E: `ml_intern/autoresearch_manager.py`

**文件存在性：** ✅ 存在

#### 问题 E-1：`launch` 未真正创建 sub-agent
**类型：** 功能缺失（严重）
**描述：** 方案的 `launch` 应调用 `sessions_spawn` 创建真正的 sub-agent，但当前实现只做了：
1. 写入 `tasks/{task_id}.json`
2. 获取锁
3. 返回 task_id

没有真正启动 sub-agent 进程。这实际上是 ml-intern 的核心集成点，必须完成。
**根因：** 实现时回避了 sub-agent 启动的复杂性
**影响：** 任务无法真正在后台自动运行，ml-intern 调用 `launch()` 后任务就"丢失"了

**修复方案：**
```python
def launch(self, config: AutoResearchConfig) -> str:
    ...
    # Store active task info
    self.active_tasks[task_id] = {
        "config": config,
        "lock_path": str(lock_path),
        "launched_at": time.time(),
    }

    # === 关键补充：启动 sub-agent ===
    # 注意：这需要 ml-intern 的 sessions_spawn 接口
    # 以下是伪代码，实际接入 ml-intern 时需要调用其实例的 spawn 方法
    try:
        from openclaw import sessions_spawn
        sessions_spawn(
            task=f"Run autoresearch for task {task_id}",
            runtime="subagent",
            command=[
                str(self.workspace / "scripts" / "autoresearch_run.py"),
                "--task-config", str(self.workspace / "tasks" / f"{task_id}.json"),
                "--workspace", str(self.workspace / "workdir" / task_id),
            ],
            cwd=str(self.workspace),
        )
        self.active_tasks[task_id]["subagent_launched"] = True
    except ImportError:
        # Fallback: ml-intern will handle sub-agent launch externally
        self.active_tasks[task_id]["subagent_launched"] = False
        pass

    return task_id
```

#### 问题 E-2：缺少 `monitor` 方法实现
**类型：** 功能缺失
**描述：** 方案中 `AutoResearchManager` 有 `async def monitor(self, task_id: str)` 方法，但当前实现缺失。
**根因：** 实现时跳过了
**影响：** 无法向 ml-intern 提供主动干预（干预 best_params、early stop 等）能力
**修复方案：** 见 E-1 修复方案中的框架，实际 monitor 功能需要 ml-intern 侧配合

---

### 2.7 模块 F: `base/train_base.py`

**文件存在性：** ✅ 存在

#### 问题 F-1：SEARCH REGION 标记正确但训练循环是假的
**类型：** 实现错误（严重）
**描述：** `train_base.py` 中的 `train_step` 和 `evaluate` 函数都是 stub——`train_step` 返回随机 `loss`，`evaluate` 返回随机 `val_bpb`，没有真正的模型训练。这使得整个实验循环在真实数据上完全无效。
**根因：** 可能是 demo 阶段故意为之，但未标注为 stub
**影响：** AI 修改超参数后看不到任何真实效果差异，所有 accept/reject 都是基于随机噪声

**修复方案（短期）：** 在文件开头添加明确的 STUB 标注：
```python
"""
Base train.py template for ml-research-loop.
AI agent modifies only the SEARCH REGION.

⚠️  WARNING: This file contains a STUB implementation for demo/development.
   The train_step() and evaluate() functions use synthetic/random data.
   Before production use, replace with real model training code.
   See: base/train_base.py:TRAIN_IMPL_STATUS = "stub"
"""
TRAIN_IMPL_STATUS = "stub"  # "stub" | "real"
```

**修复方案（长期）：** 提供真正的 PyTorch 训练循环，基于 TinyStories 数据集。

#### 问题 F-2：SEARCH REGION 中的常量不是真实超参数空间
**类型：** 实现问题
**描述：** SEARCH REGION 中有 `WINDOW_SIZE = 512` 但注释说 "AI should NOT modify"，与 region 的 "AI modifies ONLY this section" 矛盾。
**根因：** 设计混乱
**影响：** AI 可能修改不应该修改的东西
**修复方案：**
```python
# 将 WINDOW_SIZE 等不变常量移到 region 外部：
# ======= AUTORESEARCH SEARCH REGION START =======
LR = 0.001
BATCH_SIZE = 32
DEPTH = 4
DIM = 256
DROPOUT = 0.1
WEIGHT_DECAY = 0.01
# ======= AUTORESEARCH SEARCH REGION END =======

# Constants (do not modify)
WINDOW_SIZE = 512  # Fixed: architectural constraint
VOCAB_SIZE = 8192  # Fixed: dataset property
MAX_SEQ_LEN = 256   # Fixed: dataset property
```

---

### 2.8 模块 G: `scripts/generate_program_md.py`

**文件存在性：** ✅ 存在

**功能完整性：** ✅ 基本正确

**模板内容对比：**

| 方案要求 section | 实现 | 状态 |
|-----------------|------|------|
| `## Objective` | ✅ 有 | |
| `## Dataset` | ✅ 有 | |
| `## Constraints` | ✅ 有 | |
| `## Focus Areas` | ❌ 来源缺失 | program_md_overrides 缺失导致无法注入 |
| `## Forbidden Changes` | ❌ 来源缺失 | 同上 |
| `## Hints` | ❌ 来源缺失 | 同上 |
| `"Start now. Analyze train.py first."` | ✅ 有 | |

**问题：** 由于 `TaskDefinition` 缺少 `program_md_overrides` 字段，`generate_program_md` 无法接收 focus_areas/forbidden_changes/hints。修复 B-1 后，此问题自动解决。

---

### 2.9 模块 H: `tests/unit/`

**文件存在性：** ✅ 存在

#### 问题 H-1：缺少 `progress_reporter.py` 的单元测试
**类型：** 测试缺失
**描述：** `tests/unit/` 下没有 `test_progress_reporter.py`
**根因：** 未编写
**影响：** `ProgressReporter` 的 doom_loop 检测等新功能没有测试覆盖

**修复方案：** 添加 `test_progress_reporter.py`：
```python
# tests/unit/test_progress_reporter.py
import pytest
from lib.progress_reporter import ProgressReporter, ProgressReport
from lib.task_protocol import ensure_dirs, RESULTS_DIR

def test_init_and_report(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_RESEARCH_LOOP_ROOT", str(tmp_path))
    from lib import task_protocol
    task_protocol.RESULTS_DIR = tmp_path / "results"
    ensure_dirs()
    
    reporter = ProgressReporter(task_id="test-001")
    reporter.init(max_experiments=50)
    
    reporter.report(
        experiment_index=5,
        best_val=0.85,
        best_params={"lr": 0.001},
        best_experiment_id="exp-5",
        last_accepted=True,
        last_val=0.85,
        elapsed_minutes=10.0,
    )
    
    progress = task_protocol.read_progress("test-001")
    assert progress["experiment_index"] == 5
    assert progress["best_val"] == 0.85
    assert progress["progress_pct"] == 10.0

def test_complete(tmp_path, monkeypatch):
    ...

def test_fail(tmp_path, monkeypatch):
    ...
```

#### 问题 H-2：缺少 `autoresearch_run.py` 的集成测试
**类型：** 测试缺失
**描述：** `autoresearch_run.py` 的核心逻辑（`modify_train_hyperparams`, `parse_training_output`, `run_experiment_loop`）没有单元测试。
**根因：** 核心逻辑依赖文件系统状态，难以单独测试
**影响：** 重构时无法回归检测
**修复方案：** 添加 `tests/integration/test_autoresearch_run.py`（需要真实文件系统 fixture）

---

## 三、关键问题优先级排序

### 🔴 高优先级（必须修复，否则系统无法正常工作）

1. **C-1: `ExperimentStore` 硬编码 minimize 方向** — maximize 任务完全失效
2. **F-1: `train_base.py` 训练循环是 stub** — 整个实验循环结果无效
3. **E-1: `launch` 未创建 sub-agent** — 任务无法真正运行

### 🟡 中优先级（功能不完整，但有 workaround）

4. **B-1: `program_md_overrides` 缺失** — AI 缺少研究方向引导
5. **D-1/D-2: doom_loop 检测缺失** — 可能浪费算力
6. **A-1: metric 解析过于宽泛** — 可能导致错误 accept/reject
7. **B-4: `best_result` 结构过于简单** — 无法追踪改进历史

### 🟢 低优先级（改进建议）

8. **B-2: dataset 缺少 vocab_size/max_seq_len** — 依赖不可靠的文件名解析
9. **H-1/H-2: 缺少部分单元测试**
10. **目录结构不符合架构文档** — 实际功能等效，路径约定不同

---

## 四、修复执行计划

### Phase 1: 核心修复（立即执行）
1. 修复 `ExperimentStore` 的 direction 问题（C-1）
2. 标注 `train_base.py` 为 stub（F-1）或提供真实实现
3. 补充 `program_md_overrides` 到 `TaskDefinition`（B-1）

### Phase 2: ml-intern 集成（需要 ml-intern 侧配合）
4. 补充 `AutoResearchManager.launch` 的 sub-agent 启动逻辑（E-1）
5. 实现 `monitor` 方法（E-2）

### Phase 3: 增强功能
6. 添加 doom_loop 检测（D-1/D-2）
7. 修复 metric 解析（A-1）
8. 补充 dataset vocab_size/max_seq_len（B-2）

### Phase 4: 测试覆盖
9. 添加 `test_progress_reporter.py`（H-1）
10. 添加 `test_autoresearch_run.py` 集成测试（H-2）

---

## 五、已验证正常的功能

- ✅ 所有 19 个现有单元测试通过
- ✅ `ExperimentStore` 原子写入实现正确
- ✅ `task_protocol.py` 的基础 JSON 读写协议正确
- ✅ `generate_program_md.py` 模板生成逻辑正确
- ✅ `sample_hyperparameters.py` 的超参采样逻辑正确
- ✅ `SEARCH REGION` 标记格式正确（`# ======= AUTORESEARCH SEARCH REGION START =======`）
- ✅ `autoresearch_run.py` 的 CLI 参数解析正确（`--task-config` 支持）
- ✅ `ProgressReporter.init/report/complete/fail` 基础方法实现完整
- ✅ `ml_intern/tools/run_autoresearch.py` 的工具注册接口设计合理

---

*本修复方案基于 ARCHITECTURE.md v0.1（2026-04-27），共发现 15 个问题，其中高优先级 3 个。*

---

## 第一阶段：ml-intern 集成开发笔记

### 预研发现

#### 1. smolagents Tool 接口
- **Tool 基类**在 `smolagents/tools.py`（安装位置：`.venv/lib/python3.13/site-packages/smolagents/`）
- **定义方式**：继承 `Tool` 类，实现 `forward()` 方法，设置类属性 `name`, `description`, `inputs`, `output_type`
- **inputs 格式**：`dict[str, dict[str, str | type | bool]]`，每个 input 是 `{"type": "string", "description": "..."}`，type 可为 `"string" | "integer" | "number" | "boolean" | "file"` 等
- **output_type**：字符串，如 `"string"`, `"integer"`
- **forward 方法签名**：`def forward(self, param1: type1, param2: type2, ...) -> output_type`
- 验证在类级别通过 `validate_arguments()` 自动执行

示例：
```python
from smolagents import Tool

class MyTool(Tool):
    name = "my_tool"
    description = "Does something"
    inputs = {
        "task_id": {"type": "string", "description": "The task identifier"},
        "objective": {"type": "string", "description": "What to optimize"},
    }
    output_type = "string"

    def forward(self, task_id: str, objective: str) -> str:
        # actual implementation
        return json.dumps({"task_id": task_id, "status": "ok"})
```

#### 2. 当前 AutoResearchManager 实现
- `launch()` 使用 `_spawn_autoresearch_subagent()` 调用 `sessions_spawn`，返回 `session_key`
- `monitor(session_key)` 通过 `_query_subagent_status()` 查询 session 状态 + 读取 `progress.json`
- `get_status(task_id)` 读取 `results/<task_id>-progress.json`
- `get_result(task_id)` 读取 `results/<task_id>.json`
- `wait_for_completion()` 轮询 `get_result()` 直到超时

#### 3. 当前 Tool 接口（run_autoresearch.py）
- 提供了 `get_tool_spec()` 返回 dict 格式的 tool spec，**不是** smolagents Tool 类
- 实际 handler 是普通 Python 函数（`run_autoresearch_handler` 等）
- ml-intern 需要自己处理 tool 注册和参数映射

#### 4. 任务配置格式（demo-mnist-001.json）
- 必需字段：`task_id`, `objective`, `dataset.path`, `metric.name/direction`, `budget`
- hyperparameter_space 是 dict[str, HyperparamSpace]，每个 param 有 `type`, `min/max/values`
- 可序列化/反序列化 via `TaskDefinition.from_dict()` / `to_dict()`

#### 5. results/ 输出格式
- `results/<task_id>.json`：包含 `best_result`, `experiments[]`, `summary`, `finished_at`
- `results/<task_id>-progress.json`：包含 `status`, `experiment_index`, `best_val`, `best_params`

### 当前实现的局限

1. **run_autoresearch.py 不是真正的 smolagents Tool**：只是 dict spec + handler functions，ml-intern 需要自行包装
2. **AutoResearchManager.launch() 是同步的**：返回 task_id 后 sub-agent 异步运行，但 ml-intern 无法获得直接的异步 handle
3. **没有真正的 monitor 干预机制**：只能被动读取 progress.json，无法主动注入新的 best_params 或 early stop
4. **smolagents 未安装**：项目 pyproject.toml 依赖中没有 smolagents，需通过 uv 安装

### 第一阶段具体实现步骤建议

#### Step 1：创建 smolagents Tool 封装类
将 `ml_intern/tools/run_autoresearch.py` 中的 handler 函数包装为真正的 smolagents `Tool` 子类：

```python
from smolagents import Tool

class RunAutoresearchTool(Tool):
    name = "run_autoresearch"
    description = "..."  # from current DESCRIPTION
    inputs = {
        "objective": {"type": "string", "description": "..."},
        "dataset_path": {"type": "string", "description": "..."},
        "task_id": {"type": "string", "description": "..."},
        # ... 其他可选参数
    }
    output_type = "string"

    def forward(
        self,
        objective: str,
        dataset_path: str,
        task_id: str = None,
        metric_name: str = "val_bpb",
        metric_direction: str = "minimize",
        metric_target: float = None,
        max_experiments: int = 50,
        max_duration_minutes: int = 120,
        experiment_duration_seconds: int = 300,
        hyperparameter_space: dict = None,
        base_train_py_path: str = None,
    ) -> str:
        from ml_intern.autoresearch_manager import create_autoresearch_task
        result_task_id = create_autoresearch_task(...)
        return json.dumps({"task_id": result_task_id, "status": "launched", ...})
```

#### Step 2：创建 Status 和 Result Tool
同样将 `get_autoresearch_status_handler` 和 `get_autoresearch_result_handler` 包装为 Tool 类。

#### Step 3：确认 ml-intern 的 Tool 注册机制
需要确认 ml-intern 如何注册 Tool——是接受 Tool 子类实例，还是只接受 dict spec？
- 如果接受 Tool 实例：直接注册上述类
- 如果只接受 dict spec：继续用 `get_tool_spec()` dict，但需要额外的 marshal 层

#### Step 4：处理异步结果返回
smolagents Tool 的 `forward()` 是同步的，但 sub-agent 执行是异步的。当前设计是：
1. `forward()` 返回 task_id（立即返回）
2. 调用方通过 `get_autoresearch_status` 轮询结果

这是合理的设计，不需要改变。

#### Step 5：添加 smolagents 到 pyproject.toml
```toml
dependencies = [
    "torch>=2.0.0",
    "numpy>=1.24.0",
    "smolagents>=1.0.0",
]
```

### 关键依赖确认
- smolagents 已通过 uv 安装到 `.venv`，`uv run python` 可用
- `sessions_spawn` 从 `openclaw` 导入（在 `_spawn_autoresearch_subagent` 中）
- `WORKSPACE_ROOT` 通过环境变量 `ML_RESEARCH_LOOP_ROOT` 或默认路径设置

---
*预研完成：2026-04-27*
