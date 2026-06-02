# CP-Bench P17 Post-upload Verification

上传后必须等公开 storage 出现结果文件，才能更新任何官方提交状态。

## 验证步骤

1. 重新运行只读 preflight：

```bash
.venv/bin/python scripts/cp_bench_hf_gate_preflight.py \
  --gate-dir docs/hf-evaluation/cp-bench-p17-manual-submission-gate \
  --json
```

2. 确认 `target_result_path` 为 `results/v1_verified/ml_research_loop_p17/summary.txt`，且 `target_result_exists=true`。
3. 读取公开 `summary.txt` 后，再决定是否更新 `external_submission_status`。
4. 没有公开结果前，不得宣传 CP-Bench leaderboard score 或 ranking。
