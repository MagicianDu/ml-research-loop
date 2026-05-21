# Smol AI WorldCup P3 Round-004 Dev-v2 结果

本文记录 2026-05-19 的 Smol AI WorldCup 本地 dev/canary 评测。Round-004 新增 `prompt_profile=p3-dev-v2`，只针对 dev split 中暴露出的 `reasoning`、`confidence_calibration` 和 `self_correction` 失败模式做 prompt/routing 约束。

所有指标仍是本地诊断指标，`official_scores_claimed=false`；它们不是 Hugging Face leaderboard 成绩，也不是官方 WCS。

## 改动范围

`p3-dev-v2` 是 dev-only 的受控 prompt profile：

- `code_execution` / `coding` 继续复用 `p3-routing-v1` 的纯 Python 输出约束。
- `reasoning` / `answer_match` / `numeric_match` 要求输出 canonical human-readable answer，避免只返回裸数字或裸 yes/no。
- `confidence_calibration` 要求输出 `answer`、`confidence`、`reasoning` 和 `uncertainty_note`，并对 source-sensitive / unverifiable / under-specified 题目使用低置信度。
- `self_correction` 要求输出 `initial_answer`、`review`、`found_error`、`final_answer` 和 `confidence`，并在 `final_answer` 前做 manual check。

这轮没有修改 scorer，也没有上传 Hugging Face。

## 运行命令

Prompt leakage audit：

```bash
ml-loop hf-eval smol-worldcup-leakage-audit \
  --output-dir .demo_runs/hf-eval/smol-worldcup-p3-dev-v2-leakage-audit-20260519 \
  --prompt-profile p3-dev-v2 \
  --json
```

Dev 对照组：

```bash
ml-loop hf-eval smol-worldcup-model-eval \
  --output-dir .demo_runs/hf-eval/smol-worldcup-p3-dev-round-003-routing-20260519 \
  --base-url http://127.0.0.1:1234/v1 \
  --model openai/gpt-oss-20b \
  --timeout-seconds 180 \
  --max-tokens 256 \
  --round-id round-003-dev-routing \
  --prompt-profile p3-routing-v1 \
  --evaluation-split dev \
  --judge-mode openai-compatible \
  --judge-model openai/gpt-oss-20b \
  --json
```

Dev 新 profile：

```bash
ml-loop hf-eval smol-worldcup-model-eval \
  --output-dir .demo_runs/hf-eval/smol-worldcup-p3-dev-round-004-dev-v2-20260519 \
  --base-url http://127.0.0.1:1234/v1 \
  --model openai/gpt-oss-20b \
  --timeout-seconds 180 \
  --max-tokens 256 \
  --round-id round-004-dev-v2 \
  --prompt-profile p3-dev-v2 \
  --evaluation-split dev \
  --judge-mode openai-compatible \
  --judge-model openai/gpt-oss-20b \
  --json
```

Canary 最终检查：

```bash
ml-loop hf-eval smol-worldcup-model-eval \
  --output-dir .demo_runs/hf-eval/smol-worldcup-p3-canary-round-004-dev-v2-20260519 \
  --base-url http://127.0.0.1:1234/v1 \
  --model openai/gpt-oss-20b \
  --timeout-seconds 180 \
  --max-tokens 256 \
  --round-id round-004-canary-dev-v2 \
  --prompt-profile p3-dev-v2 \
  --evaluation-split canary \
  --judge-mode openai-compatible \
  --judge-model openai/gpt-oss-20b \
  --json
```

## 结果

| Run | Split | 样本数 | Prompt profile | H | I | SHIFT | WCS local diagnostic | Failure count |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| round-003-dev-routing | dev | 100 | `p3-routing-v1` | 77.696970 | 76.716418 | 77.108639 | 87.811525 | 38 |
| round-004-dev-v2 | dev | 100 | `p3-dev-v2` | 77.727273 | 78.955224 | 78.464044 | 88.579932 | 38 |
| round-004-canary-dev-v2 | canary | 25 | `p3-dev-v2` | 85.000000 | 75.555556 | 79.333334 | 89.069262 | 10 |

Dev 对比：

- `SHIFT +1.355405`
- `WCS_local_diagnostic +0.768407`
- `H +0.030303`
- `I +2.238806`
- failure count 持平为 `38`

目标类别 dev 变化：

| Category | round-003 dev | round-004 dev |
| --- | ---: | ---: |
| `reasoning` | 29.166667 | 41.666667 |
| `confidence_calibration` | 54.888889 | 55.000000 |
| `self_correction` | 65.000000 | 65.000000 |

Canary 只跑了一次，用于检查 dev 改动是否明显崩坏；不能继续根据 canary 反向调 prompt，否则会破坏 holdout 纪律。

## Scorer-v2 审计

2026-05-19 追加完成 scorer 口径审计和 deterministic rescoring。2026-05-20 已把该流程固化为正式 CLI/MCP 能力：CLI 命令为 `ml-loop hf-eval smol-worldcup-rescore`，MCP 工具为 `run_smol_worldcup_rescore`。改动范围：

- `answer_match` / `numeric_match` 增加 response normalizer：优先抽取 `final_answer` / `answer`，支持 JSON 响应、解释性括号、选项前缀和解释性破折号后缀。
- `confidence_calibration` 对齐公开 Space app 的 `expected_confidence` band 口径：`high`、`medium_high`、`medium`、`low_medium`、`low`、`very_low`。
- `self_correction` 对齐公开 Space app 的 `final_answer` 口径：优先判断 `final_answer` 是否匹配正确答案；若未匹配但 `found_error=true`，给部分分。

Rescore 只重算 deterministic scorer；已有 `llm_judge` 分数保留原 rubric judge 结果，不退回 heuristic。

| Run | Rescore profile | H | I | SHIFT | WCS local diagnostic | Failure count | Changed score count |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| round-003-dev-routing | scorer-v2 | 85.909091 | 82.835821 | 84.065129 | 91.687038 | 32 | 18 |
| round-004-dev-v2 | scorer-v2 | 89.393939 | 84.925373 | 86.712799 | 93.119708 | 30 | 19 |
| round-004-canary-dev-v2 | scorer-v2 | 77.857143 | 84.444444 | 81.809524 | 90.448617 | 9 | 5 |

Round-004 dev 目标类别 scorer-v2 后：

| Category | scorer-v1 | scorer-v2 |
| --- | ---: | ---: |
| `reasoning` | 41.666667 | 75.000000 |
| `confidence_calibration` | 55.000000 | 75.555556 |
| `self_correction` | 65.000000 | 90.000000 |

解释边界：

- 这说明此前本地 scorer 对短答案、`final_answer` 和 expected confidence band 存在低估。
- 这不是新的模型输出，也不是 Hugging Face 官方成绩。
- `confidence_calibration` 的 Space-app-style 口径主要检查 confidence 是否落在 expected band；它不等价于严格事实正确性评测。正式 rescore artifact 已增加 `confidence-calibration-audit.json`，把 expected confidence band 和 answer correctness 分开报告。
- Round-004 dev 正式 rescore 的 confidence 双轨结果为：`band_score_percent=75.555556`，`answer_correctness_percent=44.444444`。Round-004 canary 正式 rescore 的 confidence 双轨结果为：`band_score_percent=25.0`，`answer_correctness_percent=100.0`。

## Proof Archive 与 HF Submission Probe

2026-05-20 已把 formal scorer-v2 rescore 归档为 proof archive：

| Archive | Status | Artifact count | SHIFT | WCS local diagnostic |
| --- | --- | ---: | ---: | ---: |
| `docs/evidence/proof-archives/smol-worldcup-round-004-dev-formal-rescore-20260520/proof-archive.json` | `archivable` | 12 | 86.712799 | 93.119708 |
| `docs/evidence/proof-archives/smol-worldcup-round-004-canary-formal-rescore-20260520/proof-archive.json` | `archivable` | 12 | 81.809524 | 90.448617 |

这些 archive 只证明 formal rescore artifact、命令、配置、环境、日志、报告、限制说明和 hash index 可复核；`official_scores_claimed=false`，不是 Hugging Face submission，也不是 leaderboard 结果。

同日新增 HF submission path probe：`docs/hf-evaluation/smol-worldcup-submission-probe-20260520/hf-submission-path.md`。当前结论：

- `/evaluate/gradio_api/openapi.json` 暴露 `start_eval`。
- Space 当前接受 13 个固定模型 ID。
- Gradio config 标记 `allow_custom_value=true`，但 Space source 中 `model_id not in SUPPORTED_MODELS` 的校验会阻止不在固定列表里的模型。
- 本地 `openai/gpt-oss-20b` / LM Studio predictions 当前不能直接作为该 Space 的官方提交结果。

## 严谨性结论

- Prompt leakage audit 通过：`row_count=125`、`leak_count=0`，artifact 为 `.demo_runs/hf-eval/smol-worldcup-p3-dev-v2-leakage-audit-20260519/prompt-leakage-audit.json`。
- Dev split 上 `p3-dev-v2` 相对 `p3-routing-v1` 有小幅正向提升，主要来自 `reasoning` 题目。
- Scorer-v2 rescore 显示 `reasoning`、`confidence_calibration` 和 `self_correction` 的大量失败属于本地 scorer 口径低估；后续不应把 scorer-v1 到 scorer-v2 的跃升宣传为模型能力提升。
- Canary 结果没有显示明显崩坏，但它仍是公开数据集上的本地 holdout 纪律，不是 hidden test，也不是官方成绩。
- Judge model 与 candidate model 都是本地 `openai/gpt-oss-20b`，因此 judge independence 为 self-judge 风险；更严谨的路线需要独立 judge model 或外部评审。

## 产物

主要 artifact：

- `.demo_runs/hf-eval/smol-worldcup-p3-dev-v2-leakage-audit-20260519/prompt-leakage-audit.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-dev-round-003-routing-20260519/smol-worldcup-model-eval-report.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-dev-round-003-routing-20260519/score-breakdown.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-dev-round-004-dev-v2-20260519/smol-worldcup-model-eval-report.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-dev-round-004-dev-v2-20260519/score-breakdown.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-canary-round-004-dev-v2-20260519/smol-worldcup-model-eval-report.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-canary-round-004-dev-v2-20260519/score-breakdown.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-dev-round-003-routing-20260519-scorer-v2-rescore/smol-worldcup-rescore-report.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-dev-round-004-dev-v2-20260519-scorer-v2-rescore/smol-worldcup-rescore-report.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-canary-round-004-dev-v2-20260519-scorer-v2-rescore/smol-worldcup-rescore-report.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-dev-round-004-dev-v2-20260520-formal-scorer-v2-rescore/smol-worldcup-rescore-report.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-dev-round-004-dev-v2-20260520-formal-scorer-v2-rescore/confidence-calibration-audit.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-canary-round-004-dev-v2-20260520-formal-scorer-v2-rescore/smol-worldcup-rescore-report.json`
- `.demo_runs/hf-eval/smol-worldcup-p3-canary-round-004-dev-v2-20260520-formal-scorer-v2-rescore/confidence-calibration-audit.json`
- `docs/evidence/proof-archives/smol-worldcup-round-004-dev-formal-rescore-20260520/proof-archive.json`
- `docs/evidence/proof-archives/smol-worldcup-round-004-canary-formal-rescore-20260520/proof-archive.json`
- `docs/hf-evaluation/smol-worldcup-submission-probe-20260520/smol-worldcup-submission-probe.json`

运行画像：

- dev 对照组：`wall_time_seconds=349.003523`，`throughput_items_per_second=0.286530`
- dev 新 profile：`wall_time_seconds=327.014309`，`throughput_items_per_second=0.305797`
- canary 新 profile：`wall_time_seconds=72.449254`，`throughput_items_per_second=0.345069`

## 下一步

1. 接入独立 judge，避免 candidate model 与 judge model 同源导致的 self-judge 风险。
2. 若要走真实 HF submission，选择 Space 支持的模型 ID 运行，或 fork/PR Space 增加本地模型/provider/submission 合同。
3. 提交前由人工确认 token、成本、规则和结果公开路径；提交后把 API 响应、截图、日志和 publication guard 纳入新的 proof archive。
