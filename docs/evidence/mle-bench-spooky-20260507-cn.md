# MLE-bench Hard Result: Spooky Author Identification

日期：2026-05-07

本文记录一次可复核的 MLE-bench official-debug path 结果。它证明 ML Research Loop 已经可以把 Codex/Claude 生成的 bounded patch 放进真实 MLE-bench 任务 workspace，执行 solve/grade/proof archive 闭环。

## 结论

- Benchmark：MLE-bench
- Competition：`spooky-author-identification`
- 数据来源：官方 MLE-bench `prepare` + Kaggle 数据
- 运行模式：`official_debug_patch_round`
- 评分方式：官方 `mlebench grade-sample` 本地 scorer feedback
- Baseline：sample submission，log loss `1.08468`
- Patch v1：TF-IDF + calibrated SGD，log loss `0.45383`
- Patch v2：word + char TF-IDF + logistic regression，log loss `0.37038`
- 相对 baseline 改善：约 `65.85%`
- Median threshold：`0.418785`
- Patch v2 是否超过 median：`true`
- 提交文件是否有效：`true`
- Proof archive：`archivable`
- 归档 artifact 数量：`12`

## 不能声明的内容

- 这不是官方 leaderboard 成绩。
- 这不是完整 MLE-bench agent run-group / Docker / 多任务评测。
- 这不是 medal 级结果；本轮未超过 bronze threshold `0.29381`。
- 对外传播时必须保留 `official_scores_claimed=false`。

## 本地证据路径

这些路径位于 `.demo_runs`，默认不进入 git；它们用于本机复核和后续整理公开 artifact。

- Baseline grade report：`.demo_runs/hard-results/mle-spooky-20260507-1735/benchmark-rounds/baseline/grade-report.json`
- Patch v1 report：`.demo_runs/hard-results/mle-spooky-20260507-1735/benchmark-rounds/sklearn-text-v1/patch-round-report.json`
- Patch v2 report：`.demo_runs/hard-results/mle-spooky-20260507-1735/benchmark-rounds/logreg-word-char-v2/patch-round-report.json`
- Patch v2 proof manifest：`.demo_runs/hard-results/mle-spooky-20260507-1735/proof/logreg-word-char-v2/manifest.json`
- Patch v2 proof publication：`.demo_runs/hard-results/mle-spooky-20260507-1735/proof/logreg-word-char-v2/archive/publication/proof-publication.md`
- Patch v2 artifact index：`.demo_runs/hard-results/mle-spooky-20260507-1735/proof/logreg-word-char-v2/archive/artifact-index.json`

## 对产品能力的证明

这次结果证明的是产品闭环，而不是单次模型分数：

1. MCP/CLI 能创建官方 prepared-data workspace。
2. 客户端强模型可以只输出 bounded diff。
3. 服务端负责 patch preflight、执行、评分、日志和报告。
4. 本地 scorer feedback 能反馈给客户端，驱动下一轮 patch。
5. 最终结果能进入 publication guard 和 hash archive，避免把本地 debug 结果误包装为官方榜单。

## 下一步

1. 把这份 MLE-bench 结果整理成公开 README/launch 文案中的“可复核 proof run”段落。
2. 补一次 PaperBench official debug dummy run；当前主要卡点是 Git LFS 数据 hydration。
3. 准备真实 grader key 后再跑 PaperBench real judge path。
4. 在更长任务上验证多轮 patch/grade loop 的稳定性。
