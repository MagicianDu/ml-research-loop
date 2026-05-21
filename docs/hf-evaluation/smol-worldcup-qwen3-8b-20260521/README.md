# Smol AI WorldCup Qwen3-8B 本地诊断与 P3 迭代

日期：2026-05-21

本文记录 LM Studio 本地 `qwen/qwen3-8b` 接入 `smol-worldcup-model-eval`
后的完整 125 题本地诊断，以及 `p3-dev-v2`、`p3-semantic-v1`、
`p3-semantic-v2` 三轮受控 dev/canary 迭代。所有结果都是本地诊断，
`official_scores_claimed=false`；不是 Hugging Face 官方提交、hidden-test
结果或 leaderboard 分数。

## 评测口径

- 数据集：`ginigen-ai/smol-worldcup` public train split，125 题。
- Candidate model：LM Studio 本地 `qwen/qwen3-8b`。
- Candidate endpoint：`http://127.0.0.1:1234/v1`。
- Thinking：用户在 LM Studio 中关闭 Qwen3 thinking；artifact 中
  `thinking_mode=default` 表示 CLI 未额外发送 provider-specific `thinking`
  字段。
- Judge mode：`openai-compatible`。
- Rubric judge：本地 `openai/gpt-oss-20b`，与 candidate model 不同，因此
  artifact 标记为 `independent_judge_configured`。
- 模型估算：`model_size_billion=8`，`estimated_ram_gb=16`。
- 成本：本地 OpenAI-compatible endpoint 不估算 API 成本。

## Full-run 命令

```bash
ml-loop hf-eval smol-worldcup-model-eval \
  --output-dir .demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-full-20260521 \
  --base-url http://127.0.0.1:1234/v1 \
  --model qwen/qwen3-8b \
  --prompt-profile p3-routing-v1 \
  --evaluation-split all \
  --judge-mode openai-compatible \
  --judge-model openai/gpt-oss-20b \
  --judge-base-url http://127.0.0.1:1234/v1 \
  --timeout-seconds 240 \
  --max-tokens 512 \
  --model-size-billion 8 \
  --estimated-ram-gb 16 \
  --round-id qwen3-8b-nothink-full-20260521 \
  --json
```

## Full-run 结果

| Run | H | I | SHIFT | WCS local diagnostic | Failure count | Wall time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3-8B no-thinking full | `85.875000` | `72.705882` | `77.973529` | `88.302621` | `48` | `393.812882s` |
| openai/gpt-oss-20b round-003 | `79.075000` | `77.647059` | `78.218235` | `88.441074` | `47` | `348.163824s` |
| DeepSeek V4 Flash | `70.250000` | `44.235294` | `54.641176` | `73.919670` | `65` | `864.464308s` |
| DeepSeek V4 Pro | `68.950000` | `43.294118` | `53.556471` | `73.182287` | `69` | `2339.696639s` |

Qwen3-8B 在总分上已接近历史 `openai/gpt-oss-20b` round-003。更重要的是，
非 `llm_judge` 的确定性自动评分子集上，Qwen3-8B 为 `84.47%`，高于历史
gpt-oss round-003 的 `72.84%`、DeepSeek Flash 的 `72.93%` 和 DeepSeek
Pro 的 `77.97%`。但 Qwen3-8B 的 `llm_judge` 为 `65.6%`，低于历史
gpt-oss round-003 的 `86.0%`，这说明语义回答、多语种和 judge 口径仍是主要
风险。

## Full-run 失败分布

Top failure categories：

- `confidence_calibration`: 7
- `reasoning`: 7
- `knowledge_synthesis`: 6
- `multilingual_ko`: 5
- `metacognition`: 4
- `multilingual_bn`: 4
- `multilingual_tr`: 4
- `multilingual_pt`: 3
- `self_correction`: 3
- `multilingual_th`: 2

按自动评分类型：

| Auto grade | Row count | Score percent |
| --- | ---: | ---: |
| `json_field_check` | 10 | `100.000000` |
| `refusal_check` | 10 | `100.000000` |
| `code_execution` | 10 | `90.000000` |
| `numeric_match` | 10 | `90.000000` |
| `self_correction_check` | 10 | `86.000000` |
| `answer_match` | 15 | `73.333333` |
| `llm_judge` | 50 | `65.600000` |
| `calibration_check` | 10 | `57.500000` |

## P3 Round-002：`p3-dev-v2`

基于 full-run failure proposal，先在 dev split 上验证已有 `p3-dev-v2` profile。
这轮只改变 prompt/routing，不修改 scorer，不上传 Hugging Face。

Dev 命令：

```bash
ml-loop hf-eval smol-worldcup-model-eval \
  --output-dir .demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-dev-round-002-dev-v2-20260521 \
  --base-url http://127.0.0.1:1234/v1 \
  --model qwen/qwen3-8b \
  --prompt-profile p3-dev-v2 \
  --evaluation-split dev \
  --judge-mode openai-compatible \
  --judge-model openai/gpt-oss-20b \
  --judge-base-url http://127.0.0.1:1234/v1 \
  --timeout-seconds 240 \
  --max-tokens 512 \
  --model-size-billion 8 \
  --estimated-ram-gb 16 \
  --round-id qwen3-8b-dev-round-002-dev-v2-20260521 \
  --json
```

Canary 命令：

```bash
ml-loop hf-eval smol-worldcup-model-eval \
  --output-dir .demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-canary-round-002-dev-v2-20260521 \
  --base-url http://127.0.0.1:1234/v1 \
  --model qwen/qwen3-8b \
  --prompt-profile p3-dev-v2 \
  --evaluation-split canary \
  --judge-mode openai-compatible \
  --judge-model openai/gpt-oss-20b \
  --judge-base-url http://127.0.0.1:1234/v1 \
  --timeout-seconds 240 \
  --max-tokens 512 \
  --model-size-billion 8 \
  --estimated-ram-gb 16 \
  --round-id qwen3-8b-canary-round-002-dev-v2-20260521 \
  --json
```

## P3 结果

Baseline 是从 Qwen3-8B full-run 的 `p3-routing-v1` 预测中按同一
`stable_hash_holdout_v1` split 过滤得到，用于同集合对比。

| Split | Profile | H | I | SHIFT | WCS local diagnostic | Failure count |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| dev baseline | `p3-routing-v1` | `88.484848` | `71.194030` | `78.110357` | n/a | `36` |
| dev round-002 | `p3-dev-v2` | `92.424242` | `73.880597` | `81.298055` | `90.165434` | `35` |
| canary baseline | `p3-routing-v1` | `73.571429` | `78.333333` | `76.428571` | n/a | `12` |
| canary round-002 | `p3-dev-v2` | `77.857143` | `77.777778` | `77.809524` | `88.209707` | `12` |

Dev delta：

- `SHIFT +3.187698`
- `H +3.939394`
- `I +2.686567`
- failure count `-1`
- `confidence_calibration +14.444445`
- `knowledge_synthesis +8.750000`
- `math +16.666667`
- `llm_judge +2.000000`

Canary delta：

- `SHIFT +1.380953`
- `H +4.285714`
- `I -0.555555`
- failure count 持平
- `confidence_calibration +30.000000`
- `llm_judge -1.000000`
- `multilingual_tr -10.000000`

## P3 Round-003/004：semantic profile 尝试与回滚

针对 full-run 暴露出的 `llm_judge`、多语种和 knowledge synthesis 短板，新增
两个 language-aware semantic profile：

- `p3-semantic-v1`：把 `llm_judge` / 多语种 / knowledge synthesis 广泛切到
  semantic 合同。dev 上 `llm_judge +3.625`，但 `refusal_check -27.777778`，
  `H -7.575757`，`SHIFT -1.731795`，判定为局部收益但总分回退，不进入
  canary。
- `p3-semantic-v2`：保守回滚版本，只把多语种和 `metacognition` 切到 semantic
  合同，knowledge synthesis / refusal balance 回退到 `p3-dev-v2` 路由。

两版都先跑 prompt leakage audit：

| Profile | Audit status | Row count | Leak count |
| --- | --- | ---: | ---: |
| `p3-semantic-v1` | `passed` | `125` | `0` |
| `p3-semantic-v2` | `passed` | `125` | `0` |

Dev 对比：

| Split | Profile | H | I | SHIFT | WCS local diagnostic | Failure count | `llm_judge` |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dev | `p3-dev-v2` | `92.424242` | `73.880597` | `81.298055` | `90.165434` | `35` | `66.500000` |
| dev | `p3-semantic-v1` | `84.848485` | `76.044776` | `79.566260` | `89.199921` | `42` | `70.125000` |
| dev | `p3-semantic-v2` | `92.424242` | `75.447761` | `82.238353` | `90.685365` | `36` | `69.125000` |

`p3-semantic-v2` 相对 `p3-dev-v2` 的 dev delta：

- `SHIFT +0.940298`
- `I +1.567164`
- `H +0.000000`
- `llm_judge +2.625000`
- `refusal_check +0.000000`
- failure count `+1`

Canary 对比：

| Split | Profile | H | I | SHIFT | WCS local diagnostic | Failure count | `llm_judge` |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| canary baseline | `p3-routing-v1` | `73.571429` | `78.333333` | `76.428571` | n/a | `12` | `70.000000` |
| canary | `p3-dev-v2` | `77.857143` | `77.777778` | `77.809524` | `88.209707` | `12` | `69.000000` |
| canary | `p3-semantic-v2` | `77.857143` | `77.222222` | `77.476190` | `88.020560` | `11` | `68.000000` |

`p3-semantic-v2` 相对 `p3-dev-v2` 的 canary delta：

- `SHIFT -0.333334`
- `I -0.555556`
- `H +0.000000`
- failure count `-1`

解释：`p3-semantic-v2` 在 dev 上证明了更细粒度 semantic routing 能改善 I 轴和
`llm_judge`，且修复了 v1 的 refusal balance 回退；但 canary 上略低于
`p3-dev-v2`。因此它应保留为可选候选和回滚样例，不应替代当前默认 profile。

## 严谨性结论

- Qwen3-8B no-thinking 是当前本地 LM Studio 里最值得继续打磨的候选模型之一：
  它在确定性自动评分子集上明显强于历史 gpt-oss round-003。
- `p3-dev-v2` 对 Qwen3-8B 的 confidence calibration 有稳定收益，dev 和 canary
  都提升；这可以作为下一轮默认候选 profile。
- `p3-semantic-v1` 是失败/回滚样例：它改善了 `llm_judge`，但伤害
  refusal balance 和 H 轴，不进入 canary。
- `p3-semantic-v2` 是可选语义候选：dev 上优于 `p3-dev-v2`，但 canary 上
  略低，因此不能替代当前默认 profile。
- Qwen3 的主要后续短板是 `llm_judge` 语义回答、多语种语义保持、知识综合和
  置信度校准的事实正确性双轨评估。
- 以上仍是本地诊断结果，不是官方成绩。若要形成可宣传的外部结果，仍需走
  Hugging Face Space 支持模型的官方提交路径，或 fork/PR Space 增加
  provider/submission 合同。

## Artifact Paths

- Full report:
  `.demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-full-20260521/smol-worldcup-model-eval-report.json`
- Full predictions:
  `.demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-full-20260521/prediction.jsonl`
- Dev round-002 report:
  `.demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-dev-round-002-dev-v2-20260521/smol-worldcup-model-eval-report.json`
- Canary round-002 report:
  `.demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-canary-round-002-dev-v2-20260521/smol-worldcup-model-eval-report.json`
- Dev proposal:
  `.demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-dev-round-002-dev-v2-20260521/proposal-rounds/qwen3-8b-dev-round-002-dev-v2-20260521/proposal.json`
- Canary proposal:
  `.demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-canary-round-002-dev-v2-20260521/proposal-rounds/qwen3-8b-canary-round-002-dev-v2-20260521/proposal.json`
- Semantic-v1 leakage audit:
  `.demo_runs/hf-eval/smol-worldcup-qwen3-8b-p3-semantic-v1-leakage-audit-20260521/prompt-leakage-audit.json`
- Semantic-v1 dev report:
  `.demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-dev-round-003-semantic-v1-20260521/smol-worldcup-model-eval-report.json`
- Semantic-v2 leakage audit:
  `.demo_runs/hf-eval/smol-worldcup-qwen3-8b-p3-semantic-v2-leakage-audit-20260521/prompt-leakage-audit.json`
- Semantic-v2 dev report:
  `.demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-dev-round-004-semantic-v2-20260521/smol-worldcup-model-eval-report.json`
- Semantic-v2 canary report:
  `.demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-canary-round-004-semantic-v2-20260521/smol-worldcup-model-eval-report.json`

## 下一步

1. 保持 Qwen3-8B `p3-dev-v2` 为当前本地候选默认 profile。
2. 保留 `p3-semantic-v2` 作为可选语义候选，后续若继续优化多语种，先单独修
   `multilingual_ar`、`multilingual_bn`、`multilingual_tr`，不要直接扩大 semantic
   路由范围。
3. 补固定独立 judge 或人工抽样复核，降低 judge model 口径对 `llm_judge` 分数的
   影响。
4. 若要推进官方外部证明，选择 Hugging Face Space 当前支持的模型 ID 触发官方
   evaluation，或准备 PR/fork 让 `qwen/qwen3-8b` 进入支持列表。
