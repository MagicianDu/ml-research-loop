# fastText AG News P3 真实本地 patch round 证据

日期：2026-05-13

## 结论

本次运行在已归档的 fastText/AG News 真实本地 baseline 上执行了一次
Codex/Claude-style 受控超参 proposal：

- baseline `P@1` / accuracy：`0.914`
- patch：`-wordNgrams 2`
- patch 后 `P@1` / accuracy：`0.916`
- delta：`+0.002`
- 是否优于 baseline：是
- 是否仍落入 `0.924±0.02` target tolerance：是
- `official_scores_claimed`：`false`

这证明项目已经具备第一条真实的“客户端强模型提出受限 proposal，MCP
执行训练/评测，归档 diff、日志、指标和 handoff”的复现优化闭环。它仍不是官方
leaderboard 成绩，也不是完整论文所有表格的复现。

## 运行命令

```bash
.venv/bin/python scripts/full_reproduction_run.py \
  --target-spec docs/reproduction-pilot/full-reproduction-target.json \
  --output-dir .demo_runs/p3-fasttext-real-patch \
  --run-fasttext-patch-round \
  --ag-news-train-csv .demo_runs/p2ppp-ag-news-current/train.csv \
  --ag-news-test-csv .demo_runs/p2ppp-ag-news-current/test.csv \
  --fasttext-binary .external/fastText/fasttext \
  --baseline-report .demo_runs/p2ppp-fasttext-real-baseline/fasttext-baseline-report.json \
  --fasttext-proposal .demo_runs/p3-fasttext-real-patch/proposal-wordngrams-2.json \
  --max-train-seconds 900 \
  --json
```

## Proposal

```json
{
  "proposal_id": "p3-fasttext-wordngrams-2",
  "reason": "Codex/Claude-style bounded proposal: add bigram features to improve the trusted local AG News baseline while keeping fixed seed and single-thread execution.",
  "train_args": {
    "-wordNgrams": 2
  }
}
```

当前 allowlist 限制在 fastText supervised 训练参数：

- `-lr`
- `-epoch`
- `-wordNgrams`
- `-dim`
- `-minCount`
- `-loss`

固定参数仍为 `-thread 1 -seed 0`，用于降低 fastText 多线程训练波动。

## 关键 artifacts

输出目录：`.demo_runs/p3-fasttext-real-patch`

- `dataset-provenance.json`
- `fasttext-runtime-probe.json`
- `patch-proposal.json`
- `patch-diff.patch`
- `logs/fasttext-patch-train.log`
- `logs/fasttext-patch-test.log`
- `improvement-report.json`
- `client-handoff.json`
- `patched-model.bin`
- `patched-model.vec`

`patch-diff.patch` 记录训练命令变化：

```diff
--- a/fasttext-train-command
+++ b/fasttext-train-command
@@ -1 +1 @@
-<PROJECT_ROOT>/.external/fastText/fasttext supervised -input data/train.txt -output model -thread 1 -seed 0
+<PROJECT_ROOT>/.external/fastText/fasttext supervised -input data/train.txt -output patched-model -wordNgrams 2 -thread 1 -seed 0
```

`improvement-report.json` 的核心字段：

```json
{
  "stage": "p3_fasttext_patch_round",
  "metric": {
    "baseline_p_at_1": 0.914,
    "p_at_1": 0.916,
    "delta": 0.002,
    "improved": true,
    "within_tolerance": true
  },
  "loop_decision": {
    "decision": "continue_after_human_review",
    "reason_category": "metric_improved",
    "requires_human_confirmation": true
  },
  "official_scores_claimed": false
}
```

## 声明边界

可以说：

- 项目已经在一个真实公开数据 + 真实 fastText runtime 上完成一次受控
  client-proposed patch round。
- 项目可以把 baseline report、proposal、训练命令 diff、训练/评测日志、指标
  对比和 client handoff 串成可复查 artifact。
- 本次 patch 相对已归档 baseline 有小幅正向提升。

不能说：

- 这是官方 leaderboard 成绩。
- 已经完整复现论文所有实验表格。
- 已经证明任意论文都能自动复现或自动提升。
- 已经可以无人值守连续改代码和调参；后续轮次仍需要 human review 决策。

P4 已把本次 patch round 固化为 human-reviewed proof bundle，见
`docs/evidence/fasttext-ag-news-p4-proof-bundle-20260514-cn.md`。
