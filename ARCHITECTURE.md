# ML Research Loop — 技术架构

> 本文档为 ml-intern × autoresearch 集成方案的技术架构设计。

---

## 一、核心设计决策

### 1.1 为什么用共享文件系统而非消息队列？

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| **文件系统（选中）** | 简单、可视化、兼容沙盒、易调试 | 实时性略差 | ✅ 优先 |
| 消息队列 | 实时性强 | 复杂、需额外部署 | 未来迭代 |

### 1.2 为什么用 per-task sub-agent 而非 long-running agent？

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| **per-task sub-agent（选中）** | 隔离性好、容错强、资源隔离 | 启动开销 | ✅ 优先 |
| long-running agent | 无启动开销 | 状态管理复杂 | 未来迭代 |

### 1.3 为什么 program.md 内嵌生成而非模板替换？

因为 AI 需要看到完整的上下文（任务目标、数据路径、约束条件），简单模板替换无法传递足够的任务意图。

---

## 二、系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                         User / DM                            │
│                    (飞书 / CLI / API)                        │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ↓
┌──────────────────────────────────────────────────────────────┐
│               ml-intern (主 Agent / 编排者)                   │
│                                                              │
│  - 任务分解（研究 → 验证 → 部署）                           │
│  - ToolRouter（HF docs / papers / datasets / GitHub）         │
│  - sessions_spawn（创建 autoresearch sub-agent）              │
│  - event_queue 监听（进度/完成/异常）                        │
│  - 验收 & 部署                                               │
└────────────────────────────┬─────────────────────────────────┘
                             │
        ┌────────────────────┴────────────────────┐
        │                                         │
        ↓                                         ↓
┌─────────────────────────┐        ┌─────────────────────────┐
│  传统 ML 任务            │        │  需要实验迭代的任务      │
│  (直接执行)              │        │  → autoresearch sub-agent │
└─────────────────────────┘        └───────────┬─────────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           ↓                           │
                    │  ┌─────────────────────────────────────────────────┐  │
                    │  │           autoresearch sub-agent                 │  │
                    │  │                                                  │  │
                    │  │  循环（最多 N 次）：                              │  │
                    │  │    1. 读取当前 train.py + program.md             │  │
                    │  │    2. 分析并提出一个改进                         │  │
                    │  │    3. 执行训练（固定预算 5min/次）               │  │
                    │  │    4. 评估指标                                   │  │
                    │  │    5. 接受/回滚 → 记录日志                       │  │
                    │  │    6. 进度上报到 progress.json                   │  │
                    │  │                                                  │  │
                    │  │  完成后写入:                                     │  │
                    │  │    - results/{task_id}.json（最终结果）          │  │
                    │  │    - snapshots/（中间存档）                      │  │
                    │  │                                                  │  │
                    │  └─────────────────────────────────────────────────┘  │
                    │                           │                           │
                    └───────────────────────────┼───────────────────────────┘
                                                │
                                                ↓
                                ┌─────────────────────────────┐
                                │     共享文件系统              │
                                │                             │
                                │  tasks/                     │
                                │    └── {task_id}.json       │  ← 任务下发
                                │                             │
                                │  results/                   │
                                │    ├── {task_id}.json       │  ← 最终结果
                                │    └── {task_id}-progress.json │  ← 实时进度
                                │                             │
                                │  snapshots/                 │
                                │    └── {task_id}/          │  ← 中间存档
                                │        ├── ckpt_10/        │
                                │        ├── ckpt_20/        │
                                │        └── ...             │
                                │                             │
                                └─────────────────────────────┘
```

---

## 三、核心接口设计

### 3.1 任务下发协议 (`tasks/{task_id}.json`)

```json
{
  "task_id": "exp_20260427_001",
  "created_at": "2026-04-27T14:00:00+08:00",
  
  "objective": {
    "type": "minimize",
    "metric": "val_bpb",
    "target": 0.85
  },
  
  "dataset": {
    "path": "/shared/data/load_forecasting_train.bin",
    "type": "binary",
    "vocab_size": 8192,
    "max_seq_len": 1024
  },
  
  "constraints": {
    "max_time_per_run_minutes": 5,
    "max_iterations": 100,
    "editable_files": ["train.py"],
    "frozen_files": ["prepare.py"],
    "metric_target": 0.85
  },
  
  "program_md_overrides": {
    "focus_areas": [
      "attention mechanism variants",
      "layer normalization placement",
      "positional encoding (RoPE, ALiBi)"
    ],
    "forbidden_changes": [
      "disable gradient clipping"
    ],
    "hints": [
      "Consider using gradient clipping with 1.0 norm",
      "AdamW with lr=1e-4 is a safe baseline"
    ]
  },
  
  "checkpoint_interval": 10,
  
  "result_format": "structured"
}
```

### 3.2 结果回报协议 (`results/{task_id}.json`)

```json
{
  "task_id": "exp_20260427_001",
  "status": "completed",
  "completed_at": "2026-04-27T18:30:00+08:00",
  
  "best_result": {
    "train_py_sha": "abc123...",
    "metric": 0.843,
    "iteration": 47,
    "improvements": [
      {"iteration": 2, "change": "depth 8→10", "metric": 0.91},
      {"iteration": 12, "change": "AdamW → Muon", "metric": 0.88},
      {"iteration": 47, "change": "RoPE + window attention", "metric": 0.843}
    ]
  },
  
  "statistics": {
    "total_experiments": 47,
    "total_wall_clock_minutes": 235,
    "accepted_experiments": 12,
    "rejected_experiments": 35,
    "success_rate": 0.255
  },
  
  "final_program_md_sha": "def456...",
  "train_py_best": "base64...",
  
  "snapshots": [
    "snapshots/exp_20260427_001/ckpt_10",
    "snapshots/exp_20260427_001/ckpt_20",
    "snapshots/exp_20260427_001/ckpt_30",
    "snapshots/exp_20260427_001/ckpt_40",
    "snapshots/exp_20260427_001/ckpt_47_best"
  ]
}
```

### 3.3 实时进度协议 (`results/{task_id}-progress.json`)

```json
{
  "task_id": "exp_20260427_001",
  "last_updated": "2026-04-27T16:45:00+08:00",
  
  "current_iteration": 35,
  "max_iterations": 100,
  "progress_percent": 35,
  
  "best_metric_so_far": 0.856,
  "best_iteration": 28,
  
  "recent_experiments": [
    {"iteration": 33, "change": "lr 1e-4 → 8e-5", "metric": 0.862, "accepted": false},
    {"iteration": 34, "change": "layer norm epsilon 1e-5 → 1e-6", "metric": 0.861, "accepted": false},
    {"iteration": 35, "change": "window size 512 → 1024", "metric": 0.856, "accepted": true}
  ],
  
  "doom_loop_warning": false,
  "stuck_streak": 0,
  
  "estimated_time_remaining_minutes": 325
}
```

---

## 四、ml-intern 侧改动

### 4.1 新增工具：`run_autoresearch`

```python
# agent/core/tools.py

ToolSpec(
    name="run_autoresearch",
    description="""Run an autonomous experiment loop to optimize a neural network training script.
    
    Uses fixed time budget (5 min per iteration), single-file editing constraint,
    and metric-based acceptance. Best for: architecture search, optimizer tuning,
    hyperparameter optimization on a fixed dataset.
    
    Returns a task_id for monitoring progress.
    """,
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "dataset_path": {"type": "string"},
            "objective": {"type": "string"},
            "metric_target": {"type": "number"},
            "max_iterations": {"type": "integer", "default": 100},
            "focus_areas": {"type": "array", "items": {"type": "string"}},
            "forbidden_changes": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["task_id", "dataset_path", "objective"]
    },
    handler=run_autoresearch_handler
)
```

### 4.2 sub-agent 管理器

```python
# agent/core/autoresearch_manager.py

class AutoResearchManager:
    
    def launch(self, task_config: dict) -> str:
        """Launch an autoresearch sub-agent for a task."""
        
        # 1. 写入 tasks/{task_id}.json
        # 2. 生成 program.md（动态）
        # 3. sessions_spawn sub-agent
        # 4. 监听 event_queue
        # 5. 返回 task_id
        pass
    
    async def monitor(self, task_id: str):
        """监控进度，可注入干预。"""
        pass
    
    async def get_result(self, task_id: str) -> dict:
        """读取 results/{task_id}.json。"""
        pass
```

---

## 五、autoresearch 侧改动

### 5.1 新增入口：`autoresearch_run.py`

```python
# autoresearch_run.py

"""
autoresearch 的可配置运行入口。
接受 --task-config 解析外部任务，而非硬编码。
"""

import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-config", type=str, required=True)
    args = parser.parse_args()
    
    # 1. 加载任务配置
    config = json.load(open(args.task_config))
    
    # 2. 生成 program.md
    program_md = generate_program_md(config)
    
    # 3. 运行实验循环
    run_experiment_loop(
        program_md=program_md,
        constraints=config["constraints"],
        checkpoint_interval=config.get("checkpoint_interval", 10)
    )

def generate_program_md(config: dict) -> str:
    """根据任务配置动态生成 program.md。"""
    objective = config["objective"]
    overrides = config.get("program_md_overrides", {})
    
    program = f"""# Research Agent Instructions

## Objective
{objective['type']} {objective['metric']} to {objective.get('target', 'as low as possible')}

## Dataset
- Path: {config['dataset']['path']}
- Vocab size: {config['dataset']['vocab_size']}
- Max seq len: {config['dataset']['max_seq_len']}

## Constraints
- ONLY edit `train.py` (do not touch prepare.py)
- Each experiment: {config['constraints']['max_time_per_run_minutes']} minutes max
- Max {config['constraints']['max_iterations']} experiments total
- Target metric: {objective.get('target', 'as low as possible')}

## Focus Areas
{chr(10).join(f"- {area}" for area in overrides.get("focus_areas", []))}

## Forbidden Changes
{chr(10).join(f"- {x}" for x in overrides.get("forbidden_changes", []))}

## Hints
{chr(10).join(f"- {hint}" for hint in overrides.get("hints", []))}

Start now.
"""
    return program
```

---

## 六、program.md 动态生成方案

### 6.1 模板结构

```markdown
# Research Agent Instructions

## Objective
{objective_type} {metric_name} to {target}

## Dataset
- Path: {dataset_path}
- Vocab size: {vocab_size}
- Max seq len: {max_seq_len}

## Constraints
- Only edit `train.py`
- {max_time_minutes} minutes per experiment
- Max {max_iterations} experiments
- Target: {target}

## Focus Areas
{focus_areas}

## Forbidden Changes
{forbidden_changes}

## Hints
{hints}

Start now. Analyze train.py first.
```

### 6.2 任务类型对应的生成策略

| 任务类型 | focus_areas | hints |
|---------|-------------|-------|
| architecture_search | attention variants, norm placement, positional encoding | "Try pre-norm + RoPE first" |
| optimizer_tuning | Muon vs AdamW, lr schedules, weight decay | "lr=1e-4 with cosine schedule is safe" |
| context_length | RoPE extensions, efficient attention, context window | "Start with 2x current context" |
| general | all of the above | "Prioritize high-impact changes first" |

---

## 七、关键文件结构

```
ml-research-loop/
├── ml_intern/                    # ml-intern 集成
│   └── agent/
│       └── core/
│           ├── tools.py          # 新增 run_autoresearch 工具
│           └── autoresearch_manager.py  # sub-agent 管理
│
├── autoresearch/                 # autoresearch 改动
│   ├── autoresearch_run.py       # 新增：可配置入口
│   ├── train.py                  # 核心：AI 修改的文件
│   ├── prepare.py                # 核心：不修改
│   ├── program.md                # 核心：动态生成
│   └── experiment_log.jsonl      # 核心：实验记录
│
├── shared/                       # 共享存储
│   ├── tasks/                   # 任务下发
│   │   └── {task_id}.json
│   ├── results/                 # 结果回报
│   │   ├── {task_id}.json
│   │   └── {task_id}-progress.json
│   └── snapshots/               # 中间存档
│       └── {task_id}/
│           ├── ckpt_10/
│           └── ...
│
└── configs/
    ├── program_templates/       # program.md 模板
    │   ├── architecture_search.md
    │   ├── optimizer_tuning.md
    │   └── general.md
    └── default_constraints.json
```

---

## 八、最小可行实现路径

### Day 1：基础准备
- fork ml-intern + autoresearch 到项目仓库
- 实现 `autoresearch_run.py`（支持 --task-config）
- 验证 autoresearch 能独立运行

### Day 2：ml-intern 集成
- 新增 `run_autoresearch` 工具到 ml-intern
- 实现 `autoresearch_manager.py`
- 端到端调通 ml-intern → autoresearch 任务下发

### Day 3：事件驱动
- 实现 event_queue 监听
- 实现 progress.json 实时更新
- 实现进度展示和中断机制

### Day 4-5：端到端验证
- 在真实数据集上跑完整流程
- 验证日志、存档、报告生成
- 修复 bug，优化用户体验

### 预计工期：5 个工作日（MVP）

---

*文档版本：v0.1*
*创建时间：2026-04-27*
*角色：Architect*
