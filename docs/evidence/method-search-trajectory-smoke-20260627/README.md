# Method Search Trajectory Smoke 2026-06-27

本目录是 `run-method-search-trajectory` 的 4 轮本地 smoke 证据。

## 结论

- 已真实跑 4 轮 `MethodSearchTrajectory -> MultiOptimizerCandidateRace -> gate -> tell -> GateFeedbackMemory`。
- 每轮尝试两个真实 python-package optimizer source：
  - `trajectory-fast-plugin`
  - `trajectory-conservative-plugin`
- 两个 source 都通过本地插件包 `trajectory_optimizer` 被真实 import 并执行 `FixtureOptimizerAdapter.generate_slice_patch_candidate`。
- 最佳路径由 gate 选出：第 4 轮 `trajectory-fast-plugin-001`，local gate score `0.79`。
- `real_optimizer_candidate_count=8`，`fallback_candidate_count=0`。
- `official_scores_claimed=false`，不能宣称 official benchmark 提升。

## 关键产物

- `workspace-package-manifest.json`：本次 review 包范围、验证命令、best path、workspace 风险与 official claim 边界。
- `method-search-trajectory.json`：4 轮 trajectory 总报告。
- `gate-feedback-memory-store.json`：跨轮 gate feedback memory store。
- `run/round-*/multi-optimizer-candidate-race-run.json`：每轮真实 candidate race。
- `inputs/`：context、plugin manifest、每轮 gate results。

## 边界

这次 smoke 验证的是产品闭环和本地 gate 选择能力，不是外部 benchmark official result。真实 benchmark 提升仍需要接入实际任务评估、canary/holdout 和 official claim verifier。
