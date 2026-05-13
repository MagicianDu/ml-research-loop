# fastText AG News P4 proof bundle 证据

日期：2026-05-14

## 结论

本次运行把 P3 fastText AG News 真实本地 patch round 升级为 P4 proof bundle：

- 输入 patch round：`.demo_runs/p3-fasttext-real-patch/improvement-report.json`
- proof bundle 输出：`.demo_runs/p4-fasttext-real-proof`
- review status：`approved_with_limitations`
- reviewer：`codex-local-review`
- artifact count：`10`
- `official_scores_claimed`：`false`

指标摘要：

- baseline `P@1` / accuracy：`0.914`
- patch 后 `P@1` / accuracy：`0.916`
- delta：`+0.002`
- 是否优于 baseline：是
- 是否仍落入 `0.924±0.02` target tolerance：是

这说明 P3 的“受控客户端 proposal -> MCP 执行 -> 指标对比归档”已经进一步进入
“人工复核 + artifact hash + proof manifest”的证据形态。它仍不是官方 leaderboard
成绩，也不是完整论文所有表格的复现。

## 运行命令

```bash
.venv/bin/python scripts/full_reproduction_run.py \
  --target-spec docs/reproduction-pilot/full-reproduction-target.json \
  --output-dir .demo_runs/p4-fasttext-real-proof \
  --write-fasttext-patch-proof-bundle \
  --patch-round-report .demo_runs/p3-fasttext-real-patch/improvement-report.json \
  --reviewer codex-local-review \
  --json
```

## 关键 artifacts

输出目录：`.demo_runs/p4-fasttext-real-proof`

- `proof-manifest.json`
- `human-review-report.json`
- `artifact-index.json`
- `SHA256SUMS`
- `proof-summary.md`
- `artifacts/improvement-report.json`
- `artifacts/baseline-report.json`
- `artifacts/dataset-provenance.json`
- `artifacts/fasttext-runtime-probe.json`
- `artifacts/patch-proposal.json`
- `artifacts/patch-diff.patch`
- `artifacts/fasttext-patch-train.log`
- `artifacts/fasttext-patch-test.log`
- `artifacts/client-handoff.json`

`proof-manifest.json` 的核心字段：

```json
{
  "stage": "p4_fasttext_patch_proof_bundle",
  "review_status": "approved_with_limitations",
  "reviewer": "codex-local-review",
  "metric_summary": {
    "baseline_p_at_1": 0.914,
    "p_at_1": 0.916,
    "delta": 0.002,
    "improved": true,
    "within_tolerance": true
  },
  "artifact_count": 10,
  "official_scores_claimed": false
}
```

`SHA256SUMS` 记录每个 proof artifact 的哈希。示例：

```text
25cf738c39ceaa31c282a5afa17904c19623a8e897f7ea03fb49b9f197d1ec66  artifacts/patch-diff.patch
95b22b0361c22cce166de952c47ada061d8e3a6461a3cdbcc093f7acb125ff88  artifacts/fasttext-patch-test.log
2f39e347fbd79ee81ac3fb14c3116ec3649a788710e0cebab24c7a3449dc80ad  human-review-report.json
```

## 声明边界

可以说：

- 项目已经把一个真实 fastText AG News patch round 打包为可复查 proof bundle。
- proof bundle 包含人工复核状态、artifact index、SHA-256、训练/评测日志、proposal、
  diff、baseline report、improvement report 和 client handoff。
- 本地 P3 patch 相对 baseline 有小幅正向提升，并已被 P4 证据包固化。

不能说：

- 这是官方 leaderboard 成绩。
- 已经完整复现论文所有实验表格。
- 已经证明任意论文或任意模型都能自动提升。
- 已经可以无人值守连续调参；`human-review-report.json` 仍要求人工复核边界。
