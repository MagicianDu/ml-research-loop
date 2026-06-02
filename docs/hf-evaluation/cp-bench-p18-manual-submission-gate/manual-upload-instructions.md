# CP-Bench Manual Upload Instructions

当前状态：`not_submitted`，不得声明官方 leaderboard score。

## 表单字段

- Submission Name: `ml_research_loop_p18`
- Dataset Version: `verified`
- Modelling Framework: `CPMpy`
- Base LLM: `Codex-assisted deterministic CPMPy solver expansion`
- Report PDF: `approach-report.pdf`
- Submission File: `submission.jsonl`

## 上传前检查

1. 确认 `shasum -a 256 -c SHA256SUMS` 通过。
2. 确认只读 preflight 通过。
3. 只有人工明确批准公开上传后，才允许使用 Space 表单或脚本上传。
4. 上传后等待公开 `summary.txt` 出现。
5. 只有公开结果可见后，才能声明官方 score 或 ranking。
