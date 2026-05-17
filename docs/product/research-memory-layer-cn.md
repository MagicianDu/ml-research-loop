# Research Memory Layer 决策：Graphiti + cognee

> Canonical 目标架构见 `docs/product/target-architecture-cn.md`。本文档只细化 Research Memory Layer 的选型和分阶段交付。

## 决策结论

ML Research Loop 将新增 **Research Memory Layer**，用于让项目积累并复用过去的论文复现经验、实验结果、失败原因、模型配置、patch 记录和调试方法。该层采用 **Graphiti + Cognee** 的组合，但不把二者直接变成默认强依赖。Cognee 仍是 optional experimental adapter，不是默认依赖，不阻塞 beta/stable，也不进入默认 release gate；Graphiti/cognee live smoke 只作为 optional integration evidence。

- **Graphiti**：作为长期关系记忆和时间图谱候选，表达论文、claim、数据集、模型、指标、实验、patch、失败、rollback、artifact 和证据之间的关系。
- **cognee**：作为文档和 artifact 语义检索候选，负责从论文、proof bundle、日志、报告、README、release evidence 和 memory card 中检索可复用上下文。
- **ML Research Loop 自有层**：保留 `ResearchMemoryCard` schema、claim boundary、artifact provenance、MCP tool contract、privacy/sandbox policy 和 release gate。

换句话说，Graphiti 和 cognee 提供记忆基础设施；项目自己的 MCP/Skills/证据体系决定什么可以被记录、如何被检索、何时可用于下一轮实验建议。记忆建议不能直接触发执行，所有代码、超参、训练、归档和 benchmark 动作仍必须走 MCP guardrails。

## 为什么需要这一层

当前项目已经能跑受控实验、生成 proof archive、执行 guarded patch 和输出 release proof bundle，但这些 artifact 主要解决“可审计”和“可复查”。它们还不能充分解决“成长性”：

- 过去复现论文时踩过的坑不能自动进入下一篇论文的计划。
- 已验证过的模型、数据处理、超参和 patch 模式不能系统化复用。
- 失败实验、rollback 和 metric regression 的经验没有形成可查询的知识。
- Codex/Claude 每次接入时主要依赖当前上下文，而不是项目级长期研究经验。

Research Memory Layer 的目标是把一次次研究闭环沉淀成可检索、可审计、可复用的长期记忆。

## 新架构位置

```text
Codex / Claude
  强模型 planner：理解目标、读证据、提出下一轮代码或超参改动

Skills
  固化工具顺序、证据门槛、停止条件和人工确认边界

ML Research Loop MCP Service
  执行 research、experiment、patch、review、proof archive、release gate

Research Memory Layer
  ResearchMemoryCard schema + extraction + retrieval + suggestion + audit
  ├── Graphiti adapter：长期关系图谱和时间序列研究经验
  └── cognee adapter：文档、日志、proof bundle 和 artifact 语义检索

Runtime Artifacts / Proof Archive
  tasks、results、logs、workspace、snapshots、proof bundles、review reports
```

Research Memory Layer 位于 MCP 服务和 runtime artifacts 之间：每次运行结束后，它从 artifacts 中抽取结构化 memory card；下一次规划时，Codex/Claude 可以通过 MCP 工具检索相关记忆，再决定实验或 patch。

## 记忆类型

| 类型 | 内容 | 典型用途 |
| --- | --- | --- |
| Evidence memory | 论文 claim、数据集、代码来源、citation、证据等级 | 判断一个研究假设是否有足够依据 |
| Experiment memory | 数据集、模型、超参、metric、训练命令、资源预算 | 复用有效配置，避免重复低价值试验 |
| Patch memory | code diff、SEARCH REGION、preflight、metric delta、rollback | 判断类似 patch 是否值得再试 |
| Failure memory | 报错、失败分类、恢复动作、最终处理结果 | 快速定位环境、数据、训练和评测问题 |
| Procedure memory | 复现 checklist、调试流程、停止规则、人工审核规则 | 让 Skills 和客户端 planner 使用稳定流程 |

## 当前 MCP 工具

MCP contract 围绕项目自有 schema，而不是暴露 Graphiti/cognee 的原生接口：

- `record_research_memory`：从 review、proof bundle 或手工输入写入 `ResearchMemoryCard`。
- `retrieve_research_memory`：按论文、任务、数据集、metric、失败类型、patch 类型检索记忆。
- `suggest_from_memory`：基于历史成功/失败记录给出下一轮候选 proposal，但不直接执行。
- `promote_memory_card`：把临时记录提升为可复用 procedure 或 playbook。
- `audit_memory_trace`：解释某条建议引用了哪些 memory card、artifact 和证据来源。

这些工具已进入 preview contract，但仍保留现有边界：默认不隐式调用服务端 LLM，不把记忆建议当成已验证结论，不越过 allowed roots 和隐私策略。

## 数据流

1. Codex/Claude 调用 `research_task`、`read_paper`、`run_hypothesis_experiment` 或 reproduction 工具。
2. MCP 服务生成 artifacts：evidence、logs、results、patch report、review report、proof bundle。
3. extraction 层把 artifacts 转成 `ResearchMemoryCard`，写入本地 memory store。
4. Graphiti adapter 记录实体关系和时间演化。
5. cognee adapter 索引文档、日志和 proof bundle 的可检索内容。
6. 下一轮任务开始时，Codex/Claude 调用 memory retrieval 工具获取相关经验。
7. 客户端强模型结合当前论文证据和历史记忆，提出新的实验、patch 或停止决策。
8. MCP 服务继续执行、验证、记录和归档。

## 不能改变的边界

- 记忆层不替代 proof archive；任何对外 claim 仍然必须能回到 artifact、日志、metric 和 review report。
- 记忆层不替代 Codex/Claude 的规划能力；它提供可引用上下文，不自动决定高风险动作。
- Graphiti/cognee 在第一阶段是 adapter candidate，不进入默认最小安装路径。
- 任何私有论文、私有数据、未公开代码或敏感日志进入记忆前，必须经过显式配置和脱敏策略。
- memory suggestion 不能被宣传为“自动保证提升效果”；它只是历史经验驱动的候选建议。

## 分阶段交付

### P16.0 Schema 与离线 memory card

- 定义 `ResearchMemoryCard`、`MemoryEvidenceRef`、`MemoryArtifactRef`、`MemorySuggestion`。
- 从现有 fastText P3/P4/P5 proof artifacts 中抽取离线 memory cards。
- 增加 JSONL/local-store 作为 dependency-free baseline。

验收：不安装 Graphiti/cognee 也能从现有 proof bundle 生成和检索 memory card。

当前状态：已实现 dependency-free local JSONL baseline、fastText release proof extraction、CLI record/retrieve、`scripts/memory_smoke.py` 和 MCP memory tools。

### P16.1 Graphiti/cognee adapter spike

- Graphiti：验证能否表达 paper -> claim -> dataset -> model -> config -> metric -> patch -> failure/rollback 的关系。
- cognee：验证能否索引 docs、proof bundle、review report、logs，并返回可追溯片段。
- 两个 adapter 都必须返回项目统一的 `ResearchMemoryCard` 视图。

验收：同一个 fastText/AG News 记忆查询可以从关系图谱和语义检索两条路径返回，并附 provenance。

当前状态：已提供真实 adapter 调用路径，但仍保持显式 opt-in：

- Graphiti adapter 会把 `ResearchMemoryCard` 转成 JSON episode，并在配置 `ML_RESEARCH_LOOP_GRAPHITI_URI`、`ML_RESEARCH_LOOP_GRAPHITI_USER`、`ML_RESEARCH_LOOP_GRAPHITI_PASSWORD` 或注入 client 后调用 `add_episode` / `search`。
- cognee adapter 会把 `ResearchMemoryCard` 转成文档，调用 `cognee.add`、`cognee.cognify` 和 `cognee.search(..., query_type=CHUNKS)`。
- CLI/MCP 只有在 `--sync-adapters` / `--include-adapters` 或对应 MCP 参数显式打开时才访问 Graphiti/cognee。
- 当前已由 fake-client 单测验证真实 API 调用形态；Graphiti live smoke 已可通过，Cognee 已能进入 ingest/cognify/search pipeline，但本地 `gpt-oss-20b:2` 下 `cognify` 仍可能超时或返回嵌套 `PipelineRunErrored`，因此 Cognee 仍是实验性 adapter。对真实 Neo4j/Graphiti 服务和 Cognee 后端的端到端 live smoke 只作为可选集成验收项。

### P16.2 MCP + Skills 集成

- 增加 memory retrieval MCP 工具。
- 更新 planner、reproduction、experiment-optimizer skills，在实验前检索相似经验，在实验后记录结果。
- 增加 memory trace 到 review 输出和 proof bundle。
- 增加 dependency-free proposal handoff proof：先检索本地 memory store，再输出给 Codex/Claude 审阅的下一轮实验 proposal payload。

验收：Codex/Claude 能在下一轮实验前看到历史成功/失败建议，但执行仍走 guarded patch 和 release gate。

当前状态：MCP contract 已暴露 record/retrieve/suggest/promote/audit；planner、reproduction、optimizer 和 operator skills 已加入记忆检索与记录边界。`scripts/memory_guided_proposal.py` 可从本地 JSONL memory store 生成 `memory-guided-proposal.json` 和 `memory-guided-proposal.md`，其中保留 `memory_provenance`、`claim_boundary`、`executes_tool=false` 和 `official_scores_claimed=false`，用于证明历史记忆可以影响下一轮实验规划，但不会绕过 MCP guardrails 自动执行 patch 或训练。

### P16.3 产品化与发布边界

- 增加 privacy/redaction 配置。
- 增加 memory export/import 和清理策略。
- release check 覆盖 dependency-free baseline；Graphiti/cognee adapter 作为 optional integration check。Graphiti/cognee live smoke 只作为 optional integration evidence，不进入默认 release gate；Cognee 失败不能阻塞 beta/stable。

验收：fresh checkout 不依赖外部记忆服务；高级用户可显式启用 Graphiti+cognee。

当前状态：

- private memory ingestion 已要求显式 opt-in。
- `ResearchMemoryStore.export_cards(...)` 默认会把 private memory 导出为 redacted public card，移除私有 summary、config、artifact path、hash、evidence quote 和 URL。
- `ResearchMemoryStore.import_cards(...)` 默认拒绝 private memory；只有显式 `allow_private=True` 才允许导入。
- `ResearchMemoryStore.cleanup(...)` 和 `ml-loop memory cleanup` 已提供 dependency-free cleanup/retention：支持 `--dry-run`、`--keep-last`、`--memory-type`、`--older-than-days`、`--confirm` 和 `--include-private`。默认不会删除 private memory；实际删除必须显式 `--confirm`，只有同时显式 `--include-private` 才允许 private card 进入清理候选。清理后 JSONL store 仍必须可被 `ResearchMemoryStore.list_cards()` 读取。

安装可选依赖：

```bash
pip install -e ".[memory-graphiti]"
pip install -e ".[memory-cognee]"
pip install -e ".[memory]"
```

显式同步和检索示例：

```bash
ml-loop memory record-fasttext-release \
  --store .memory/research-memory.jsonl \
  --release-manifest <release-proof-manifest.json> \
  --multi-round-report <multi-round-report.json> \
  --review-checklist <release-review-checklist.md> \
  --sync-adapters \
  --adapter graphiti \
  --adapter cognee

ml-loop memory retrieve \
  --store .memory/research-memory.jsonl \
  --query "fastText AG News P@1" \
  --include-adapters \
  --adapter graphiti \
  --adapter cognee

ml-loop memory cleanup \
  --store .memory/research-memory.jsonl \
  --dry-run \
  --keep-last 20 \
  --memory-type failure \
  --json

# 确认 dry-run 输出后，才执行真实删除。
ml-loop memory cleanup \
  --store .memory/research-memory.jsonl \
  --confirm \
  --keep-last 20 \
  --memory-type failure \
  --json
```

## 当前结论

整体架构会发生变化：项目从 “MCP 执行层 + Skills 工作流 + proof archive” 升级为 “MCP 执行层 + Skills 工作流 + Research Memory Layer + proof archive”。但默认职责边界不变：Codex/Claude 仍是强模型 planner，MCP 服务仍是受控执行和证据层，Graphiti+cognee 只作为长期记忆基础设施，不直接替代研究判断。
