# fastText AG News P5 多轮 proposal 与 release proof bundle

## 结论边界

本证据证明 ML Research Loop 已能在 fastText AG News 轨道上执行多轮客户端 proposal，保留失败轮次和 best-so-far 回滚记录，并把 P4/P5 证据打包成可下载、可 checksum 复核的 release proof bundle。

它不证明官方 leaderboard 成绩、不证明论文所有表格完整复现，也不证明任意论文或模型都能无人值守自动优化。所有 artifact 保持 `official_scores_claimed=false`。

## 运行输入

- target spec：`docs/reproduction-pilot/full-reproduction-target.json`
- train CSV：`.demo_runs/p2ppp-ag-news-current/train.csv`
- test CSV：`.demo_runs/p2ppp-ag-news-current/test.csv`
- fastText binary：`.external/fastText/fasttext`
- baseline report：`.demo_runs/p2ppp-fasttext-real-baseline/fasttext-baseline-report.json`
- P4 proof manifest：`.demo_runs/p4-fasttext-real-proof/proof-manifest.json`
- proposal list：`.demo_runs/p5-fasttext-real/proposals.json`

## 多轮 proposal 命令

```bash
.venv/bin/python scripts/full_reproduction_run.py \
  --target-spec docs/reproduction-pilot/full-reproduction-target.json \
  --output-dir .demo_runs/p5-fasttext-real/multi-round \
  --run-fasttext-multi-proposal-loop \
  --ag-news-train-csv .demo_runs/p2ppp-ag-news-current/train.csv \
  --ag-news-test-csv .demo_runs/p2ppp-ag-news-current/test.csv \
  --fasttext-binary .external/fastText/fasttext \
  --baseline-report .demo_runs/p2ppp-fasttext-real-baseline/fasttext-baseline-report.json \
  --fasttext-proposals .demo_runs/p5-fasttext-real/proposals.json \
  --max-train-seconds 900 \
  --json
```

## 多轮结果

- status：`completed_with_failures`
- baseline：`P@1=0.914`
- best metric：`P@1=0.916`
- best source：`round-001-p5-wordngrams-2`
- proposal count：`2`
- completed count：`1`
- failure count：`1`
- rollback events：`1`
- `official_scores_claimed=false`

两轮 proposal：

1. `p5-wordngrams-2`：allowlisted `wordNgrams=2`，完成训练/评测，保持当前最佳 `P@1=0.916`。
2. `p5-invalid-bucket`：非 allowlist 参数 `bucket=100`，被记录为失败轮次，回滚策略为 `keep_best_so_far`。

核心 artifact：

- `.demo_runs/p5-fasttext-real/multi-round/multi-round-report.json`
- `.demo_runs/p5-fasttext-real/multi-round/client-handoff.json`
- `.demo_runs/p5-fasttext-real/multi-round/rounds/round-001-p5-wordngrams-2/improvement-report.json`

## Release proof bundle 命令

```bash
.venv/bin/python scripts/full_reproduction_run.py \
  --target-spec docs/reproduction-pilot/full-reproduction-target.json \
  --output-dir .demo_runs/p5-fasttext-real/release-proof \
  --write-fasttext-release-proof-bundle \
  --proof-manifest .demo_runs/p4-fasttext-real-proof/proof-manifest.json \
  --multi-round-report .demo_runs/p5-fasttext-real/multi-round/multi-round-report.json \
  --reviewer codex-local-review \
  --json
```

## Release proof 结果

- release manifest：`.demo_runs/p5-fasttext-real/release-proof/release-proof-manifest.json`
- review checklist：`.demo_runs/p5-fasttext-real/release-proof/release-review-checklist.md`
- download bundle：`.demo_runs/p5-fasttext-real/release-proof/release-proof-bundle.tar.gz`
- checksum file：`.demo_runs/p5-fasttext-real/release-proof/release-proof-bundle.sha256`
- bundle sha256：`7e48e9d50934d476bcd57dfdd6925db4eb4cd646fec2f9f76624108be16bbf45`

已执行复核：

```bash
cd .demo_runs/p5-fasttext-real/release-proof
shasum -a 256 -c release-proof-bundle.sha256
```

结果为：

```text
release-proof-bundle.tar.gz: OK
```

bundle 内容包含：

- `p4-proof/proof-manifest.json`
- `p4-proof/artifact-index.json`
- `p4-proof/SHA256SUMS`
- `p4-proof/human-review-report.json`
- `p4-proof/artifacts/improvement-report.json`
- `p4-proof/artifacts/patch-diff.patch`
- `p4-proof/artifacts/fasttext-patch-train.log`
- `p4-proof/artifacts/fasttext-patch-test.log`
- `p5-multi-round/multi-round-report.json`

## 可以宣传什么

可以宣传：

- fastText AG News 轨道已有真实本地 baseline、一次受控改进、人工复核 proof bundle。
- P5 增强了多轮 proposal、失败样例、回滚摘要和 release bundle 下载/复核路径。
- Codex/Claude 可以作为 planner 生成 proposal；MCP 作为 bounded executor 运行、归档、打包证据。

不能宣传：

- 不能说这是官方 fastText leaderboard 成绩。
- 不能说已经完整复现论文全部实验表格。
- 不能说系统可以无人值守自动完成任意论文复现或任意模型优化。
