# Smol AI WorldCup P3 Round-002 迭代结果

本文记录 2026-05-18 的 Smol AI WorldCup 本地完整评测和第一轮 P3 proposal/迭代。所有指标都是本地诊断指标，`official_scores_claimed=false`；它们不是 Hugging Face leaderboard 成绩，也不是官方 WCS。

## 运行入口

Round-001 完整本地模型评测：

```bash
ml-loop hf-eval smol-worldcup-model-eval \
  --output-dir .demo_runs/hf-eval/smol-worldcup-p2-full-20260518 \
  --base-url http://127.0.0.1:1234/v1 \
  --model openai/gpt-oss-20b \
  --timeout-seconds 180 \
  --max-tokens 256 \
  --round-id round-001 \
  --json
```

Round-002 P3 routing 迭代：

```bash
ml-loop hf-eval smol-worldcup-model-eval \
  --output-dir .demo_runs/hf-eval/smol-worldcup-p3-round-002-20260518 \
  --base-url http://127.0.0.1:1234/v1 \
  --model openai/gpt-oss-20b \
  --timeout-seconds 180 \
  --max-tokens 256 \
  --round-id round-002 \
  --prompt-profile p3-routing-v1 \
  --json
```

MCP profile smoke：

```python
from lib import mcp_service

mcp_service.run_smol_worldcup_model_eval_tool({
    "output_dir": ".demo_runs/hf-eval/smol-worldcup-p3-mcp-profile-smoke-20260518",
    "base_url": "http://127.0.0.1:1234/v1",
    "model": "openai/gpt-oss-20b",
    "limit": 1,
    "timeout_seconds": 180,
    "max_tokens": 256,
    "round_id": "round-002-mcp-smoke",
    "prompt_profile": "p3-routing-v1",
})
```

## 指标结果

| Round | 样本数 | Prompt profile | H | I | SHIFT | WCS local diagnostic | Failure count |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| round-001 artifact | 125 | `default` | 65.75 | 34.080086 | 46.748052 | 68.372547 | 89 |
| round-001 rescored | 125 | `default` | 65.75 | 38.785968 | 49.571581 | 未重算 | 85 |
| round-002 | 125 | `p3-routing-v1` | 80.25 | 43.037029 | 57.922217 | 76.106647 | 74 |

对比原始 round-001 artifact：

- `H +14.5`
- `I +8.956943`
- `SHIFT +11.174165`
- `WCS_local_diagnostic +7.7341`
- failure count `-15`

对比修复 scorer 后的 round-001 rescored：

- `H +14.5`
- `I +4.251061`
- `SHIFT +8.350636`
- failure count `-11`

## 主要变化

P3 改动包含两部分：

- scorer 修复：本地 code scorer 现在会从 JSON `code` 或 `answer` 字段提取 Python 代码，避免把模型返回的合法代码 JSON 当作整段 Python 执行。
- prompt routing：新增 `prompt_profile=p3-routing-v1`，按 `auto_grade` / category 调整输出约束。`code_execution` 题要求只返回可执行 Python，`answer_match` / `numeric_match` 题要求短答案 JSON，其他语义题要求保留语言并避免不必要拒答。

改善最明显的类别：

- `coding`：round-001 rescored 后为 `40.0`，round-002 为 `90.0`。
- `hallucination_trap`：`80.0` 提升到 `100.0`。
- `refusal_balance`：`50.0` 提升到 `90.0`。

仍然薄弱或退化的类别：

- `knowledge_synthesis`：仍为 `0.0`，当前 heuristic LLM-judge fallback 对语义质量覆盖不足。
- `metacognition`：仍为 `0.0`，需要更强 rubric/LLM judge 或专门 prompt。
- `reasoning`：`30.0` 降到 `26.666667`，短答案 routing 没有解决 expected-answer 口径问题。
- 多语种任务整体仍弱，韩语、阿拉伯语、土耳其语等仍需专门 routing 或更强 judge。

## 结论

P3 已经形成可运行的 proposal/迭代闭环：完整 round-001 -> failure proposal -> scorer/prompt patch -> 完整 round-002 -> 指标对比。当前可以谨慎宣传“本地 Smol AI WorldCup 诊断指标经一轮受控迭代提升”，但不能宣传 Hugging Face 官方提交、官方排名或官方 WCS。

下一轮建议优先做两件事：

- 引入更真实的 LLM/rubric judge，避免 `knowledge_synthesis` 和 `metacognition` 被当前 heuristic fallback 低估。
- 针对 `reasoning` 和多语种类别做第二轮 routing，而不是继续泛化同一个 prompt。
