# 混合 MCP 架构要求

## 目标

本项目采用混合架构：Codex/Claude 作为客户端强模型 planner，MCP 服务作为稳定执行器；同时保留服务端 LLM 后端用于无人值守自动实验。

## 固定边界

- 默认实验路径不得隐式调用服务端 LLM。`run_autoresearch` 和 `run_hypothesis_experiment` 只负责执行任务、记录结果、返回状态。
- 客户端模型负责理解目标、读论文、选择工具、解释实验结果、决定下一轮代码或超参策略。
- 服务端自主优化必须显式使用 `run_ai_autoresearch`，并显式选择 `llm_provider`。
- 执行类 MCP 工具必须遵守路径 sandbox：`runtime_root`、`workspace` 和 `task_config`
  只能位于项目根目录、服务端配置的 `ML_RESEARCH_LOOP_ROOT`，或
  `ML_RESEARCH_LOOP_ALLOWED_ROOTS` 中显式允许的目录内。
- 每轮实验结束后，`review_research_results` 必须返回足够给客户端模型继续迭代的 `experiment_state`。
- 新客户端必须先调用 `get_service_manifest`，校验 `contract_version`、
  `schema_versions` 和 `tool_contracts` 后再进入自动规划循环；当前 preview
  合约版本为 `2026-04-30.preview.v1`。

## 客户端规划循环

1. `research_task` / `read_paper` 收集研究上下文。
2. `propose_hypotheses` 生成可验证假设。
3. `run_hypothesis_experiment` 执行固定预算实验。
4. `review_research_results` 返回 `research_review` 和 `experiment_state`。
5. Codex/Claude 读取 `experiment_state`，决定下一轮：
   - 传入 `next_round.task_patch` 继续局部优化。
   - 如果 `failure_summary.failed_count > 0`，先调用 `get_experiment_logs` 获取日志摘要。
   - 调整搜索空间、预算或停止条件后再次运行。
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
- release check 必须覆盖 MCP stdio smoke、research-to-review golden path、两轮 `task_patch` handoff 和真实小数据验收。
