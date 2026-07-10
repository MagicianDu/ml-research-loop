# ArGuard B1 P1 本地优化证据

本目录记录一次公开 train/dev 上的本地 baseline、5 轮 optimizer/gate 和 submission gate。

## 结论

- best local trial: `b1-round-003-word-char-logreg`
- best local macro-F1: `0.928714`
- train 清洗后 `16833` 行；过滤空/非法 label `2` 行。
- 5 轮 gate 里 `word_char_logreg` 成为当前 best，后续 `LinearSVC` 和 dialect-conditioned 变体被剪枝。
- 登录态页面确认 Codabench 要上传 `prediction.zip`，其中包含 UTF-8 `prediction.csv`，列为 `id,prediction`。
- `official_scores_claimed=false`：未提交 Codabench，未宣称官方榜单成绩。
- Codabench submission gate 当前为 `ready_for_manual_codabench_submission=true`。

## 阻断

- 当前登录用户已注册参赛，页面出现 `Submission upload`；下一步仍需人工授权上传。
- 公开仓库有 train/dev 数据，但 official scorer 和 format checker 仍未释放为可执行脚本；最终成绩只能由 Codabench submission/result 验证。

## 文件

- `source-readiness.json`：公开仓库资产和源码状态。
- `local-optimization-run.json`：baseline、每轮 proposal、gate、trial、memory。
- `codabench-submission-gate.json`：Codabench 页面确认的提交格式检查和人工提交阻断。
- `local-diagnostic-dev-with-label.csv`：对 dev_with_label 的本地诊断预测。
- `prediction.csv`：对 dev_without_label 的 Codabench 格式预测文件。
- `prediction.zip`：待人工确认后上传的 Codabench submission package。
