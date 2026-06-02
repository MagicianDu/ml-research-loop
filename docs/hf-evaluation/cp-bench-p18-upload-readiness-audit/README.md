# CP-Bench Upload Readiness Audit

本目录汇总公开上传前的本地状态；它不执行上传。

## 当前状态

- status: `public_result_available_for_claim_review`
- ready_for_public_upload_attempt: `true`
- claimable_public_result: `true`
- blockers: `0`
- next_action: `verify_public_summary_and_prepare_promotional_claim`
- `external_upload_performed_by_script=false`
- `official_scores_claimed=false`

只有公开 `summary.txt` 出现后，才允许进入宣传 claim review。

## 依赖证据

- hf-cp-bench extra declares gradio_client: `true`
- install_command: `pip install 'ml-research-loop[hf-cp-bench]'`

## 明确批准后命令

第一条命令只有在用户明确批准真实公开上传后才可执行。

### 公开上传

```bash
.venv/bin/python scripts/cp_bench_hf_gradio_submission.py --gate-dir docs/hf-evaluation/cp-bench-p18-manual-submission-gate --output-dir docs/hf-evaluation/cp-bench-p18-gradio-submission-dry-run --confirm-public-upload --human-approval-note '<explicit approval note>'
```

### 上传后检查公开结果

```bash
.venv/bin/python scripts/cp_bench_hf_public_result_watcher.py --gate-dir docs/hf-evaluation/cp-bench-p18-manual-submission-gate --output-dir docs/hf-evaluation/cp-bench-p18-public-result-watch
```

### 刷新 readiness audit

```bash
.venv/bin/python scripts/cp_bench_hf_upload_readiness_audit.py --gate-dir docs/hf-evaluation/cp-bench-p18-manual-submission-gate --gradio-plan docs/hf-evaluation/cp-bench-p18-gradio-submission-dry-run/gradio-submission-plan.json --public-watch docs/hf-evaluation/cp-bench-p18-public-result-watch/public-result-watch.json --output-dir docs/hf-evaluation/cp-bench-p18-upload-readiness-audit
```
