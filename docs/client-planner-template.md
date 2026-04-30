# Codex/Claude 客户端 Planner 模板

## 职责

客户端 planner 使用 Codex/Claude 的大模型能力做判断，MCP 服务只负责执行实验、读取论文、返回状态和结果。默认不要让服务端隐式调用 LLM；只有需要无人值守自动实验时，才显式调用 `run_ai_autoresearch`。

## 每轮输入

每次调用 `review_research_results` 后，优先读取：

- `experiment_state.best_result`
- `experiment_state.summary`
- `experiment_state.recent_experiments`
- `experiment_state.failure_summary`
- `experiment_state.research_evidence_gate`
- `experiment_state.planner_actions`
- `experiment_state.code_change_plan.next_experiment_plan`
- `experiment_state.code_change_plan.next_experiment_plan.proposed_task_patch`
- `experiment_state.code_change_plan.next_experiment_plan.dry_run_validation`
- `experiment_state.current_code.search_region`
- `experiment_state.next_round.task_patch`
- `experiment_state.next_round.experiment_strategy`

## 决策规则

- 如果 `planner_actions` 非空，优先解释并执行第一个 action，除非用户明确要求改走其他路径。
- 如果 `failure_summary.failed_count > 0`，先看日志和失败摘要；不要盲目扩大搜索空间。
- 如果 `research_evidence_gate.recommended_action == "refresh_research"`，先查看 `research_evidence_gate.retrieval_recovery`，再重新调用 `research_task`；不要把空来源的假设当成论文证据。
- 如果最近实验有目标 metric 且 accepted，先查看 `code_change_plan.next_experiment_plan` 的候选值、停止条件和 edit policy；若存在 `proposed_task_patch`，优先用它做单参数验证，否则再使用 `next_round.task_patch`。
- 使用 `proposed_task_patch` 前先执行 `dry_run_validation.preflight_checks`，实验完成后按 `dry_run_validation.post_run_checks` 调用 `review_research_results` 并判断是否停止。
- 如果最近实验没有目标 metric，先检查 `current_code.search_region` 和日志，再缩小到可运行参数。
- 如果 `experiment_strategy.mode == "debug_failures"`，优先调用 `get_experiment_result` 或日志工具，不要启动大批量实验。
- 如果连续两轮没有改善，停止当前局部方向，重新调用 `research_task` 或人工修改假设。
- 如果用户明确要求无人值守，调用 `run_ai_autoresearch`，并显式设置 `llm_provider`。

## 下一轮 MCP 调用

常规下一轮：

```json
{
  "name": "run_hypothesis_experiment",
  "arguments": "<experiment_state.planner_actions[0].arguments>"
}
```

无人值守下一轮：

```json
{
  "name": "run_ai_autoresearch",
  "arguments": {
    "task_config": "/ABS/PATH/TO/runtime/tasks/next-round.json",
    "runtime_root": "/ABS/PATH/TO/runtime",
    "llm_provider": "openai",
    "llm_model": "gpt-5.5",
    "max_experiments": 3,
    "experiment_duration": 300
  }
}
```

## 停止条件

- 已达到用户指定 metric 阈值。
- 当前方向连续失败或没有目标 metric。
- 搜索空间只是在重复同类参数，没有新证据支持继续。
- 运行预算、时间预算或用户成本预算接近上限。
