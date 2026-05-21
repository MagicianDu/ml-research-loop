# Smol WorldCup / Qwen3 Proposal Context 样例

这个目录是 `proposal context` 的真实本地诊断样例。它压缩自
`docs/hf-evaluation/smol-worldcup-qwen3-8b-20260521/README.md`、
`docs/hf-evaluation/smol-worldcup-p3-round-004-dev-v2/README.md` 和
`docs/evidence/proof-archives/smol-worldcup-round-004-*-formal-rescore-20260520/`。

边界：所有指标都是 local diagnostic。这里没有 Hugging Face official score、
leaderboard score、hidden-test score 或官方 WCS。formal rescore 只证明既有
prediction 的本地 scorer-v2 复核 artifact 可复查，不是新模型运行。

## 本地命令

```bash
.venv/bin/ml-loop proposal context \
  --objective "为 Smol WorldCup Qwen3-8B 本地 prompt/profile 迭代生成受控 proposal" \
  --output-dir .demo_runs/proposal-contract/smol-qwen3-context \
  --baseline-report examples/proposal-contract/smol-qwen3/baseline-report.json \
  --current-report examples/proposal-contract/smol-qwen3/current-report.json \
  --dev-report examples/proposal-contract/smol-qwen3/dev-report.json \
  --canary-report examples/proposal-contract/smol-qwen3/canary-report.json \
  --category-deltas examples/proposal-contract/smol-qwen3/category-deltas.json \
  --failure-samples examples/proposal-contract/smol-qwen3/failure-samples.json \
  --rollback-summary examples/proposal-contract/smol-qwen3/rollback-summary.json \
  --previous-proposals examples/proposal-contract/smol-qwen3/previous-proposals.json \
  --memory-cards examples/proposal-contract/smol-qwen3/memory-cards.json \
  --allowed-change-surface prompt_profile \
  --allowed-change-surface routing \
  --max-proposals 2 \
  --force \
  --json
```

如果本机已经把项目 entry point 安装到 PATH，也可以把 `.venv/bin/ml-loop`
替换为 `ml-loop`。`resource-constraints.json` 当前不是 CLI 文件参数；MCP `build_proposal_context`
可通过 `resource_constraints` inline 传入同等内容。CLI 使用时把它作为客户端
读入材料即可。

## 文件说明

- `baseline-report.json`：Qwen3-8B `p3-routing-v1` full-run 与同 split baseline。
- `current-report.json`：当前可保守推进的 `p3-dev-v2` dev/canary 结果。
- `dev-report.json`：`p3-semantic-v2` dev 结果，显示局部语义收益。
- `canary-report.json`：`p3-semantic-v2` canary 结果，未确认替代默认 profile。
- `category-deltas.json`：关键类别和指标 delta 摘要。
- `failure-samples.json`：可读的失败模式样例，不包含完整 prediction。
- `rollback-summary.json`：semantic-v1 回滚与 semantic-v2 保留边界。
- `previous-proposals.json`：已尝试 profile 的 proposal 历史。
- `memory-cards.json`：用于约束 proposal 的路线记忆。
- `resource-constraints.json`：本地资源、轮次和 claim guardrail。
- `proposal.json`：一个符合 contract 的下一步候选 proposal。
- `evaluation-payload.json`：对 `proposal.json` 的本地候选评估占位与 gate 口径。
- `artifact-sources.json`：本样例引用的上游 artifact 和文档依据。
