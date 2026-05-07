# Benchmark Evidence Index

本文索引当前项目中已经完成的可复核 benchmark evidence。所有结果都按证据强度和声明边界区分，避免把本地 debug 或 dummy 结果包装成 leaderboard 成绩。

## 已完成

| Benchmark | Evidence | 结果 | 可宣传边界 |
| --- | --- | --- | --- |
| MLE-bench | `docs/evidence/mle-bench-spooky-20260507-cn.md` | `spooky-author-identification` 从 baseline log loss `1.08468` 改善到 `0.37038`，超过 median threshold `0.418785` | 可以宣传本地 official scorer proof run 超过 median；不能宣传 leaderboard |
| PaperBench | `docs/evidence/paperbench-debug-dummy-20260507-cn.md` | official debug split `rice` dummy solver + dummy judge 跑通，mean score `1.0`，三类 failure 均为 `0` | 可以宣传 official debug harness 全链路跑通；不能宣传真实论文复现质量 |

## 待完成

- MLE-bench：完整 agent run-group / Docker / 多任务评分。
- PaperBench：real judge debug path。
- PaperBench：客户端模型驱动的真实 reproduction attempt。
- PaperBench：用 `paperbench-codex-review-bundle` 和
  `paperbench-codex-review-report` 对 debug artifact 生成一份 Codex-assisted
  rubric review。Codex-assisted rubric review is not an official PaperBench
  score.
- Public artifact：把 `.demo_runs` 下的 proof archives 整理成可下载、可 hash 复核的 release bundle。

## 可用审查路径

- CLI：`ml-loop benchmark paperbench-codex-review-bundle --run-dir <paperbench-run-dir> --paper-dir <paperbench-paper-dir> --output-dir <review-bundle> --json`
- CLI：`ml-loop benchmark paperbench-codex-review-report --bundle <review-bundle/codex-review-bundle.json> --review-file <codex-review.json> --output-dir <review-report> --json`
- MCP：`prepare_paperbench_codex_review_bundle` -> Codex/Claude 审查 packet -> `write_paperbench_codex_review_report`
