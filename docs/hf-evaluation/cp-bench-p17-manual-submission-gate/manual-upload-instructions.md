# CP-Bench P17 Manual Upload Instructions

当前状态：`not_submitted`，不得声明官方 leaderboard score。

## 表单字段

- Submission Name: `ml_research_loop_p17`
- Dataset Version: `verified`
- Modelling Framework: `CPMpy`
- Base LLM: `Codex-assisted deterministic CPMPy solver expansion`
- Report PDF: `approach-report.pdf`
- Submission File: `submission.jsonl`

## 上传前检查

1. 确认 Hugging Face 账号具备向 `kostis-init/my-storage` dataset 写入 submission 的权限。
2. 确认 `ml_research_loop_p17` 在 verified submissions 中不存在。
3. 确认 `shasum -a 256 -c SHA256SUMS` 通过。
4. 从 repo 根目录运行只读 preflight：
   `.venv/bin/python scripts/cp_bench_hf_gate_preflight.py --gate-dir docs/hf-evaluation/cp-bench-p17-manual-submission-gate`
5. 生成只读 submission packet：
   `.venv/bin/python scripts/cp_bench_hf_submission_packet.py --output-dir docs/hf-evaluation/cp-bench-p17-space-submission-packet`
6. 只有 preflight 或 packet 显示 `ready_for_manual_space_upload`，并且人工批准公开上传后，才使用 Space 表单上传。
7. 上传后等待 Space 后台 evaluator 写入 `results/v1_verified/ml_research_loop_p17/summary.txt`。
8. 只有公开结果可见后，才能把 `external_submission_status` 改为 `submitted`，并记录公开 URL。

## 不允许的宣传口径

- 不得把本地 `52.38%` 写成官方成绩。
- 不得声称已有 CP-Bench ranking。
- 不得忽略 CP-Bench 已被 DCP-Bench-Open 取代的边界。
