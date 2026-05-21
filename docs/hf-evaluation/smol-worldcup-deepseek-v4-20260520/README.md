# Smol AI WorldCup DeepSeek V4 本地诊断评测

日期：2026-05-20

本文记录 DeepSeek V4 Flash / Pro 接入 `smol-worldcup-model-eval` 后的完整
125 题本地诊断结果。该结果只用于产品能力验证和模型/provider 对比，不是
Hugging Face 官方提交、hidden-test 结果或 leaderboard 分数。

## 评测口径

- 数据集：`ginigen-ai/smol-worldcup` public train split，125 题。
- Prompt profile：`p3-routing-v1`，用于和历史 `openai/gpt-oss-20b`
  round-003 full-run 保持主要口径一致。
- Judge mode：`openai-compatible`。
- DeepSeek 参数：`thinking_mode=enabled`，`reasoning_effort=high`。
- DeepSeek endpoint：`https://api.deepseek.com`。
- 鉴权：只读取 `DEEPSEEK_API_KEY` 环境变量；artifact 不记录 API key 值。
- 成本：本次 artifact 中的数值来自候选模型调用 token，是修复前生成的
  lower-bound estimate；后续 run 已修正为同时计入 `llm_judge` 的 rubric
  judge token。实际账单还可能因 cache hit 或供应商改价而不同。

## 命令

```bash
ml-loop hf-eval smol-worldcup-model-eval \
  --output-dir .demo_runs/hf-eval/smol-worldcup-deepseek-v4-flash-full-20260520 \
  --model-provider deepseek \
  --model deepseek-v4-flash \
  --prompt-profile p3-routing-v1 \
  --evaluation-split all \
  --judge-mode openai-compatible \
  --judge-model deepseek-v4-flash \
  --thinking-mode enabled \
  --reasoning-effort high \
  --timeout-seconds 240 \
  --max-tokens 512 \
  --round-id deepseek-v4-flash-full-20260520 \
  --json
```

```bash
ml-loop hf-eval smol-worldcup-model-eval \
  --output-dir .demo_runs/hf-eval/smol-worldcup-deepseek-v4-pro-full-20260520 \
  --model-provider deepseek \
  --model deepseek-v4-pro \
  --prompt-profile p3-routing-v1 \
  --evaluation-split all \
  --judge-mode openai-compatible \
  --judge-model deepseek-v4-pro \
  --thinking-mode enabled \
  --reasoning-effort high \
  --timeout-seconds 300 \
  --max-tokens 512 \
  --round-id deepseek-v4-pro-full-20260520 \
  --json
```

## 结果摘要

| Run | H | I | SHIFT | WCS local diagnostic | Failure count | Wall time | Candidate-call lower-bound cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DeepSeek V4 Flash | `70.25` | `44.235294` | `54.641176` | `73.91967` | `65` | `864.464308s` | `$0.01502550` |
| DeepSeek V4 Pro | `68.95` | `43.294118` | `53.556471` | `73.182287` | `69` | `2339.696639s` | `$0.04863517` |
| openai/gpt-oss-20b round-003 | `79.075` | `77.647059` | `78.218235` | `88.441074` | `47` | `348.163824s` | 本地 LM Studio，未估算 API 成本 |

## 关键观察

- 总分口径下，DeepSeek Flash / Pro 都低于历史 `openai/gpt-oss-20b`
  round-003。主要差异来自 `llm_judge`：Flash 为 `22.0%`，Pro 为
  `11.8%`，而历史 gpt-oss round-003 为 `86.0%`。
- 如果只看非 `llm_judge` 的确定性自动评分子集，DeepSeek Pro 为
  `584.8/750 = 77.97%`，DeepSeek Flash 为 `547/750 = 72.93%`，
  历史 gpt-oss round-003 为 `546.3/750 = 72.84%`。这说明 DeepSeek
  Pro 在可自动判分题上并不弱，甚至略优于历史 gpt-oss full-run。
- DeepSeek Flash 比 Pro 更快，candidate-call lower-bound cost 也更低，并且本轮总分略高；Pro 在
  `answer_match`、`code_execution`、`refusal_check` 上更强，但在
  `self_correction_check` 和 `llm_judge` 上被明显拖低。
- 当前使用“模型自评同 provider”作为 rubric judge，不能把 `llm_judge`
  差异简单解释为被测模型能力差异。后续需要新增固定独立 judge provider
  或人工复核抽样，才能更严谨地区分“模型输出质量”和“judge 口径偏差”。

## Top Failure Categories

DeepSeek V4 Flash：

- `multilingual_ko`: 10
- `reasoning`: 7
- `self_correction`: 7
- `confidence_calibration`: 6
- `knowledge_synthesis`: 5
- `metacognition`: 5
- `multilingual_tr`: 5
- `coding`: 4

DeepSeek V4 Pro：

- `knowledge_synthesis`: 9
- `multilingual_ko`: 9
- `self_correction`: 9
- `confidence_calibration`: 7
- `reasoning`: 6
- `metacognition`: 5
- `multilingual_bn`: 5
- `multilingual_th`: 5

历史 gpt-oss round-003：

- `reasoning`: 13
- `confidence_calibration`: 8
- `knowledge_synthesis`: 7
- `metacognition`: 4
- `self_correction`: 4
- `multilingual_pt`: 3
- `multilingual_ko`: 2
- `coding`: 1

## Artifact Paths

- Flash report:
  `.demo_runs/hf-eval/smol-worldcup-deepseek-v4-flash-full-20260520/smol-worldcup-model-eval-report.json`
- Flash predictions:
  `.demo_runs/hf-eval/smol-worldcup-deepseek-v4-flash-full-20260520/prediction.jsonl`
- Pro report:
  `.demo_runs/hf-eval/smol-worldcup-deepseek-v4-pro-full-20260520/smol-worldcup-model-eval-report.json`
- Pro predictions:
  `.demo_runs/hf-eval/smol-worldcup-deepseek-v4-pro-full-20260520/prediction.jsonl`
- Historical gpt-oss comparison report:
  `.demo_runs/hf-eval/smol-worldcup-p3-round-003-judge-20260519/smol-worldcup-model-eval-report.json`

## 结论边界

这次结果证明项目已经可以通过 CLI/MCP 触发 DeepSeek provider 的完整
Smol AI WorldCup 125 题本地诊断、记录失败类型、产生成本估算，并和历史本地
模型 run 做对照。它不证明 DeepSeek 或 gpt-oss 的官方榜单能力，也不证明当前
rubric judge 口径已经足够公平。下一步应补“固定独立 judge provider / 人工抽样
复核”能力，再进入更强的 provider selection 和自动迭代策略。
