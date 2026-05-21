# Smol AI WorldCup P3 Round-003 Rubric Judge 结果

本文记录 2026-05-19 的 Smol AI WorldCup 本地完整评测。Round-003 在 `prompt_profile=p3-routing-v1` 的基础上，把 `llm_judge` 类题目从 heuristic fallback 切换为本地 OpenAI-compatible rubric judge。

所有指标仍是本地诊断指标，`official_scores_claimed=false`；它们不是 Hugging Face leaderboard 成绩，也不是官方 WCS。

## 运行入口

Round-003 完整 125 题评测：

```bash
ml-loop hf-eval smol-worldcup-model-eval \
  --output-dir .demo_runs/hf-eval/smol-worldcup-p3-round-003-judge-20260519 \
  --base-url http://127.0.0.1:1234/v1 \
  --model openai/gpt-oss-20b \
  --timeout-seconds 180 \
  --max-tokens 256 \
  --round-id round-003 \
  --prompt-profile p3-routing-v1 \
  --judge-mode openai-compatible \
  --judge-model openai/gpt-oss-20b \
  --json
```

CLI/MCP 参数已经支持：

- `judge_mode=heuristic`
- `judge_mode=openai-compatible`
- `judge_model`
- `judge_base_url`

MCP 客户端调用 `run_smol_worldcup_model_eval` 时可以传入同名字段。

## 指标结果

| Round | 样本数 | Prompt profile | Judge mode | H | I | SHIFT | WCS local diagnostic | Failure count |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| round-001 artifact | 125 | `default` | `heuristic` | 65.75 | 34.080086 | 46.748052 | 68.372547 | 89 |
| round-001 rescored | 125 | `default` | `heuristic` | 65.75 | 38.785968 | 49.571581 | 未重算 | 85 |
| round-002 | 125 | `p3-routing-v1` | `heuristic` | 80.25 | 43.037029 | 57.922217 | 76.106647 | 74 |
| round-003 | 125 | `p3-routing-v1` | `openai-compatible` | 79.075 | 77.647059 | 78.218235 | 88.441074 | 47 |

对比 round-002：

- `H -1.175`
- `I +34.610030`
- `SHIFT +20.296018`
- `WCS_local_diagnostic +12.334427`
- failure count `-27`

对比原始 round-001 artifact：

- `H +13.325`
- `I +43.566973`
- `SHIFT +31.470183`
- `WCS_local_diagnostic +20.068527`
- failure count `-42`

## 解释边界

Round-003 不是单纯的模型能力提升实验。它同时改变了评测路径：

- round-002 的 `llm_judge` 题使用 heuristic fallback，容易低估 `knowledge_synthesis`、`metacognition` 和多语种语义题。
- round-003 使用本地 OpenAI-compatible rubric judge，因此更接近真实语义评审路径。
- 当前 judge model 仍是本地 `openai/gpt-oss-20b`，不是官方 judge，也不是独立第三方评审。

因此，round-003 的提升可以谨慎表述为：“本地评测系统补齐了真实 rubric judge 路径，并在该诊断口径下得到更高的 semantic task 分数”。不能表述为：“模型在官方榜单上提升了 20 分”或“已经取得 Hugging Face 官方成绩”。

## 严谨性补强

2026-05-19 之后，Smol AI WorldCup 本地评测新增三项 guardrail：

- Prompt leakage audit：`write_smol_worldcup_prompt_leakage_audit` / `ml-loop hf-eval smol-worldcup-leakage-audit` 会检查模型 prompt 中是否出现 `answer_key`、`grading_rule`、`test_case`、`correct_answer` 等 evaluation-only marker。
- Dev/canary split：baseline 和 model eval 支持 `evaluation_split=all|dev|canary`，默认 `canary_fraction=0.2`，使用 `stable_hash_holdout_v1` 固定切分。
- Judge independence metadata：`judge_mode=openai-compatible` 会记录 `judge_independence.status`。同一模型和同一 endpoint 会标记为 `self_judge`；不同 judge model 或不同 endpoint 会标记为 `independent_judge_configured`。

已执行一次真实 prompt leakage audit：

```bash
ml-loop hf-eval smol-worldcup-leakage-audit \
  --output-dir .demo_runs/hf-eval/smol-worldcup-p3-leakage-audit-20260519 \
  --prompt-profile p3-routing-v1 \
  --json
```

结果：`status=passed`、`row_count=125`、`leak_count=0`。artifact 为 `.demo_runs/hf-eval/smol-worldcup-p3-leakage-audit-20260519/prompt-leakage-audit.json`。

也已执行一次 canary baseline：

```bash
ml-loop hf-eval smol-worldcup-baseline \
  --output-dir .demo_runs/hf-eval/smol-worldcup-canary-baseline-20260519 \
  --evaluation-split canary \
  --json
```

结果：`source_row_count=125`、`row_count=25`、`evaluation_split=canary`。注意：历史 round-001/002/003 已经使用过全部公开 125 题，所以这个 canary split 只能作为此版本之后的未来 holdout 纪律，不能回溯声明历史轮次使用了 untouched holdout。

## 类别表现

改善最明显的是 `llm_judge` 覆盖的语义类任务：

- `knowledge_synthesis`：`79.0`
- `metacognition`：`86.0`
- 多语种类别普遍达到 `82.0` 到 `98.0`
- `llm_judge` auto grade 总分：`86.0`

仍然薄弱的类别：

- `reasoning`：`26.666667`，仍受 expected-answer 口径和短答案匹配限制影响。
- `confidence_calibration`：`59.3`，部分题目因为 confidence 与本地 answer matcher 口径不一致被扣分。
- `self_correction`：`62.0`，当前 prompt 仍不能稳定触发可评分的自我纠错结构。

## 产物

主要 artifact：

- `.demo_runs/hf-eval/smol-worldcup-p3-round-003-judge-20260519/smol-worldcup-model-eval-report.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-round-003-judge-20260519/prediction.jsonl`
- `.demo_runs/hf-eval/smol-worldcup-p3-round-003-judge-20260519/score-breakdown.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-round-003-judge-20260519/failure-cases.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-round-003-judge-20260519/runtime-profile.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-round-003-judge-20260519/proposal-rounds/round-003/proposal.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-round-003-judge-20260519/multi-round-report.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-leakage-audit-20260519/prompt-leakage-audit.json`
- `.demo_runs/hf-eval/smol-worldcup-canary-baseline-20260519/smol-worldcup-baseline-report.json`

运行画像：

- `row_count=125`
- `wall_time_seconds=348.163824`
- `throughput_items_per_second=0.359026`
- `estimated_tokens_per_second=25.6948`
- `input_tokens_estimate=30119`
- `output_tokens_estimate=16419`

## 结论

P3 当前已经形成第二层闭环：

1. 完整 round-001 本地模型评测。
2. 基于失败样例生成 proposal。
3. 修复 code scorer 并执行 `p3-routing-v1`。
4. 补齐 OpenAI-compatible rubric judge。
5. 完整 round-003 产出可复核 artifact、失败样例、runtime profile 和下一轮 proposal。

下一轮不应继续只调通用 prompt，而应拆成两条：

- 做 `reasoning` 专用 answer normalizer 或 expected-answer 口径审查。
- 做 `confidence_calibration` 与 `self_correction` 的结构化 prompt 和 scorer 对齐。

后续 round-004 已按这个方向新增 `prompt_profile=p3-dev-v2`，并在 dev/canary split 下完成一次受控检查。详见 [../smol-worldcup-p3-round-004-dev-v2/README.md](../smol-worldcup-p3-round-004-dev-v2/README.md)。
