# ML Research Loop 🦾

> AI 自主 ML 研究引擎 — 让 AI 替你做 ML 实验，24/7 不间断。

**融合 Hugging Face ml-intern + Karpathy autoresearch，构建研究-验证-部署全链路闭环。**

---

## 核心特性

- 🔬 **科学验证循环** — 固定预算实验，accept/reject 决策，可审计的实验日志
- 🤖 **AI 驱动研究** — LLM 生成假设，autoresearch 验证，科学迭代
- ⚡ **高效迭代** — 5 分钟/次实验，夜间可跑，早上收成果
- 📊 **实验记录** — 本地 JSON 结果、进度、checkpoint 与快照
- 🔧 **可扩展** — 插件式工具系统，支持自定义指标和工作流

---

## 快速开始

### 安装

```bash
git clone https://github.com/your-username/ml-research-loop.git
cd ml-research-loop
uv sync
```

### 运行演示（合成数据）

```bash
make run-demo
```

如果当前 shell 没有 `uv`，可以使用本机 Python 加载 `.venv` 依赖：

```bash
make test-python
make run-fresh-demo-python
```

### 启动 MCP 服务（Codex / Claude）

项目的最终入口是一个本地 stdio MCP server，Codex、Claude Code、Claude Desktop 等 MCP
客户端都可以通过同一个服务调用 ML 实验循环：

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 scripts/mcp_server.py
```

也可以在可编辑安装后使用 console script：

```bash
ml-loop-mcp
```

当前暴露 4 个 MCP 工具：

| 工具 | 说明 |
|------|------|
| `run_fresh_demo` | 新建隔离 runtime root，跑通一个可重复的合成数据 demo |
| `run_autoresearch` | 读取任务 JSON，启动 autoresearch 实验循环 |
| `get_experiment_status` | 读取 `results/<task_id>-progress.json` |
| `get_experiment_result` | 读取 `results/<task_id>.json` |

本机 Codex 配置示例（`~/.codex/config.toml`）：

```toml
[mcp_servers.mlResearchLoop]
command = "/opt/homebrew/Caskroom/miniforge/base/bin/python3"
args = ["/Users/dm/Documents/ml-research-loop/scripts/mcp_server.py"]
cwd = "/Users/dm/Documents/ml-research-loop"
startup_timeout_sec = 10
tool_timeout_sec = 3600

[mcp_servers.mlResearchLoop.env]
PYTHONPATH = "/Users/dm/Documents/ml-research-loop:/Users/dm/Documents/ml-research-loop/.venv/lib/python3.13/site-packages"
ML_RESEARCH_LOOP_PYTHON = "/opt/homebrew/Caskroom/miniforge/base/bin/python3"
```

Claude Code 配置示例：

```bash
claude mcp add-json ml-research-loop '{
  "type": "stdio",
  "command": "/opt/homebrew/Caskroom/miniforge/base/bin/python3",
  "args": ["/Users/dm/Documents/ml-research-loop/scripts/mcp_server.py"],
  "env": {
    "PYTHONPATH": "/Users/dm/Documents/ml-research-loop:/Users/dm/Documents/ml-research-loop/.venv/lib/python3.13/site-packages",
    "ML_RESEARCH_LOOP_PYTHON": "/opt/homebrew/Caskroom/miniforge/base/bin/python3"
  }
}'
```

Claude Desktop 可在 `claude_desktop_config.json` 中加入：

```json
{
  "mcpServers": {
    "ml-research-loop": {
      "type": "stdio",
      "command": "/opt/homebrew/Caskroom/miniforge/base/bin/python3",
      "args": ["/Users/dm/Documents/ml-research-loop/scripts/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/Users/dm/Documents/ml-research-loop:/Users/dm/Documents/ml-research-loop/.venv/lib/python3.13/site-packages",
        "ML_RESEARCH_LOOP_PYTHON": "/opt/homebrew/Caskroom/miniforge/base/bin/python3"
      }
    }
  }
}
```

### 创建自己的实验

```bash
# 1. 准备任务配置
cat > tasks/my-experiment.json << 'EOF'
{
  "task_id": "my-experiment-001",
  "objective": "minimize val_bpb on my dataset",
  "dataset": {
    "name": "my-dataset",
    "path": "data/train_8192_256.bin"
  },
  "metric": {
    "name": "val_bpb",
    "direction": "minimize",
    "threshold": 0.85
  },
  "hyperparameter_space": {
    "lr": {"type": "log_uniform", "min": 1e-5, "max": 1e-2},
    "depth": {"type": "choice", "values": [4, 6, 8, 10, 12]},
    "dim": {"type": "choice", "values": [128, 256, 384, 512]}
  },
  "budget": {
    "max_experiments": 50,
    "max_duration_minutes": 120,
    "experiment_duration_seconds": 300
  },
  "base_code": {
    "train_py_url": "file:///path/to/ml-research-loop/base/train_base.py",
    "prepare_py_url": "file:///path/to/ml-research-loop/base/prepare.py"
  }
}
EOF

# 2. 运行实验
uv run python scripts/autoresearch_run.py \
    --task-config tasks/my-experiment.json \
    --workspace ./workdir/my-experiment-001 \
    --verbose

# 3. 查看结果
cat results/my-experiment-001.json
```

---

## 项目结构

```
ml-research-loop/
├── base/                         # 基础代码（AI 不可修改）
│   ├── train_base.py            # train.py 模板
│   └── prepare.py               # 数据准备脚本
│
├── scripts/                      # 可执行脚本
│   ├── autoresearch_run.py      # 主入口
│   ├── generate_program_md.py   # 动态生成 program.md
│   └── sample_hyperparams.py    # 超参采样
│
├── ml_intern/                    # ml-intern 集成层
│   ├── autoresearch_manager.py  # sub-agent 管理
│   └── tools/
│       └── run_autoresearch.py  # smolagents 工具
│
├── lib/                          # 共享库
│   ├── task_protocol.py         # JSON 协议定义
│   ├── experiment_store.py      # 实验记录存储
│   ├── progress_reporter.py      # 进度报告
│   ├── metrics.py               # 指标计算
│   └── exceptions.py            # 自定义异常
│
├── templates/
│   └── program_template.md      # program.md 模板
│
├── tasks/                        # 任务定义（运行时）
├── results/                      # 实验结果（运行时）
├── snapshots/                    # 代码快照（运行时）
└── workdir/                     # 工作目录（运行时）
```

---

## 核心概念

### 实验循环

```
提出假设 → 修改 train.py → 训练 5 分钟 → 评估 val_bpb → 接受/回滚 → 记录日志 → 重复
```

### 任务协议

任务通过 JSON 文件定义：
- `tasks/<task_id>.json` — 任务下发
- `results/<task_id>.json` — 结果回报
- `results/<task_id>-progress.json` — 实时进度

### Hyperparameter Space

支持多种采样策略：
- `uniform` — 均匀分布浮点数
- `log_uniform` — 对数均匀分布
- `choice` — 离散选择
- `q_uniform` / `q_log_uniform` — 量化均匀

---

## 与 ml-intern 集成

```python
from ml_intern.tools.run_autoresearch import run_autoresearch_handler

# 在 ml-intern 中注册工具
tool_router.register(run_autoresearch_handler)

# 使用工具
task_id = run_autoresearch(
    objective="minimize val_bpb on TinyStories",
    dataset_path="data/train_8192_256.bin",
    metric_name="val_bpb",
    max_experiments=50,
    hyperparameter_space={
        "lr": {"type": "log_uniform", "min": 1e-5, "max": 1e-2},
        "depth": {"type": "choice", "values": [4, 6, 8, 10, 12]},
    }
)
```

---

## 文档

- [项目背景书](项目背景书.md) — 市场分析、竞争格局、商业模式
- [ARCHITECTURE.md](ARCHITECTURE.md) — 技术架构设计
- [FIX_PROPOSAL.md](FIX_PROPOSAL.md) — 当前代码审查与修复建议
- [docs/Phase2-AI自主研究设计.md](docs/Phase2-AI自主研究设计.md) — AI 自主研究循环设计
- [docs/Phase3-可靠性设计.md](docs/Phase3-可靠性设计.md) — checkpoint、告警与恢复设计

---

## Codex 插件

> 让任何 Codex 用户用自然语言驱动 ML 实验循环

Codex 插件位于 `codex_plugin/` 目录，提供三个工具：

| 工具 | 说明 |
|------|------|
| `run_ml_experiment` | 启动 ML 实验循环 |
| `get_ml_experiment_status` | 查询实验进度 |
| `get_ml_experiment_results` | 获取实验结果 |

**自然语言驱动示例：**

```
"帮我把 MNIST 模型的 val_bpb 降到 0.8 以下"
```

Codex 会将 `run_ml_experiment` 等工具暴露给 LLM，用户无需编写代码即可驱动 ML 实验。

详细文档请参考 [codex_plugin/README.md](codex_plugin/README.md)。

---

## 许可证

MIT
