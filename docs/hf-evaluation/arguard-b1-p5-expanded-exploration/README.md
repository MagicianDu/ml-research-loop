# ArGuard B1 P5 扩展探索

本目录沿着已提交 P1 官方结果继续运行 5 轮 ml-research-loop MethodSearch/gate/memory 探索，目标是找出更有希望的下一步方向，而不是直接消耗新的 Codabench 提交次数。

## 结论

- MethodSearch status: `completed_without_gate_winner`。
- best direction: `p5-memory-guided-family-ensemble` / `combine.memory_guided_model_family_views`。
- best direction gate status: `near_pass`。
- submission recommendation: `HOLD`。
- recommended_for_codabench_submission: `false`。
- `official_scores_claimed=false`：本轮没有上传新 submission，也没有声明新的官方提升。

## 5 轮探索

- round 1: `p5-cv-stable-regularization` / `tune.cv_stable_regularization`，local macro-F1 `0.928714`，gate `blocked`，blockers `['insufficient_local_score_delta']`。
- round 2: `p5-safe-recall-frontier` / `refine.safe_recall_frontier`，local macro-F1 `0.928714`，gate `blocked`，blockers `['insufficient_local_score_delta']`。
- round 3: `p5-arabic-normalization-surface` / `adapt.arabic_normalization_surface`，local macro-F1 `0.927319`，gate `blocked`，blockers `['insufficient_local_score_delta', 'cv_regression']`。
- round 4: `p5-memory-guided-family-ensemble` / `combine.memory_guided_model_family_views`，local macro-F1 `0.929676`，gate `near_pass`，blockers `[]`。
- round 5: `p5-high-dev-risk-audit` / `audit.high_dev_score_risk`，local macro-F1 `0.929181`，gate `blocked`，blockers `['insufficient_local_score_delta', 'cv_regression', 'safe_false_positive_regression']`。

## 边界

- 所有 evidence 都来自公开 train/dev 的 local evidence 和 3-fold train CV。
- P5 用 official P1 score 作为方向反馈，但不把 local evidence 升格为 official score。
- 如果 gate 没有 `passed`，不会生成新的 `prediction.zip`。

## 文件

- `expanded-exploration-run.json`：候选、CV、gate、best direction 和提交建议。
- `method-search-trajectory.json`：5 轮 MethodSearch/gate/tell/memory 轨迹。
- `gate-feedback-memory-store.json`：gate 反馈后的 operator memory。
- `submission-recommendation-gate.json`：是否建议进入人工提交复核。
