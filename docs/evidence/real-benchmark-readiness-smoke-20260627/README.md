# Real Benchmark Readiness Smoke 2026-06-27

本目录是 `run_real_benchmark_readiness_run` / `proposal run-real-benchmark-readiness` 的本地 readiness smoke 证据。

## 结论

- 已跑通 3 轮 `optimizer source -> MethodSearchTrial -> Smol WorldCup local eval -> gate -> tell -> GateFeedbackMemory`。
- 每轮真实 import 并执行本地 python-package optimizer：`readiness-optimizer-plugin`。
- 每轮候选都被材料化成 prompt profile registration overlay，并进入 dev/canary eval。
- gate result 来自 eval outcome，不是人工喂 `gate-results.json`。
- best path 由 gate 选出：第 1 轮 `readiness-optimizer-plugin-001`，local gate score `100.0`。
- `real_optimizer_candidate_count=3`，`real_eval_outcome_count=3`，`fallback_candidate_count=0`。
- `GateFeedbackMemory` 将 `adapt` 权重更新到 `3.25`。
- `official_scores_claimed=false`，未执行外部 submission。

## 关键产物

- `run_smoke.py`：可重复执行 smoke 的入口。
- `real-benchmark-readiness-run.json`：3 轮 readiness 总报告。
- `gate-feedback-memory-store.json`：跨轮 feedback memory store。
- `inputs/rows.json`：低成本 Smol WorldCup fixture rows。
- `inputs/plugin-manifest.json`：python-package optimizer adapter manifest。
- `runtime_plugins/readiness_optimizer/`：真实 import 的本地 optimizer package。
- `run/baseline/*.json`：baseline dev/canary eval。
- `run/round-*/candidate-evals/*/dev-eval.json` 与 `canary-eval.json`：候选实际 eval。
- `run/round-*/gate-results-from-eval.json`：由 eval outcome 转出的 gate result。
- `run/round-*/race/multi-optimizer-candidate-race.json`：每轮 MethodSearch race ledger。

## 边界

这次 smoke 使用 deterministic local chat fixture，目的是稳定验证产品闭环，不验证 live LLM endpoint 质量。它执行了本地 benchmark eval，但不是 external official benchmark，不可宣称 official score 或真实榜单提升。

公开边界仍是：local readiness evidence only；`official_scores_claimed=false`。
