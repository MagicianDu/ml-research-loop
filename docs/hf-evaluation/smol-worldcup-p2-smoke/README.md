# Smol AI WorldCup P2 本地模型评测 Smoke

本目录记录 2026-05-18 的 P2 接入验收结论。完整原始运行 artifact 写在本地 `.demo_runs/hf-eval/`，该目录只保存可提交的摘要，避免把本机临时运行目录直接纳入仓库。

## 运行入口

CLI smoke：

```bash
ml-loop hf-eval smol-worldcup-model-eval \
  --output-dir .demo_runs/hf-eval/smol-worldcup-p2-smoke \
  --base-url http://127.0.0.1:1234/v1 \
  --model openai/gpt-oss-20b \
  --limit 3 \
  --timeout-seconds 180 \
  --max-tokens 256 \
  --json
```

MCP smoke：

```python
from lib import mcp_service

mcp_service.run_smol_worldcup_model_eval_tool({
    "output_dir": ".demo_runs/hf-eval/smol-worldcup-p2-mcp-smoke",
    "base_url": "http://127.0.0.1:1234/v1",
    "model": "openai/gpt-oss-20b",
    "limit": 1,
    "timeout_seconds": 180,
    "max_tokens": 256,
})
```

## 结果摘要

| 入口 | 样本数 | 模型 | H | I | SHIFT | WCS_local_diagnostic | 声明边界 |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| CLI | 3 | `openai/gpt-oss-20b` via LM Studio | 66.666667 | 0.0 | 26.666667 | 0.0 | 本地评测，不是 HF leaderboard |
| MCP | 1 | `openai/gpt-oss-20b` via LM Studio | 0.0 | 0.0 | 0.0 | 0.0 | 本地评测，不是 HF leaderboard |

CLI artifact：

- `.demo_runs/hf-eval/smol-worldcup-p2-smoke/smol-worldcup-model-eval-report.json`
- `.demo_runs/hf-eval/smol-worldcup-p2-smoke/prediction.jsonl`
- `.demo_runs/hf-eval/smol-worldcup-p2-smoke/score-breakdown.json`
- `.demo_runs/hf-eval/smol-worldcup-p2-smoke/failure-cases.json`
- `.demo_runs/hf-eval/smol-worldcup-p2-smoke/runtime-profile.json`
- `.demo_runs/hf-eval/smol-worldcup-p2-smoke/proposal-rounds/round-001/proposal.json`
- `.demo_runs/hf-eval/smol-worldcup-p2-smoke/multi-round-report.json`

MCP artifact：

- `.demo_runs/hf-eval/smol-worldcup-p2-mcp-smoke/smol-worldcup-model-eval-report.json`
- `.demo_runs/hf-eval/smol-worldcup-p2-mcp-smoke/prediction.jsonl`
- `.demo_runs/hf-eval/smol-worldcup-p2-mcp-smoke/score-breakdown.json`
- `.demo_runs/hf-eval/smol-worldcup-p2-mcp-smoke/failure-cases.json`
- `.demo_runs/hf-eval/smol-worldcup-p2-mcp-smoke/runtime-profile.json`
- `.demo_runs/hf-eval/smol-worldcup-p2-mcp-smoke/proposal-rounds/round-001/proposal.json`
- `.demo_runs/hf-eval/smol-worldcup-p2-mcp-smoke/multi-round-report.json`

## 结论

- `smol-worldcup-model-eval` 已能从 CLI 调用 LM Studio 本地 OpenAI-compatible endpoint。
- `run_smol_worldcup_model_eval` 已能从 MCP 工具层触发同一路径，适合 Codex/Claude 调用。
- 输出已经包含 prediction、score breakdown、failure cases、runtime profile、proposal round 和 multi-round report。
- 当前只是 smoke，不代表完整 125 题评测，也不是 Hugging Face 官方提交或榜单分数。
