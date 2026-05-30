# CP-Bench P0 Live Verification

日期：2026-05-23

本目录保存 CP-Bench 作为第一条 Hugging Face 可提交 proof 线的 P0 artifact。

## 当前结论

- `verification_status=verified_with_limitations`
- `official_scores_claimed=false`
- `external_submission_status=not_submitted`
- `manual_submission_required=true`

P0 只证明公开数据集、leaderboard 说明、UI 提交流程和本地 evaluator 源码当前可访问。它不代表已经提交 CP-Bench，也不代表已经取得 Hugging Face leaderboard 成绩。

## Artifact

- `cp-bench-live-verification.json`：URL 可访问性、HTTP 状态、hash 和 target contract。
- `cp-bench-target-contract.md`：面向人工和 MCP client 的简明 target contract。

## Live Checks

本次检查覆盖：

- CP-Bench dataset API；
- CP-Bench Leaderboard README；
- CP-Bench Leaderboard UI；
- CP-Bench local evaluator `user_eval.py`。

四个 critical check 均为 `reachable`。

## 下一步

进入 P1：实现 CP-Bench local baseline adapter。要求先 dry-run 生成合法 `.jsonl` submission、summary parser、runtime profile 和 artifact manifest；若本机缺少 `datasets`、`cpmpy`、`minizinc` 或 `ortools` 等依赖，必须写出 blocked artifact，而不是崩溃。
