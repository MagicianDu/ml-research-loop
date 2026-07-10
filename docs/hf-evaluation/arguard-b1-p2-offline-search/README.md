# ArGuard B1 P2 离线优化搜索

本目录记录 P1 提交后的一轮离线搜索，目标是在不消耗 Codabench 提交次数的前提下评估继续优化空间。

## 结论

- 当前 P1 best local macro-F1: `0.928714`。
- P2 local diagnostic winner: `p2-ensemble-fasttext-char25-norm`，local macro-F1 `0.931150`。
- submission recommendation gate: `HOLD`，recommended_for_codabench_submission=`false`。
- `official_scores_claimed=false`：本轮未声明官方成绩，也未生成新的 `prediction.zip`。

## 关键原因

- 最高 dev 候选主要通过提高 unsafe 判定降低漏判，但 safe 误伤明显增加。
- 3-fold train CV 显示该候选相对 P1 baseline 退化，因此被 gate 拦下。
- 在每天 5 次、总共 10 次提交预算下，本轮不建议消耗新的 Codabench 提交。

## 文件

- `offline-search-run.json`：所有候选、Optuna 搜索、CV 和 gate 证据。
- `submission-recommendation-gate.json`：是否推荐提交的最终 gate。
- `diagnostic-dev-with-label-prediction.csv`：本地诊断 winner 对 dev_with_label 的预测。
- `diagnostic-dev-without-label-prediction.csv`：本地诊断 winner 对 dev_without_label 的预测；不是可直接上传的 `prediction.zip`。
