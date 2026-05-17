# Benchmark Evidence Index

本文索引当前项目中已经完成的可复核 benchmark evidence。所有结果都按证据强度和声明边界区分，避免把本地 debug 或 dummy 结果包装成 leaderboard 成绩。

全局声明边界：本索引只发布 proof evidence 文档和限制说明，`official_scores_claimed=false`。当前没有声明 official leaderboard、official PaperBench score 或完整官方 run-group 成绩；当前 checkout 也未保留对应 `.demo_runs` 原始 artifact，不能把本索引当作可下载 release proof bundle。

P15 文档级证据索引已经分成三类，不得混写：

- official-debug hard result：MLE-bench `spooky-author-identification` 使用官方 prepared data 和 `mlebench grade-sample` 本地 scorer feedback，证明 patch/grade/proof archive 闭环；不能宣传 leaderboard。
- debug dummy harness：PaperBench debug split `rice` 使用 dummy solver + dummy judge 跑通官方 rollout/reproduction/grading path，`score=1.0` 只说明 harness 连通；不是官方 PaperBench score。
- Codex-assisted review：对同一 `rice` dummy run 做非官方 rubric 审查，`codex_review_score=0.0`、`PaperBench official score=null`；不是官方 PaperBench score。

## 已完成

| Benchmark | Evidence | 结果 | 可宣传边界 |
| --- | --- | --- | --- |
| MLE-bench | `docs/evidence/mle-bench-spooky-20260507-cn.md` | official-debug hard result：`spooky-author-identification` 从 baseline log loss `1.08468` 改善到 `0.37038`，超过 median threshold `0.418785` | 可以宣传本地 official scorer proof run 超过 median；不能宣传 leaderboard；`official_scores_claimed=false` |
| PaperBench | `docs/evidence/paperbench-debug-dummy-20260507-cn.md` | debug dummy harness：official debug split `rice` dummy solver + dummy judge 跑通，mean score `1.0`，三类 failure 均为 `0` | 可以宣传 official debug harness 全链路跑通；不能宣传真实论文复现质量；不是官方 PaperBench score；`official_scores_claimed=false` |
| PaperBench | `docs/evidence/paperbench-codex-review-rice-20260507-cn.md` | Codex-assisted review：对同一 `rice` debug dummy run 产出非官方 rubric review，审查分 `0.0`，proof archive `archivable` 且包含 `14` 个 artifact | 可以宣传 keyless Codex-assisted review 和诚实证据边界；不是官方 PaperBench score；`official_scores_claimed=false` |
| fastText AG News | `docs/evidence/fasttext-ag-news-real-baseline-20260513-cn.md` | 完整 AG News CSV + 本机官方 fastText binary 跑出 `P@1=0.914`，落入当前 `0.924±0.02` target tolerance，并归档 train/test logs、runtime probe、baseline report 和 handoff | 可以宣传真实本地 baseline proof；不能宣传 leaderboard、完整论文所有表格或自动改进闭环 |
| fastText AG News | `docs/evidence/fasttext-ag-news-p3-patch-round-20260513-cn.md` | 基于可信 baseline 执行一次客户端风格 proposal `-wordNgrams 2`，`P@1` 从 `0.914` 提升到 `0.916`，delta `+0.002`，并归档 proposal、diff、train/test logs、improvement report 和 handoff | 可以宣传真实本地受控 patch loop proof；不能宣传 leaderboard、完整论文所有表格或任意自动优化 |
| fastText AG News | `docs/evidence/fasttext-ag-news-p4-proof-bundle-20260514-cn.md` | 将 P3 patch round 打包为 `approved_with_limitations` proof bundle，包含 `10` 个 artifact、`human-review-report.json`、`proof-manifest.json`、`artifact-index.json` 和 `SHA256SUMS` | 可以宣传真实本地 proof bundle 和 hash-indexed evidence；不能宣传 leaderboard、完整论文所有表格或无人值守自动科研 |
| fastText AG News | `docs/evidence/fasttext-ag-news-p5-release-proof-20260514-cn.md` | 执行 2 轮 proposal，其中 1 轮 `wordNgrams=2` 成功、1 轮非法 `bucket=100` 被记录为失败，best `P@1=0.916`，rollback events `1`，并生成 checksum 复核通过的 `release-proof-bundle.tar.gz` | 可以宣传多轮 proposal、失败/回滚样例和 release proof bundle 下载/复核路径；不能宣传 leaderboard、完整论文所有表格或任意自动优化 |

## 待完成

- MLE-bench：完整 agent run-group / Docker / 多任务评分。
- PaperBench：real judge debug path。
- PaperBench：客户端模型驱动的真实 reproduction attempt。
- Public artifact：把 release proof bundle 附到 GitHub release 或外部可下载存储，并补充独立复核说明。

## 可用审查路径

- CLI：`ml-loop benchmark paperbench-codex-review-bundle --run-dir <paperbench-run-dir> --paper-dir <paperbench-paper-dir> --output-dir <review-bundle> --json`
- CLI：`ml-loop benchmark paperbench-codex-review-report --bundle <review-bundle/codex-review-bundle.json> --review-file <codex-review.json> --output-dir <review-report> --json`
- MCP：`prepare_paperbench_codex_review_bundle` -> Codex/Claude 审查 packet -> `write_paperbench_codex_review_report`
