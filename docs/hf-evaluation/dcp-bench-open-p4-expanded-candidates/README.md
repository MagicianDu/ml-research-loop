# DCP-Bench-Open P4 扩容候选

本目录在 P3 扩容候选基础上追加一批小规模逻辑、构造和公开实例求解候选。
候选生成只使用公开题面、第一实例数据和输出变量要求；不读取 DCP reference model 或 example solution。

## 状态

- base candidate count: `110`
- added candidate count: `18`
- total candidate count: `128`
- `official_scores_claimed=false`
- `external_submission_status=not_submitted`

## 文件

- `submission.jsonl`: 扩容后的 DCP candidate submission。
- `candidate-expansion-report.json`: 扩容元数据。
- `source-audit.json`: no-reference source audit。
- `artifact-manifest.json` / `SHA256SUMS`: 完整性记录。
