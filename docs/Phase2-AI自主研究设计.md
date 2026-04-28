# Phase 2 — AI 自主研究能力设计

> **角色**：Architect（架构师）
> **日期**：2026-04-27
> **背景**：Phase 1 完成 ml-intern 集成，Phase 3 完成 checkpoint + 告警 + 异常恢复。当前 `autoresearch_run.py` 是**超参采样循环**（随机采样 → 训练 → accept/reject），目标升级为**AI 自主研究循环**（AI 分析 → 提出改进 → 训练验证）

---

## 0. 问题陈述

### 0.1 当前循环 vs 目标循环

**当前循环**（随机采样，无智能）：
```
sample_hyperparams() → 修改 train.py → 训练 → accept/reject
```
AI 每次随机采样超参，不分析为什么某个方向有效或无效。

**目标循环**（AI 驱动研究）：
```
analyze(train.py + program.md + 实验历史 + metrics 趋势)
  → propose_change(LLM 调用)     # "depth 8→10 可能提升 val_bpb"
  → modify_train.py(LLM 建议)
  → train()
  → evaluate()
  → accept/reject + 记录改动原因
```

### 0.2 核心差距

| 维度 | 当前（随机采样） | 目标（AI 自主研究） |
|------|-----------------|-------------------|
| 改动来源 | 随机采样 | LLM 基于上下文分析 |
| 改动类型 | 仅超参（LR、DIM 等） | 超参 + 架构 + 训练策略 |
| 决策依据 | 简单 accept/reject | 记录改动原因，LLM 参考历史 |
| 方向性 | 无方向，随机探索 | 有方向，基于实验结果驱动 |
| 失败学习 | 不记录原因 | 记录失败原因，LLM 避免重复 |

---

## 1. 整体架构

### 1.1 四大核心组件

```
AI 自主研究循环
├── ResearchAnalyzer    — 分析 train.py、实验历史、metrics 趋势
├── ChangeProposer      — 调用 LLM 提出改进建议
├── ChangeExecutor      — 将 LLM 建议转化为 train.py 代码修改
└── ExperimentLoop      — 整合上述组件，形成"分析→提议→执行→验证"循环
```

### 1.2 架构图

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    ExperimentLoop                        │
                    │                                                           │
                    │  while not done:                                          │
                    │    1. analyze() → 上下文 (train.py + 历史)              │
                    │    2. propose() → LLM 建议                               │
                    │    3. execute() → 修改 train.py                          │
                    │    4. train()   → 训练模型                                │
                    │    5. evaluate() → 解析 metrics                          │
                    │    6. accept/reject + 记录实验历史                        │
                    │    7. update_experiment_history()                        │
                    └─────────────────────────────────────────────────────────┘
                                          │
          ┌──────────────────────────────┼──────────────────────────────┐
          │                              │                              │
          ▼                              ▼                              ▼
┌─────────────────┐          ┌─────────────────────┐          ┌─────────────────┐
│ResearchAnalyzer │          │   ChangeProposer    │          │  ChangeExecutor │
│                 │          │                     │          │                 │
│ 分析:           │─────────▶│ 调用 MiniMax LLM:   │─────────▶│ 解析 LLM 建议    │
│ - train.py      │  上下文   │ - 分析上下文         │  建议文本 │ - 生成 patch    │
│ - program.md    │          │ - 提出具体改动       │          │ - 安全验证       │
│ - 实验历史       │          │ - 解释改动原因       │          │ - 回滚机制       │
│ - metrics 趋势   │          │                     │          │                 │
└─────────────────┘          └─────────────────────┘          └─────────────────┘
```

### 1.3 数据流

```
train.py + program.md + experiments.json + progress.json
        │
        ▼
  ResearchAnalyzer
        │ 分析报告 (analyze_report)
        ▼
  ChangeProposer (LLM MiniMax-M2.7)
        │ 改动建议 (change_proposal)  ← {change_type, target, value, reason}
        ▼
  ChangeExecutor
        │ 修改后的 train.py
        ▼
  run_training() + evaluate()
        │ 结果 {val_bpb, accepted, change_record}
        ▼
  ExperimentLoop 记录到 experiments.json
        │
        └──▶ 下一轮 analyze() 可看到本轮结果
```

---

## 2. 核心组件详解

### 2.1 ResearchAnalyzer

**职责**：分析当前 train.py、实验历史、metrics 趋势，生成 LLM 可理解的上下文。

**输入**：
- `train.py` — 当前可修改的训练脚本
- `program.md` — 研究目标与约束
- `experiments.json` — 历史实验记录（每次的 params、metrics、accepted、error）
- `progress.json` — 实时进度（best、doom_loop streak）

**输出**（`AnalyzeResult`）：
```python
@dataclass
class AnalyzeResult:
    current_code_summary: str       # train.py 关键结构摘要
    experiment_history_summary: str # 历史实验趋势
    metrics_trend: str              # metrics 走向分析
    promising_directions: list[str] # 有前景的方向（供 LLM 参考）
    risk_directions: list[str]      # 高风险方向（已失败过的）
    focus_suggestion: str            # 建议 LLM 关注什么
```

**分析维度**：
1. **代码结构分析**：当前 SEARCH REGION 的超参、架构特点
2. **实验历史分析**：哪些改动曾经有效/无效
3. **指标趋势分析**：val_bpb 是下降还是平台期
4. **收敛性判断**：是否进入 doom_loop

```python
class ResearchAnalyzer:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.train_py = workspace / "train.py"
        self.experiments_file = workspace / "experiments.json"
        self.progress_file = RESULTS_DIR / f"{workspace.name}-progress.json"

    def analyze(self) -> AnalyzeResult:
        train_summary = self._analyze_train_py()
        history_summary = self._analyze_history()
        trend = self._analyze_trend()
        promising, risky = self._analyze_directions(history_summary, trend)
        focus = self._suggest_focus(promising, risky, trend)

        return AnalyzeResult(
            current_code_summary=train_summary,
            experiment_history_summary=history_summary,
            metrics_trend=trend,
            promising_directions=promising,
            risk_directions=risky,
            focus_suggestion=focus,
        )

    def _analyze_train_py(self) -> str:
        """解析 SEARCH REGION，生成代码摘要。"""
        content = self.train_py.read_text(encoding="utf-8")
        # 提取 SEARCH REGION
        # 解析超参变量
        # 生成结构化摘要

    def _analyze_history(self) -> str:
        """从 experiments.json 提取趋势。"""
        store = ExperimentStore(task_id=workspace.name, workdir=self.workspace)
        store.load()
        # 生成自然语言摘要：哪些改动产生了 improvement
        # 例如："exp-003: depth 4→8, val_bpb 1.23→1.15, improvement=True"
        # 例如："exp-007: lr 1e-3→1e-4, val_bpb 无改善, rejected"

    def _analyze_trend(self) -> str:
        """分析指标走向（下降/平台/上升）。"""
        # 比较最近 5 个实验的 val_bpb 趋势

    def _analyze_directions(self, history, trend) -> tuple[list, list]:
        """从历史中提取有前景/高风险方向。"""
        # 统计：depth 增大时 val_bpb 的变化趋势
        # 统计：哪些参数改动后经常被 reject

    def _suggest_focus(self, promising, risky, trend) -> str:
        """生成建议关注方向的自然语言。"""
```

### 2.2 ChangeProposer

**职责**：调用 LLM，基于 ResearchAnalyzer 的分析结果，提出具体的代码改动建议。

**LLM 选择**：
- 主模型：**MiniMax-M2.7**（已在 OpenClaw 配置，直接通过 OpenClaw 会话调用）
- 备用：**OpenAI GPT-4o**（通过 `requests` 调用）

**调用方式**：
- 通过 OpenClaw 的 `sessions_spawn` 创建临时子会话调用 LLM
- 或通过 `exec` + `curl` 直接调用 MiniMax API

**输入**：
- AnalyzeResult（来自 ResearchAnalyzer）
- 改动约束（SEARCH REGION 范围、安全约束）

**输出**（`ChangeProposal`）：
```python
@dataclass
class ChangeProposal:
    change_type: str           # "hyperparam" | "architecture" | "training_strategy"
    target: str                # 改动的变量或位置，例如 "DEPTH"
    current_value: str          # 当前值
    proposed_value: str        # 建议值
    reason: str                # 改动原因（让 LLM 解释思考过程）
    confidence: float          # 置信度 0-1
    llm_model: str             # 调用的模型
    llm_prompt_tokens: int
    llm_response_tokens: int
```

**Prompt 设计**：

```
你是一个 ML 研究助手。当前任务是最小化 val_bpb（越低越好）。

## 当前 train.py SEARCH REGION
```python
# ======= AUTORESEARCH SEARCH REGION START =======
LR = 0.001
BATCH_SIZE = 32
DEPTH = 4
DIM = 256
WINDOW_SIZE = 512
DROPOUT = 0.1
WEIGHT_DECAY = 0.01
# ======= AUTORESEARCH SEARCH REGION END =======
```

## 实验历史
exp-001: baseline, val_bpb=1.23
exp-002: DEPTH 4→8, val_bpb=1.15, improvement=True
exp-003: LR 1e-3→1e-4, val_bpb=1.18, improvement=False (轻微恶化)
exp-004: DIM 256→512, val_bpb=1.08, improvement=True

## 当前 best: val_bpb=1.08 (exp-004)

## 分析结论
- depth 增大通常有效（4→8 带来改进）
- 继续增大 depth 可能仍有空间
- LR 调小反而恶化，当前 LR=1e-3 已是最优
- 指标目前处于平台期

## 约束
1. 每次只改一个方向
2. 改动必须可逆（保留能回滚的代码）
3. 改动后必须有明确评估标准
4. 不要改动 SEARCH REGION 之外的代码
5. 改动必须是具体的、可执行的

## 请提出一个改动建议

输出格式（JSON）：
{
  "change_type": "hyperparam|architecture|training_strategy",
  "target": "变量名或代码位置",
  "current_value": "当前值",
  "proposed_value": "建议值",
  "reason": "改动原因，解释你的思考过程",
  "confidence": 0.0-1.0
}
```

### 2.3 ChangeExecutor

**职责**：将 ChangeProposal 转化为 train.py 的实际修改，并验证修改有效。

**关键要求**：
- **原子性**：每次只应用一个改动
- **可逆性**：改动前保存当前 train.py（通过 snapshot）
- **验证**：修改后检查 train.py 语法正确

```python
class ChangeExecutor:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.train_py = workspace / "train.py"

    def execute(self, proposal: ChangeProposal) -> "ExecutionResult":
        """
        将 ChangeProposal 应用于 train.py。
        返回 ExecutionResult 包含是否成功、错误信息等。
        """
        # 1. 读取当前 train.py
        content = self.train_py.read_text(encoding="utf-8")

        # 2. 根据 change_type 生成修改
        if proposal.change_type == "hyperparam":
            modified_content = self._apply_hyperparam(content, proposal)
        elif proposal.change_type == "architecture":
            modified_content = self._apply_architecture(content, proposal)
        elif proposal.change_type == "training_strategy":
            modified_content = self._apply_training_strategy(content, proposal)
        else:
            return ExecutionResult(
                success=False,
                error=f"Unknown change_type: {proposal.change_type}",
            )

        # 3. 验证语法
        if not self._validate_syntax(modified_content):
            return ExecutionResult(
                success=False,
                error="修改后 train.py 语法错误",
                rollback=True,
            )

        # 4. 写入
        self.train_py.write_text(modified_content, encoding="utf-8")

        # 5. 记录改动
        change_record = {
            "change_type": proposal.change_type,
            "target": proposal.target,
            "from": proposal.current_value,
            "to": proposal.proposed_value,
            "reason": proposal.reason,
            "confidence": proposal.confidence,
        }

        return ExecutionResult(success=True, change_record=change_record)

    def _apply_hyperparam(self, content, proposal) -> str:
        """应用超参修改。例如 DEPTH = 4 → DEPTH = 8。"""
        # 查找 SEARCH REGION 中的对应行
        # 替换为新值
        pattern = rf"({re.escape(proposal.target)}\s*=\s*)[^\n]+"
        replacement = rf"\g<1>{proposal.proposed_value}"
        return re.sub(pattern, replacement, content, count=1)

    def _apply_architecture(self, content, proposal) -> str:
        """
        应用架构修改。
        例如：在 transformer 后面加一层 LayerNorm
        或：改变 nhead 数量
        """
        # Architecture 修改比超参修改复杂，需要解析代码结构
        # 使用 AST 或正则表达式

    def _apply_training_strategy(self, content, proposal) -> str:
        """
        应用训练策略修改。
        例如：AdamW → Muon，或添加 cosine annealing
        """
        # 替换 optimizer 定义
        # 或添加 lr_scheduler 定义
```

### 2.4 ExperimentLoop（改造版）

**职责**：整合上述三个组件，形成完整的"分析→提议→执行→验证"循环。

```python
class AIExperimentLoop:
    """
    AI 驱动的实验循环。
    替代 autoresearch_run.py 中的随机采样循环。
    """

    def __init__(
        self,
        task: TaskDefinition,
        workspace: Path,
        llm_provider: LLMProvider,  # MiniMax 或 OpenAI
        max_llm_calls_per_experiment: int = 3,  # 每个实验最多尝试 3 次 LLM 建议
    ):
        self.task = task
        self.workspace = workspace
        self.llm_provider = llm_provider
        self.max_llm_calls = max_llm_calls_per_experiment

        self.analyzer = ResearchAnalyzer(workspace)
        self.executor = ChangeExecutor(workspace)
        self.store = ExperimentStore(task_id=task.task_id, workdir=workspace).load()
        self.reporter = ProgressReporter(task_id=task.task_id)
        self.checkpoint_mgr = CheckpointManager(task.task_id)
        self.alert_mgr = AlertManager(task.task_id)

    def run(self) -> TaskResult:
        """
        运行 AI 自主研究循环。
        替代 run_experiment_loop() 中的采样循环。
        """
        # ... checkpoint 恢复逻辑（同 Phase 3）...

        for exp_idx in range(start_idx, max_experiments):
            # ── 阶段 1：分析 ────────────────────────────────────────────
            analyze_result = self.analyzer.analyze()

            # ── 阶段 2：提议（可能需要多轮）───────────────────────────
            proposal = None
            for attempt in range(self.max_llm_calls):
                try:
                    proposal = self._propose_change(analyze_result, attempt)
                    if proposal and proposal.confidence >= 0.5:
                        break
                except Exception as e:
                    if attempt == self.max_llm_calls - 1:
                        # 兜底：使用随机采样
                        proposal = self._fallback_to_random_sample()
                    continue

            if not proposal:
                proposal = self._fallback_to_random_sample()

            # ── 阶段 3：执行 ───────────────────────────────────────────
            exec_result = self.executor.execute(proposal)
            if not exec_result.success:
                # LLM 建议失败，尝试下一个
                continue

            # ── 阶段 4：训练 ───────────────────────────────────────────
            metrics = self._run_training(experiment_id)
            if not metrics:
                self._record_experiment(proposal, exec_result.change_record,
                                        accepted=False, error="训练失败")
                continue

            # ── 阶段 5：评估 ───────────────────────────────────────────
            current_val = metrics.get(self.task.metric.name)
            accepted = self._evaluate(current_val)

            # ── 阶段 6：记录 ───────────────────────────────────────────
            self._record_experiment(
                proposal=proposal,
                change_record=exec_result.change_record,
                metrics=metrics,
                accepted=accepted,
            )

            # ── 阶段 7：更新上下文 ─────────────────────────────────────
            self._update_context(proposal, current_val, accepted)

            # ── checkpoint + 告警（同 Phase 3）────────────────────────
            self._save_checkpoint(exp_idx)
            self._check_doom_loop()

            if self._should_stop():
                break

        return self._finalize_result()

    def _propose_change(self, analyze_result, attempt: int) -> Optional[ChangeProposal]:
        """调用 LLM 生成改动建议。"""
        # 构建 prompt（包含 AnalyzeResult）
        prompt = self._build_propose_prompt(analyze_result, attempt)

        # 调用 MiniMax LLM
        response = self.llm_provider.generate(prompt)

        # 解析 JSON 响应
        return self._parse_proposal_response(response, analyze_result)

    def _build_propose_prompt(self, analyze_result: AnalyzeResult, attempt: int) -> str:
        """构建 LLM prompt。"""
        # 根据 attempt 调整策略：
        # - attempt=0: 保守方向（已有成功经验的参数范围）
        # - attempt=1: 中等风险（参数空间内的未知区域）
        # - attempt=2: 探索方向（大胆假设）

    def _parse_proposal_response(self, response: str, analyze_result: AnalyzeResult) -> ChangeProposal:
        """解析 LLM 响应，提取 ChangeProposal。"""
        # 尝试 JSON 解析
        # 如果失败，使用正则提取关键信息
        # 验证改动是否在 SEARCH REGION 范围内
```

---

## 3. LLM 集成方案

### 3.1 LLM 选择

| 模型 | 用途 | 说明 |
|------|------|------|
| **MiniMax-M2.7** | 主模型 | 已在 OpenClaw 配置，成本低 |
| **OpenAI GPT-4o** | 备用 | 更高智能，当 MiniMax 效果差时使用 |

### 3.2 MiniMax 调用

**方式**：通过 OpenClaw sessions_spawn 创建临时子会话调用 LLM

```python
class MiniMaxLLMProvider:
    """
    通过 OpenClaw 会话调用 MiniMax LLM。
    """
    API_KEY = os.environ.get("MINIMAX_API_KEY")
    API_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"

    def __init__(self, model: str = "MiniMax-M2.7"):
        self.model = model

    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
        """
        调用 MiniMax API 生成文本。

        Args:
            prompt: 用户 prompt
            system: 系统 prompt（可选）
            max_tokens: 最大生成 token 数

        Returns:
            LLM 生成的文本
        """
        import requests

        headers = {
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system} if system else None,
                {"role": "user", "content": prompt},
            ].filter(None),
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }

        resp = requests.post(self.API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        return data["choices"][0]["message"]["content"]
```

**OpenClaw sessions_spawn 方式**（备用）：

```python
def call_llm_via_openclaw(prompt: str, system_prompt: str = "") -> str:
    """通过 OpenClaw sessions_spawn 调用 LLM。"""
    from openclaw import sessions_spawn

    result = sessions_spawn(
        task=f"""
        你是一个 ML 研究助手。请根据以下信息提出一个超参改动建议：

        {prompt}

        直接输出 JSON 格式的建议，不要有其他文字。
        """,
        mode="run",
        runtime="subagent",
    )
    return result
```

### 3.3 MiniMax API 集成到 autoresearch_run.py

在 `scripts/autoresearch_run.py` 中添加 LLM 调用支持：

```python
# 在 autoresearch_run.py 顶部添加
from lib.llm_providers import MiniMaxLLMProvider

# 在 run_experiment_loop() 中，当需要 AI 建议时
llm_provider = MiniMaxLLMProvider(model="MiniMax-M2.7")
analyzer = ResearchAnalyzer(workspace)
proposal = analyzer.propose_with_llm(llm_provider)
```

---

## 4. 改动协议设计

### 4.1 改动类型分类

| 类型 | 描述 | 示例 |
|------|------|------|
| `hyperparam` | 超参修改（SEARCH REGION 内） | `DEPTH = 4 → 8` |
| `architecture` | 架构修改（模型结构层面） | `nhead 4 → 8`，`添加 LayerNorm` |
| `training_strategy` | 训练策略修改 | `AdamW → Muon`，`添加 cosine annealing` |

### 4.2 改动约束（Safety Protocol）

```
每次实验只允许一个改动。
改动必须满足：
1. 范围约束：只能修改 SEARCH REGION 内的变量（超参）
   或 SEARCH REGION 附近的架构代码（需精确识别行号）
2. 大小约束：单次数值改动不超过当前值的 4 倍或 1/4 倍
   （防止过大的跳变）
3. 可逆性约束：每次改动前自动保存 snapshot（已有此机制）
4. 类型约束：Architecture 和 TrainingStrategy 改动需要额外验证

禁止的改动：
1. 删除核心组件（如删除 attention 层）
2. 将梯度裁剪阈值设为 0
3. 减少训练 step 数到 10 以下
4. 任何导致 train.py 无法启动的修改
```

### 4.3 改动执行流程

```
ChangeProposer 产出 ChangeProposal
        │
        ▼
ChangeExecutor 验证提议是否合法
        │
   合法？ ──否──▶ 返回错误，重新提议
        │
       是
        ▼
保存当前 train.py 快照
        │
        ▼
应用修改到 train.py
        │
        ▼
语法验证（python -m py_compile train.py）
        │
   通过？ ──否──▶ 回滚到快照，返回错误，重新提议
        │
       是
        ▼
返回 ExecutionResult（success=True, change_record）
```

### 4.4 Architecture 改动扩展 SEARCH REGION

当前 SEARCH REGION 只包含超参。为支持架构修改，需要扩展 SEARCH REGION：

```python
# train.py 中的扩展 SEARCH REGION
# ======= AUTORESEARCH SEARCH REGION START =======
# 超参
LR = 0.001
BATCH_SIZE = 32
DEPTH = 4
DIM = 256

# 架构选项（LLM 可以修改这些）
# NHEAD = 4          # 可选：attention head 数量
# USE_LAYERNORM = True  # 可选：是否使用 pre-norm
# ACTIVATION = "gelu"   # 可选：激活函数
# ======= AUTORESEARCH SEARCH REGION END =======
```

AI 通过注释指示可选的架构参数，LLM 可以取消注释并修改。

---

## 5. 实验历史记录

### 5.1 增强的实验记录格式

在 `experiments.json` 中添加 LLM 相关字段：

```json
{
  "experiment_id": "exp-004",
  "params": {"DEPTH": 8, "DIM": 256},
  "metrics": {"val_bpb": 1.08, "train_loss": 0.52},
  "accepted": true,
  "timestamp": "2026-04-27T14:30:00Z",

  "change_record": {
    "change_type": "hyperparam",
    "target": "DEPTH",
    "from": "4",
    "to": "8",
    "reason": "depth 增大通常能提升模型容量，exp-002 验证了 depth 8 优于 4"
  },

  "llm_info": {
    "model": "MiniMax-M2.7",
    "proposal_attempts": 2,
    "prompt_tokens": 1200,
    "response_tokens": 150,
    "proposal": {
      "change_type": "hyperparam",
      "target": "DEPTH",
      "current_value": "4",
      "proposed_value": "8",
      "reason": "depth 增大通常能提升模型容量，exp-002 验证了 depth 8 优于 4",
      "confidence": 0.85
    }
  },

  "duration_seconds": 280,
  "snapshot_path": "snapshots/exp_001/exp-004/"
}
```

### 5.2 ChangeProposer 历史追踪

在 `ChangeProposer` 中维护一个"改动建议历史"，供 LLM 分析：

```python
class ChangeProposer:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.proposal_history: list[ChangeProposal] = []

    def propose(self, analyze_result: AnalyzeResult) -> ChangeProposal:
        """提出改动建议并记录。"""
        proposal = self._call_llm(analyze_result)
        self.proposal_history.append(proposal)
        return proposal

    def get_context_for_llm(self) -> str:
        """生成供 LLM 参考的历史上下文。"""
        lines = []
        for p in self.proposal_history[-5:]:  # 最近 5 个
            lines.append(
                f"- {p.change_type} {p.target}: {p.current_value}→{p.proposed_value} "
                f"(confidence={p.confidence:.2f}, reason: {p.reason})"
            )
        return "\n".join(lines)
```

### 5.3 实验历史分析（供下一轮 LLM 使用）

```python
def summarize_history_for_llm(store: ExperimentStore) -> str:
    """生成实验历史摘要，供 LLM 作为上下文。"""
    experiments = store.experiments[-10:]  # 最近 10 个

    lines = ["## 实验历史（最近 10 个）"]
    for exp in experiments:
        change = exp.get("change_record", {})
        val = exp.get("metrics", {}).get("val_bpb", "N/A")
        status = "✅" if exp.get("accepted") else "❌"

        change_desc = f"{change.get('target', '?')}: {change.get('from', '?')}→{change.get('to', '?')}"
        lines.append(
            f"{exp['experiment_id']}: {change_desc} | val_bpb={val} {status}"
        )

    return "\n".join(lines)
```

---

## 6. 验证策略设计

### 6.1 三阶段验证方案

```
阶段 1: 流程验证（Mock LLM）
  └── 验证架构正确性（LLM 调用 → 解析 → 修改 → 训练）

阶段 2: 收敛性测试（已知答案）
  └── 验证系统能学到东西（depth 越大越好 → 最终收敛到 depth=10）

阶段 3: 真实实验（MiniMax LLM）
  └── 在真实任务上验证 AI 自主研究能力
```

### 6.2 阶段 1：流程验证（方案 C + Mock LLM）

**目标**：验证 AI 正确调用 LLM、解析建议、修改 train.py、执行训练。

**Mock LLM 设计**：
```python
class MockLLMProvider:
    """
    返回固定"正确"建议的 Mock LLM。
    用于验证流程正确性。
    """

    def __init__(self, fixed_response: dict):
        self.fixed_response = fixed_response

    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
        # 记录调用次数和 prompt
        return json.dumps(self.fixed_response)
```

**测试用例**：

| 测试 | Mock 返回 | 验证点 |
|------|----------|--------|
| T1 | `{"change_type": "hyperparam", "target": "DEPTH", "current_value": "4", "proposed_value": "8", "reason": "test", "confidence": 0.9}` | train.py 的 DEPTH 被修改为 8 |
| T2 | `{"change_type": "hyperparam", "target": "DIM", "current_value": "256", "proposed_value": "512", "reason": "test", "confidence": 0.9}` | train.py 的 DIM 被修改为 512 |
| T3 | `{"change_type": "architecture", "target": "NHEAD", "proposed_value": "8"}` | 架构改动正确应用 |

**验证步骤**：
1. 构造 Mock LLM，返回固定建议
2. 运行 AIExperimentLoop 1 个实验
3. 检查 `experiments.json` 中记录的 change_record
4. 检查 train.py 中的实际修改
5. 检查训练是否正常运行（无 crash）

**测试代码**：
```python
def test_ai_loop_with_mock_llm():
    """测试 AI 循环在 Mock LLM 下正确执行。"""

    # 1. Setup
    mock_llm = MockLLMProvider(fixed_response={
        "change_type": "hyperparam",
        "target": "DEPTH",
        "current_value": "4",
        "proposed_value": "8",
        "reason": "depth 增大可能提升性能",
        "confidence": 0.85,
    })

    task = TaskDefinition(...)
    workspace = Path("workdir/test-ai-loop")
    workspace.mkdir(parents=True, exist_ok=True)
    setup_workdir(task, workspace)

    # 2. Run loop
    loop = AIExperimentLoop(task, workspace, llm_provider=mock_llm)
    result = loop.run()

    # 3. Verify
    assert result.status == TaskStatus.COMPLETED
    store = ExperimentStore(task_id=task.task_id, workdir=workspace).load()
    last_exp = store.experiments[-1]

    assert last_exp["change_record"]["target"] == "DEPTH"
    assert last_exp["change_record"]["to"] == "8"
    assert last_exp["llm_info"]["model"] == "MockLLM"

    # 4. Check train.py actual content
    train_content = (workspace / "train.py").read_text()
    assert "DEPTH = 8" in train_content
```

### 6.3 阶段 2：收敛性测试（方案 B）

**目标**：设计一个已知答案的任务，验证系统能收敛到正确答案。

**任务设计**：
- **假设**：`DEPTH` 越大，val_bpb 越低（性能越好）
- **已知答案**：depth=10 时 val_bpb 最低
- **搜索空间**：`DEPTH` ∈ {4, 6, 8, 10}

**实验设计**：
1. 修改 `base/train_base.py`，使 `DEPTH` 与 val_bpb 强相关
2. 运行 AIExperimentLoop 20 个实验
3. 验证：best 出现在 `DEPTH=10` 附近

**实现方式**（修改 train.py 中的 val_bpb 计算）：
```python
def evaluate(model, val_tensor, ...):
    # 模拟一个 DEPTH 相关的 val_bpb
    # DEPTH=4 → val_bpb=1.5, DEPTH=6 → val_bpb=1.3, ...
    depth = DEPTH  # 从 SEARCH REGION 读取
    base_bpb = 1.8
    depth_bonus = (depth - 4) * 0.1
    val_bpb = base_bpb - depth_bonus + noise()
    return val_bpb
```

这样 AI 只有增大 DEPTH 才是最优方向，系统应该能收敛到 DEPTH=10。

**验证标准**：
- 如果 AI 正确学习，应该最终探索到 DEPTH=10
- 可以计算收敛率：前 10 个实验中 DEPTH 是否呈上升趋势

**测试代码**：
```python
def test_depth_convergence():
    """
    测试 AI 循环是否收敛到 depth=10（已知最优）。
    """
    # 1. 修改 base train 以模拟 DEPTH → val_bpb 关系
    # 2. 运行 20 个实验
    # 3. 收集所有 experiments 的 DEPTH 和 val_bpb
    # 4. 验证 best_result 的 DEPTH == 10

    depths_tried = []
    bpb_values = []

    for exp in store.experiments:
        params = exp.get("params", {})
        metrics = exp.get("metrics", {})
        if "DEPTH" in params and "val_bpb" in metrics:
            depths_tried.append(params["DEPTH"])
            bpb_values.append(metrics["val_bpb"])

    # 验证：depth 越大，val_bpb 越低（趋势正确）
    best_idx = bpb_values.index(min(bpb_values))
    assert depths_tried[best_idx] == 10, f"Expected best DEPTH=10, got {depths_tried[best_idx]}"
```

### 6.4 阶段 3：真实实验

**目标**：在真实任务上验证 AI 自主研究能力（使用真实 MiniMax LLM）。

**测试用例**：
1. 在 TinyStories 数据集上运行完整实验
2. 验证 AI 提出的改动是否有意义
3. 对比 AI 驱动 vs 随机采样的实验结果

**评估指标**：
- 收敛速度：AI 驱动是否比随机采样更快达到目标指标
- 改动质量：AI 提出的改动是否比随机更合理
- 实验效率：平均每个实验的 val_bpb 改善

---

## 7. 与现有代码的集成

### 7.1 改造策略

**保持向后兼容**：当前 `autoresearch_run.py` 的超参采样循环仍然可用，作为 fallback。

**新增 `scripts/ai_autoresearch_run.py`**：AI 驱动的实验循环脚本。

```python
# scripts/ai_autoresearch_run.py

"""
AI 驱动的 autoresearch 实验循环。
使用 LLM 分析 + 提议 + 执行，而非随机采样。
"""

from scripts.autoresearch_run import (
    parse_args,
    setup_workdir,
    run_training,
    parse_training_output,
    ExperimentStore,
    ProgressReporter,
    CheckpointManager,
    AlertManager,
)
from lib.llm_providers import MiniMaxLLMProvider
from lib.research_analyzer import ResearchAnalyzer
from lib.change_proposer import ChangeProposer
from lib.change_executor import ChangeExecutor
from lib.ai_experiment_loop import AIExperimentLoop


def main() -> int:
    args = parse_args()

    # Load task
    task_config_path = Path(args.task_config)
    task_def = read_task(task_config_path.stem)

    workspace = WORKSPACE_ROOT / "workdir" / task_def.task_id
    workspace.mkdir(parents=True, exist_ok=True)
    setup_workdir(task_def, workspace)

    # 选择 LLM Provider
    llm_provider = MiniMaxLLMProvider(
        model=os.environ.get("LLM_MODEL", "MiniMax-M2.7")
    )

    # 运行 AI 驱动的实验循环
    loop = AIExperimentLoop(
        task=task_def,
        workspace=workspace,
        llm_provider=llm_provider,
        max_llm_calls_per_experiment=3,
    )

    result = loop.run()

    print(f"RESULT_FILE={RESULTS_DIR / f'{task_def.task_id}.json'}")
    print(f"STATUS={result.status.value}")

    return 0 if result.status == TaskStatus.COMPLETED else 1
```

### 7.2 关键文件变更

```
ml-research-loop/
├── scripts/
│   ├── autoresearch_run.py          # 不变（向后兼容）
│   ├── ai_autoresearch_run.py       # 新增：AI 驱动入口
│   └── sample_hyperparams.py         # 不变（fallback 使用）
│
├── lib/
│   ├── llm_providers.py              # 新增：LLM Provider 抽象
│   │   ├── MiniMaxLLMProvider
│   │   └── OpenAILLMProvider
│   ├── research_analyzer.py          # 新增：ResearchAnalyzer
│   ├── change_proposer.py            # 新增：ChangeProposer
│   ├── change_executor.py            # 新增：ChangeExecutor
│   └── ai_experiment_loop.py         # 新增：AIExperimentLoop
│
├── base/
│   └── train_base.py                 # 扩展 SEARCH REGION 支持架构改动
│
└── docs/
    └── Phase2-AI自主研究设计.md      # 本文档
```

### 7.3 ml-intern 集成

在 ml-intern 的 `autoresearch_manager.py` 中添加 AI 模式选项：

```python
class AutoResearchManager:
    def launch(self, config: AutoResearchConfig) -> str:
        if config.ai_mode:
            # 使用 AI 驱动的实验循环
            script = "scripts/ai_autoresearch_run.py"
        else:
            # 使用传统随机采样循环
            script = "scripts/autoresearch_run.py"

        # ... spawn sub-agent with script ...
```

---

## 8. 实施计划

### Phase 2 实施分为 4 个阶段：

| 阶段 | 内容 | 预计工期 |
|------|------|----------|
| **P2-1** | 实现 LLM Provider（MiniMax + OpenAI） + Mock 测试框架 | 1 天 |
| **P2-2** | 实现 ResearchAnalyzer + ChangeProposer + ChangeExecutor | 2 天 |
| **P2-3** | 实现 AIExperimentLoop，整合所有组件 | 1 天 |
| **P2-4** | 验证：Mock 测试 → 收敛性测试 → 真实实验 | 2 天 |

**总工期：6 个工作日**

### P2-1 详细任务

1. **LLM Provider 抽象**
   - 创建 `lib/llm_providers.py`
   - 实现 `MiniMaxLLMProvider`
   - 实现 `OpenAILLMProvider`（备用）
   - 实现 `MockLLMProvider`（测试用）

2. **Prompt 模板库**
   - 创建 `lib/prompts.py`
   - 实现 `build_propose_prompt()` 函数

3. **Mock 测试框架**
   - 在 `tests/` 中创建 `test_ai_loop.py`
   - 实现 MockLLM 测试用例

### P2-2 详细任务

1. **ResearchAnalyzer**
   - 实现 `_analyze_train_py()`：提取 SEARCH REGION 超参
   - 实现 `_analyze_history()`：生成历史实验摘要
   - 实现 `_analyze_trend()`：分析指标趋势
   - 实现 `_analyze_directions()`：提取有前景/高风险方向

2. **ChangeProposer**
   - 实现 `_call_llm()`：调用 MiniMax API
   - 实现 `_parse_proposal_response()`：解析 JSON 响应
   - 实现 `proposal_history` 追踪

3. **ChangeExecutor**
   - 实现 `_apply_hyperparam()`：超参修改
   - 实现 `_apply_architecture()`：架构修改
   - 实现 `_validate_syntax()`：语法验证
   - 实现 `_rollback()`：回滚机制

### P2-3 详细任务

1. **AIExperimentLoop 核心循环**
   - 实现 `run()` 方法
   - 实现 `_propose_change()` 循环（最多 3 次尝试）
   - 实现 fallback 到随机采样

2. **Checkpoint 集成**
   - 在 AIExperimentLoop 中集成 CheckpointManager
   - 支持 kill -9 恢复

3. **AlertManager 集成**
   - doom_loop 检测（已有）
   - 新增：`llm_failure` 告警（LLM 调用失败）

### P2-4 详细任务

1. **Mock LLM 测试**
   - 运行 `test_ai_loop_with_mock_llm()`
   - 验证 train.py 修改正确

2. **收敛性测试**
   - 修改 train_base.py 以模拟 DEPTH → val_bpb 关系
   - 运行 20 个实验
   - 验证收敛到 depth=10

3. **真实实验**
   - 在 TinyStories 数据集上运行
   - 对比 AI 驱动 vs 随机采样

---

## 9. 关键风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM 返回格式不稳定 | 无法解析 JSON | 实现 robust 解析，fallback 到随机采样 |
| LLM 幻觉改动 | 改动无效或破坏代码 | ChangeExecutor 验证语法，snapshot 回滚 |
| LLM 调用成本高 | 费用超出预算 | 限制 `max_llm_calls=3`，使用 Mock 测试 |
| 改动过于频繁 | 探索效率低 | 每次只改一个方向，有明确的 accept/reject |
| doom_loop 无法检测 | 系统陷入局部最优 | AlertManager 触发告警，通知 DM |
| Architecture 改动破坏训练 | train.py 无法运行 | 语法验证 + snapshot 回滚 + 运行前检查 |

---

## 10. 文件清单

### 新增文件

```
lib/llm_providers.py          # LLM Provider 抽象（MiniMax/OpenAI/Mock）
lib/research_analyzer.py      # ResearchAnalyzer
lib/change_proposer.py        # ChangeProposer
lib/change_executor.py        # ChangeExecutor
lib/ai_experiment_loop.py     # AIExperimentLoop
lib/prompts.py                # LLM Prompt 模板

scripts/ai_autoresearch_run.py  # AI 驱动实验循环入口

tests/test_ai_loop.py           # AI 循环测试
tests/test_mock_llm.py          # Mock LLM 测试
tests/test_convergence.py       # 收敛性测试

docs/Phase2-AI自主研究设计.md    # 本文档
```

### 修改文件

```
scripts/autoresearch_run.py    # 添加 LLM 集成代码（保持向后兼容）
base/train_base.py             # 扩展 SEARCH REGION 支持架构改动
lib/experiment_store.py         # 添加 llm_info 字段
```

---

*文档版本：v0.1*
*创建时间：2026-04-27*
*角色：Architect*