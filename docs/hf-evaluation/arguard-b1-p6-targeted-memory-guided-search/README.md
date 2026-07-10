# ArGuard B1 P6 定向 memory-guided 搜索

本目录接续 P5 的 near-pass 结论，只围绕 `p5-memory-guided-family-ensemble` 做 5 轮定向探索，目标是判断它是否能跨过提交 gate，而不是扩大到新的无关搜索空间。

## 结论

- MethodSearch status: `completed_without_gate_winner`。
- best direction: `p6-member-regularization-frontier` / `tune.memory_guided_member_regularization`。
- best direction gate status: `near_pass`。
- submission recommendation: `HOLD`。
- recommended_for_codabench_submission: `false`。
- `official_scores_claimed=false`：本轮没有上传新 submission，也没有声明新的官方提升。

## 5 轮探索

- round 1: `p6-family-weight-frontier` / `combine.memory_guided_weight_frontier`，local macro-F1 `0.929676`，gate `near_pass`，blockers `[]`。
- round 2: `p6-threshold-tightening` / `refine.memory_guided_threshold_tightening`，local macro-F1 `0.929676`，gate `near_pass`，blockers `[]`。
- round 3: `p6-member-regularization-frontier` / `tune.memory_guided_member_regularization`，local macro-F1 `0.929676`，gate `near_pass`，blockers `[]`。
- round 4: `p6-cv-stability-audit` / `audit.memory_guided_cv_stability`，local macro-F1 `0.929676`，gate `near_pass`，blockers `[]`。
- round 5: `p6-relaxed-risk-boundary` / `audit.memory_guided_relaxed_risk_boundary`，local macro-F1 `0.929304`，gate `blocked`，blockers `['insufficient_local_score_delta', 'cv_regression', 'safe_false_positive_regression']`。

## 边界

- 所有 evidence 都来自公开 train/dev 的 local evidence 和 train CV。
- P6 使用 P5 memory 作为方向选择依据，但不能自行宣称 official score 提升。
- 只有 gate `passed` 才会生成 `candidate-prediction.zip` 进入人工提交复核。

## 文件

- `targeted-search-run.json`：候选、CV、gate、best direction 和提交建议。
- `method-search-trajectory.json`：5 轮 MethodSearch/gate/tell/memory 轨迹。
- `gate-feedback-memory-store.json`：gate 反馈后的 operator memory。
- `submission-recommendation-gate.json`：是否建议进入人工提交复核。
