# ML Research Loop 🦾

> AI 自主 ML 研究引擎 — 让 AI 从研究探索到实验验证形成闭环。

**融合 Hugging Face ml-intern + Karpathy autoresearch，构建研究-验证-部署全链路闭环。**

---

## 核心特性

- 🔬 **保留 autoresearch 能力** — `program.md` 驱动、固定预算实验、`train.py` 可编辑、accept/reject 决策、可审计日志
- 🤖 **保留 ml-intern 能力** — 论文、HF docs/datasets、GitHub、工具路由、研究计划与假设生成
- 🔁 **融合闭环** — ml-intern 产生研究假设，autoresearch 做实验验证，结果再反馈给下一轮研究
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
make run-fusion-demo-python
```

### 启动 MCP 服务（Codex / Claude）

MCP 是 Codex、Claude Code、Claude Desktop 等客户端调用本项目的入口；项目核心仍是
ml-intern 的研究探索能力和 autoresearch 的固定预算验证循环融合：

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 scripts/mcp_server.py
```

也可以在可编辑安装后使用 console script：

```bash
ml-loop-mcp
```

当前暴露基础实验工具和融合工作流工具：

| 工具 | 说明 |
|------|------|
| `run_fresh_demo` | 新建隔离 runtime root，跑通一个可重复的合成数据 demo |
| `run_autoresearch` | 读取任务 JSON，启动 autoresearch 实验循环 |
| `get_experiment_status` | 读取 `results/<task_id>-progress.json` |
| `get_experiment_result` | 读取 `results/<task_id>.json` |
| `read_paper` | 按 arXiv ID / URL 读取单篇论文，返回 source、evidence snippets、findings、hypotheses |
| `research_task` | 准备 ml-intern 风格的研究任务上下文，并返回 `query_plan`、`findings`、`source_rankings` |
| `propose_hypotheses` | 将研究来源和 `findings` 转成可实验验证的假设，优先使用高相关度来源 |
| `run_hypothesis_experiment` | 对带 hypothesis 的任务运行 autoresearch；可消费 `task_patch` / `recommended_search_space` 继续下一轮 |
| `review_research_results` | 读取并复盘 hypothesis-backed 实验结果，返回 `research_review`、假设支持度、`experiment_strategy`、推荐搜索空间和 `next_task_patch` |

autoresearch 主循环会把已完成实验历史传给 sampler：重复的失败/拒绝参数组合会被惩罚，
已接受的配置会作为局部搜索参考；没有历史时仍保持原来的随机采样行为。
`review_research_results` 会把复盘结果整理成 `next_task_patch`，下一次调用
`run_hypothesis_experiment` 时可直接传入这个 patch：它会更新搜索空间、写入
需要避开的 `sampling_constraints.avoid_params`，按策略收窄下一轮 `budget.max_experiments`，
并把下一轮研究提示和停止条件注入 `program.md`。
同一个复盘结果还会返回结构化 `experiment_strategy`，用于判断下一轮应做局部搜索、
失败调试、重新扩展搜索空间，还是先启动首轮实验。

`run-fusion-demo-python` 是验收路径：它构造一个
ml-intern 风格的 `ResearchBrief`，把 hypothesis 写入任务 JSON 和 `program.md`，
再交给 autoresearch 跑一次固定预算验证。

P4 交付包提供一条更贴近客户端调用的 MCP golden path：

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30
```

Codex、Claude Code、Claude Desktop 的配置模板位于 `examples/mcp/`。
完整接入步骤见 `docs/mcp-client-setup.md`。
发布前验收使用 `docs/release-checklist.md` 和 `scripts/release_check.py`。

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

### 融合边界

本项目不是替换 `ml-intern` 或 `autoresearch`，而是保留两边优势：

- `ml-intern` 负责研究探索：读论文、查 HF docs/datasets、搜索 GitHub、形成可验证假设。
- `autoresearch` 负责实验验证：读取任务与 `program.md`，在固定预算内修改 `train.py`，用统一指标接受或拒绝改动。
- `MCP` 负责外部调用：让 Codex/Claude 以工具方式驱动这个闭环。

### 实验循环

```
研究资料 → 提出假设 → 写入 program.md → 修改 train.py → 固定预算训练 → 评估 val_bpb → 接受/回滚 → 反馈下一轮
```

### 任务协议

任务通过 JSON 文件定义：
- `tasks/<task_id>.json` — 任务下发
- `results/<task_id>.json` — 结果回报
- `results/<task_id>-progress.json` — 实时进度
- `program_md_overrides` — ml-intern 或复盘结果注入的 focus、forbidden changes、hints
- `sampling_constraints.avoid_params` — 下一轮采样时需要避开的失败/拒绝参数组合

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
- [docs/superpowers/plans/2026-04-28-ml-intern-autoresearch-fusion.md](docs/superpowers/plans/2026-04-28-ml-intern-autoresearch-fusion.md) — ml-intern × autoresearch 融合实现计划

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
