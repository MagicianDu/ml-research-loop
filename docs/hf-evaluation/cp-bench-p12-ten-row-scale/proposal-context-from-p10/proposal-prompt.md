# CP-Bench Proposal Prompt

你是客户端 planner。请基于本地 evaluator 的逐题 outcome 生成下一轮受控 proposal。

## 硬性边界

- 不要上传 Hugging Face。
- 不要声明 leaderboard score、排名或官方成绩。
- 只能生成本地 candidate submission 或 repair proposal。
- 必须保留 rollback_plan。

## 当前状态

- status: `improved`
- decision: `candidate_improved`
- metric: `final_solution_accuracy_percent`
- current_metric: `3.17`
- max_proposals: `3`

## 失败样本

- `csplib__csplib_005_autocorrelation`: `consistency_or_objective_failed`

## 输出 JSON 要求

返回一个 proposal JSON object，必须包含：

- `proposal_id`
- `hypothesis`
- `change_type`
- `expected_metric`
- `risk`
- `rollback_plan`

`change_type` 只能是： `prompt_profile, code_patch, framework_switch`。

proposal 必须说明预期影响、风险、失败时如何回滚，以及下一步应调用 `run_cp_bench_candidate_round` 验证。
