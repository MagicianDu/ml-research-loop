# 混合 MCP 架构要求

## 目标

本项目采用混合架构：Codex/Claude 作为客户端强模型 planner，MCP 服务作为稳定执行器；同时保留服务端 LLM 后端用于无人值守自动实验。

## 固定边界

- 默认实验路径不得隐式调用服务端 LLM。`run_autoresearch` 和 `run_hypothesis_experiment` 只负责执行任务、记录结果、返回状态。
- 客户端模型负责理解目标、读论文、选择工具、解释实验结果、决定下一轮代码或超参策略。
- 服务端自主优化必须显式使用 `run_ai_autoresearch`，并显式选择 `llm_provider`。
- 每轮实验结束后，`review_research_results` 必须返回足够给客户端模型继续迭代的 `experiment_state`。

## 客户端规划循环

1. `research_task` / `read_paper` 收集研究上下文。
2. `propose_hypotheses` 生成可验证假设。
3. `run_hypothesis_experiment` 执行固定预算实验。
4. `review_research_results` 返回 `research_review` 和 `experiment_state`。
5. Codex/Claude 读取 `experiment_state`，决定下一轮：
   - 传入 `next_round.task_patch` 继续局部优化。
   - 调整搜索空间、预算或停止条件后再次运行。
   - 在具备文件写权限的客户端中修改代码，再调用实验工具验证。
   - 需要无人值守时改用 `run_ai_autoresearch`。

## `experiment_state` 合约

`experiment_state` 是客户端模型的 handoff 数据包，至少包含：

- `planner_handoff`：声明客户端模型和 MCP 服务的职责边界，以及建议下一步工具。
- `best_result` / `summary` / `recent_experiments`：让模型判断当前优化走势。
- `failure_summary`：最近失败原因，避免盲目继续采样。
- `current_code.search_region`：当前可调参数区。
- `current_code.program_md_excerpt`：当前实验约束和提示摘要。
- `artifacts`：结果、进度、workspace、`train.py`、`program.md`、日志目录路径。
- `next_round`：可直接交给下一轮的 `task_patch`、推荐搜索空间和实验策略。

## 验收要求

- MCP 工具列表同时包含客户端编排工具和服务端自主工具。
- `review_research_results` 在没有服务端 LLM 的情况下也能返回 `experiment_state`。
- release check 必须覆盖 MCP stdio smoke、research-to-review golden path 和两轮 `task_patch` handoff。
