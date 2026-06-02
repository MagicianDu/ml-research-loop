# DCP-Bench-Open 本地评测门禁

本目录记录 `DCP-Bench-Open P3 expanded candidates` 在 DCP-Bench-Open v0.1.0 的本地 evaluator 结果。
它不是公开榜单成绩，也没有执行任何外部上传。

## 结果

- DCP release: `v0.1.0`
- DCP commit: `5bef2cec7c62fecb0cfc47c7bb6879588fbaaf26`
- DCP problem count: `164`
- submitted models: `110`
- runtime success: `110/110`
- submission coverage: `67.07%`
- final solution accuracy: `65.24%`
- submitted-only accuracy: `97.27%`
- passed models: `107`
- failed models: `3`

失败 ID:
- `csplib_021_crossfigures`
- `coins_grid`
- `twelve_pack`

## 声明边界

- `official_scores_claimed=false`
- `external_submission_status=not_submitted`
- `external_upload_performed=false`
- 不得宣传为 DCP-Bench-Open 官方榜单或外部提交成绩。
- 这只能宣传为固定公开 release 上的本地 evaluator 迁移结果。

## 文件

- `submission.jsonl`: DCP candidate submission。
- `evaluation-summary.txt`: 已净化机器路径的 evaluator summary。
- `dcp-bench-open-local-eval-report.json`: 结构化评测报告。
- `source-audit.json`: no-reference 边界审计。
- `artifact-manifest.json` / `SHA256SUMS`: artifact 完整性记录。
