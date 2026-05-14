# 混合 MCP 架构要求

## 目标

本项目采用混合架构：Codex/Claude 作为客户端强模型 planner，MCP 服务作为稳定执行器；同时保留服务端 LLM 后端用于无人值守自动实验。下一阶段将新增 Research Memory Layer，用 Graphiti + cognee 作为可选长期记忆基础设施，让过去的论文复现、实验、patch、失败和 proof archive 能被后续任务检索和复用。

## 固定边界

- 默认实验路径不得隐式调用服务端 LLM。`run_autoresearch` 和 `run_hypothesis_experiment` 只负责执行任务、记录结果、返回状态。
- 客户端模型负责理解目标、读论文、选择工具、解释实验结果、决定下一轮代码或超参策略。
- 客户端模型自行生成单参数超参 proposal 时，必须走 `run_client_patch_experiment`
  的 `change_proposal` 契约，由 MCP 校验 SEARCH REGION 和 stale state 后执行。
- 服务端自主优化必须显式使用 `run_ai_autoresearch`，并显式选择 `llm_provider`。
- 执行类 MCP 工具必须遵守路径 sandbox：`runtime_root`、`workspace` 和 `task_config`
  只能位于项目根目录、服务端配置的 `ML_RESEARCH_LOOP_ROOT`，或
  `ML_RESEARCH_LOOP_ALLOWED_ROOTS` 中显式允许的目录内。
- Research Memory Layer 只提供可追溯的历史上下文和候选建议，不替代 proof
  archive、release gate 或 Codex/Claude 的最终规划判断。
- Graphiti/cognee 在第一阶段必须作为可选 adapter，不进入默认最小安装路径；
  MCP contract 应暴露项目自有的 `ResearchMemoryCard` 视图，而不是泄漏外部
  provider 的原生接口。
- 每轮实验结束后，`review_research_results` 必须返回足够给客户端模型继续迭代的 `experiment_state`。
- 新客户端必须先调用 `get_service_manifest`，校验 `contract_version`、
  `schema_versions` 和 `tool_contracts` 后再进入自动规划循环；当前 preview
  合约版本为 `2026-04-30.preview.v1`。

## 上游模式融合规则

AIDE 和 PaperBench 是架构参考，不是替换运行时。后续只能吸收它们的
experiment-tree search、reproduction、rubric 和 grading 模式，并且必须通过
本项目现有 MCP contract、task protocol、runtime artifact layout 和 release
gate 表达。直接依赖上游包、Docker/GPU-first 执行栈、nanoeval/alcatraz，或
把默认 Codex/Claude planner 路径改成服务端 LLM runtime，都需要单独的兼容性
决策，不能作为默认实现进入主路径。

## Research Memory Layer

Research Memory Layer 是新增的产品层，目标是解决项目成长性：过去复现论文的经验、有效模型配置、失败原因、rollback、调试方法和 proof bundle 不应只停留在一次性 artifact 中，而应能在后续任务中被检索、引用和复用。

当前选型为 Graphiti + cognee：

- Graphiti 负责长期关系图谱和时间演化，表达 paper、claim、dataset、model、
  metric、experiment、patch、failure、rollback、artifact 之间的关系。
- cognee 负责文档和 artifact 语义检索，索引论文、日志、proof bundle、review
  report、release evidence 和 memory card。
- ML Research Loop 自己负责 `ResearchMemoryCard` schema、artifact
  provenance、claim boundary、隐私策略、MCP tool contract 和 release gate。

目标工具应包括 `record_research_memory`、`retrieve_research_memory`、
`suggest_from_memory`、`promote_memory_card` 和 `audit_memory_trace`。这些工具
只能返回带来源的候选上下文；真正执行仍必须走 `run_client_patch_experiment`、
`apply_client_code_patch`、reproduction harness 或其他受控 MCP 工具。

## 客户端规划循环

1. 新任务开始时，可先调用 memory retrieval 工具，查询相似论文、任务、数据集、metric、patch 和失败经验。
2. `research_task` / `read_paper` 收集当前研究上下文。
3. `propose_hypotheses` 生成可验证假设。
4. `run_hypothesis_experiment` 执行固定预算实验。
5. `review_research_results` 返回 `research_review` 和 `experiment_state`。
6. 运行结束后，可把 review、proof bundle 和失败记录抽取为 `ResearchMemoryCard`。
7. Codex/Claude 读取 `experiment_state` 和相关 memory trace，决定下一轮：
   - 传入 `next_round.task_patch` 继续局部优化。
   - 如果 `failure_summary.failed_count > 0`，先调用 `get_experiment_logs` 获取日志摘要。
   - 调整搜索空间、预算或停止条件后再次运行。
   - 如果客户端模型自行提出单参数 SEARCH REGION 改动，调用
     `run_client_patch_experiment`，并检查 `patch_execution`。
   - 在具备文件写权限的客户端中修改代码，再调用实验工具验证。
   - 需要无人值守时改用 `run_ai_autoresearch`。
   - 优先使用 `experiment_state.planner_actions` 中排序后的第一项作为默认下一步。

## `experiment_state` 合约

`experiment_state` 是客户端模型的 handoff 数据包，至少包含：

- `planner_handoff`：声明客户端模型和 MCP 服务的职责边界，以及建议下一步工具。
- `best_result` / `summary` / `recent_experiments`：让模型判断当前优化走势。
- `failure_summary`：最近失败原因，避免盲目继续采样。
- `research_evidence_gate`：判断当前研究上下文是否有足够来源、发现和无警告证据。
- `retrieval_diagnostics` / `research_evidence_gate.retrieval_recovery`：解释检索后端失败、空结果、缓存命中和建议恢复动作。
- `current_code.search_region`：当前可调参数区。
- `current_code.program_md_excerpt`：当前实验约束和提示摘要。
- `code_change_plan.next_experiment_plan`：下一轮单参数验证计划，包括目标 metric、候选值、best params、停止条件、安全编辑策略、`proposed_task_patch` 和 `dry_run_validation`。
- `artifacts`：结果、进度、workspace、`train.py`、`program.md`、日志目录路径。
- `planner_actions`：按优先级排序的客户端动作，可直接映射到 `research_task`、`get_experiment_logs`、`run_hypothesis_experiment`，或提示客户端先做文件修正。
- `next_round`：可直接交给下一轮的 `task_patch`、推荐搜索空间和实验策略。

## 验收要求

- MCP 工具列表同时包含客户端编排工具和服务端自主工具。
- `review_research_results` 在没有服务端 LLM 的情况下也能返回 `experiment_state`。
- `experiment_state.planner_actions` 必须能表达补检索、查日志、修数据路径、继续实验四类下一步。
- `run_client_patch_experiment` 必须拒绝 stale `change_proposal.current_value`，
  且有效 proposal 只能以 `task_patch_only` 方式执行单参数验证。
- release check 必须覆盖 MCP stdio smoke、research-to-review golden path、两轮 `task_patch` handoff 和真实小数据验收。
