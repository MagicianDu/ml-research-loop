# ArGuard B1 P4 官方结果引导 MethodSearch

本目录把 Codabench 已返回的 P1 官方结果作为 outcome evidence，继续通过 ml-research-loop 自身的 MethodSearch/gate/memory 路径做下一轮低风险搜索。

## 结论

- official submission: `819950`。
- official score: `0.93`，visible rank: `3` / `6`。
- MethodSearch status: `completed_without_gate_winner`。
- submission recommendation: `HOLD`。
- recommended_for_codabench_submission: `false`。
- `official_scores_claimed=false`：本轮不上传新 submission，不声明新官方提升。

## 边界

- P4 使用公开 train/dev 重训和评估 P1-family 低风险候选。
- gate 同时检查 local macro-F1、3-fold train CV、safe 误伤预算和剩余提交预算。
- 若生成 `candidate-prediction.zip`，它也只是待人工复核的候选包，不会自动上传。

## 文件

- `official-result-observation.json`：登录态 Codabench 页面观察到的官方结果。
- `official-guided-search-run.json`：P4 候选、CV、gate 和提交建议。
- `method-search-trajectory.json`：MethodSearch/gate/tell/memory 轨迹。
- `gate-feedback-memory-store.json`：gate 反馈记忆。
- `submission-recommendation-gate.json`：是否建议人工复核下一次提交。
