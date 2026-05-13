# Benchmark Evidence Index

本文索引当前项目中已经完成的可复核 benchmark evidence。所有结果都按证据强度和声明边界区分，避免把本地 debug 或 dummy 结果包装成 leaderboard 成绩。

## 已完成

| Benchmark | Evidence | 结果 | 可宣传边界 |
| --- | --- | --- | --- |
| MLE-bench | `docs/evidence/mle-bench-spooky-20260507-cn.md` | `spooky-author-identification` 从 baseline log loss `1.08468` 改善到 `0.37038`，超过 median threshold `0.418785` | 可以宣传本地 official scorer proof run 超过 median；不能宣传 leaderboard |
| PaperBench | `docs/evidence/paperbench-debug-dummy-20260507-cn.md` | official debug split `rice` dummy solver + dummy judge 跑通，mean score `1.0`，三类 failure 均为 `0` | 可以宣传 official debug harness 全链路跑通；不能宣传真实论文复现质量 |
| PaperBench | `docs/evidence/paperbench-codex-review-rice-20260507-cn.md` | 对同一 `rice` debug dummy run 产出 Codex-assisted rubric review，审查分 `0.0`，proof archive `archivable` 且包含 `14` 个 artifact | 可以宣传 keyless Codex-assisted review 和诚实证据边界；不能宣传 official PaperBench score |
| fastText AG News | `docs/evidence/fasttext-ag-news-real-baseline-20260513-cn.md` | 完整 AG News CSV + 本机官方 fastText binary 跑出 `P@1=0.914`，落入当前 `0.924±0.02` target tolerance，并归档 train/test logs、runtime probe、baseline report 和 handoff | 可以宣传真实本地 baseline proof；不能宣传 leaderboard、完整论文所有表格或自动改进闭环 |

## 待完成

- MLE-bench：完整 agent run-group / Docker / 多任务评分。
- PaperBench：real judge debug path。
- PaperBench：客户端模型驱动的真实 reproduction attempt。
- fastText AG News：在可信 baseline 上执行 Codex/Claude patch 或超参 proposal loop，证明可控自动改进。
- Public artifact：把 `.demo_runs` 下的 proof archives 整理成可下载、可 hash 复核的 release bundle。

## 可用审查路径

- CLI：`ml-loop benchmark paperbench-codex-review-bundle --run-dir <paperbench-run-dir> --paper-dir <paperbench-paper-dir> --output-dir <review-bundle> --json`
- CLI：`ml-loop benchmark paperbench-codex-review-report --bundle <review-bundle/codex-review-bundle.json> --review-file <codex-review.json> --output-dir <review-report> --json`
- MCP：`prepare_paperbench_codex_review_bundle` -> Codex/Claude 审查 packet -> `write_paperbench_codex_review_report`
