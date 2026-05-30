# CP-Bench P12 Manual Submission Decision

decision: `defer_external_submission`
official_scores_claimed: `false`
external_submission_status: `not_submitted`

## 结论

P12 不进入人工 Hugging Face submission gate。

## 依据

- P12 已把本地 evaluator proof 扩到 10 个 verified rows。
- 10 个 rows 均 `final_passed=true`，`final_solution_accuracy_percent` 从 `0.0` 到 `15.87`。
- candidate 使用公开 CP-Bench `model` 字段做 reference replay，因此证明的是 evaluator、artifact、outcome parser、failure summary 和 rollback evidence 的扩容能力。
- 这不证明 autonomous model generation、官方 leaderboard 竞争力或真实外部提交成绩。

## 进入 Submission Gate 前置条件

- P13 至少覆盖 10 个 verified rows，且 candidate 不能依赖公开 ground-truth model 字段。
- 每个失败 row 必须记录 `failure_type`、rollback evidence 和 proposal context。
- 需要证明 client-generated 或 client-repaired candidate 相比负控有稳定本地提升。
- 提交前必须通过路径泄露扫描、测试和人工声明边界审查。
