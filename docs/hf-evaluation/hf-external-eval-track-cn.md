# Hugging Face 外部评测轨道

本文档把“参加 Hugging Face 上的公开比赛、leaderboard 或 evaluation”固化为产品验收路线。目标不是刷榜，而是用外部可复核目标证明 ML Research Loop 能完成：

- 研究目标选择；
- baseline 建立；
- Codex/Claude 生成 proposal；
- MCP 执行实验或评测；
- 指标对比、失败记录、回滚；
- proof archive 和公开声明边界。

## 当前结论

优先级已从 `smol-ai-worldcup-shift` 调整为 `cp-bench-constraint-modeling`。原因是 Smol AI WorldCup 当前更适合作为本地诊断和 proposal loop 训练场；公开 Space 对本地模型 prediction 的直接提交路径受限，不能很好证明市场竞争力。CP-Bench 则有明确的 `.jsonl` 提交、leaderboard、可本地运行的 evaluator 和可审计代码 artifact，更适合第一条真实 Hugging Face 可提交 proof 线。

CP-Bench 目标筛选见 [hf-submittable-targets-20260522-cn.md](hf-submittable-targets-20260522-cn.md)，研发计划见 [../superpowers/plans/2026-05-22-cp-bench-submittable-proof-track-cn.md](../superpowers/plans/2026-05-22-cp-bench-submittable-proof-track-cn.md)。

`smol-ai-worldcup-shift` 继续保留。它的价值是低成本本地诊断、provider 对比、dev/canary 纪律、scorer audit 和“5 轮以内发现稳定提升方向”的产品能力训练；但在没有外部可提交结果前，不再作为第一条竞争力宣传目标。

第二优先级候选是 `aitx-challenge-model-space` 和 `frugal-ai-challenge-text`。AI-Tx 有明确的 HF Space API 提交和 private test，但医学 QA 合规压力更高；Frugal AI 更贴近效率型 ML 产品叙事，但正式推进前需要重新 live verification 当前提交状态。

完整候选清单见 [target-shortlist.json](target-shortlist.json)。

## 分阶段目标

| 阶段 | 目标 | 验收 |
| --- | --- | --- |
| P0 | 目标清单和声明边界 | `ml-loop hf-eval shortlist --json` 能输出候选，且 `official_scores_claimed=false` |
| P1 | 选定第一个外部目标 | 生成 `hf-external-eval-plan.json/.md`，明确数据、metric、baseline、迭代和 proof 入口 |
| P2 | 本地 HF-compatible baseline | 读取公开数据或规则，跑出本地 baseline，生成 artifact manifest |
| P3 | 一轮自动迭代 | Codex/Claude 提出 proposal，MCP 执行，比较指标并记录失败/回滚 |
| P4 | 外部提交 dry-run 或人工提交 | 生成提交文件或 Space API，人工确认后才能上传 |
| P5 | 可宣传 proof | proof archive、public claims map、benchmark index 和 release evidence 一致 |

## 声明边界

在没有完成外部平台提交并可公开复核前，只允许宣传：

- “已接入 Hugging Face 外部评测候选目标”；
- “已生成 local HF-compatible proof plan”；
- “已完成本地 baseline / 迭代 proof archive”。

不能宣传：

- official leaderboard score；
- 第三方比赛成绩；
- 任意论文或任意模型都能自动提升；
- 没有 proof archive 的口头结果。

## 使用方式

查看候选目标：

```bash
ml-loop hf-eval shortlist --json
```

生成第一个目标的 proof plan：

```bash
ml-loop hf-eval plan \
  --target-id cp-bench-constraint-modeling \
  --output-dir .demo_runs/hf-eval/cp-bench-plan \
  --json
```

Smol AI WorldCup 本地诊断计划仍可生成：

```bash
ml-loop hf-eval plan \
  --target-id smol-ai-worldcup-shift \
  --output-dir .demo_runs/hf-eval/smol-ai-worldcup-plan \
  --json
```

执行 CP-Bench P0 live verification：

```bash
ml-loop hf-eval cp-bench-verify \
  --output-dir docs/hf-evaluation/cp-bench-p0 \
  --no-raw \
  --json
```

MCP 客户端可调用 `write_cp_bench_live_verification` 触发同一条 P0 路径。该工具只检查公开 URL 并写 artifact，不上传 submission，不声明 leaderboard score。

执行 CP-Bench P1 dry-run local baseline：

```bash
ml-loop hf-eval cp-bench-baseline \
  --output-dir docs/hf-evaluation/cp-bench-p1 \
  --limit 1 \
  --framework CPMpy \
  --dry-run \
  --json
```

P1 dry-run 只校验 `.jsonl` submission 格式、summary parser 和 artifact manifest，不调用 CP-Bench evaluator，不声明外部成绩。

MCP 客户端可调用 `run_cp_bench_local_baseline` 触发同一条 P1 dry-run 路径。

执行 CP-Bench P2 local evaluator dependency gate：

```bash
ml-loop hf-eval cp-bench-baseline \
  --output-dir docs/hf-evaluation/cp-bench-p2 \
  --limit 1 \
  --framework CPMpy \
  --timeout-seconds 15 \
  --json
```

P2 会进入真实 evaluator 路径：先生成 `.jsonl` submission，再探测本机 `datasets`、`click`、`cpmpy`、`minizinc`、`ortools` 依赖。若依赖不足，命令写出 `blocked_missing_dependencies` artifact，而不是崩溃或伪造成绩。2026-05-23 的本机验收结果为缺少 `datasets`、`cpmpy`、`minizinc`、`ortools`，见 [cp-bench-p2/README.md](cp-bench-p2/README.md)。

MCP 客户端仍调用 `run_cp_bench_local_baseline`；当 `dry_run=false` 时触发同一条 P2 路径。该工具不自动上传 Hugging Face，不声明 leaderboard score。

执行 CP-Bench P3 proposal round：

```bash
ml-loop hf-eval cp-bench-proposal-round \
  --baseline-report docs/hf-evaluation/cp-bench-p2/cp-bench-local-eval-report.json \
  --proposal docs/hf-evaluation/cp-bench-p3-proposal-round/proposal.json \
  --output-dir docs/hf-evaluation/cp-bench-p3-proposal-round \
  --json
```

P3 只执行 proposal contract guard 和 rollback evidence 写入，不绕过 P2 依赖门。2026-05-23 的样例 proposal 是 `framework_switch` 到 MiniZinc；由于 P2 baseline 仍是 `blocked_missing_dependencies`，P3 结果为 `blocked_pending_local_eval`，见 [cp-bench-p3-proposal-round/README.md](cp-bench-p3-proposal-round/README.md)。

MCP 客户端可调用 `run_cp_bench_proposal_round` 触发同一条 P3 路径。该工具只写 proposal round 和 rollback artifact，不上传 Hugging Face。

执行 CP-Bench P4 submission gate：

```bash
ml-loop hf-eval cp-bench-submission-gate \
  --submission docs/hf-evaluation/cp-bench-p2/submission.jsonl \
  --source-report docs/hf-evaluation/cp-bench-p2/cp-bench-local-eval-report.json \
  --output-dir docs/hf-evaluation/cp-bench-p4-submission-gate \
  --json
```

P4 生成可人工复核的 submission gate bundle，包括 `submission.jsonl`、`submission-report.md`、`manual-checklist.md`、`artifact-manifest.json` 和 `SHA256SUMS`。它仍是 `external_submission_status=not_submitted`，不会上传 Hugging Face，也不会声明官方成绩，见 [cp-bench-p4-submission-gate/README.md](cp-bench-p4-submission-gate/README.md)。

MCP 客户端可调用 `write_cp_bench_submission_gate` 触发同一条 P4 路径。

执行 CP-Bench P5 real local evaluator baseline：

```bash
ml-loop hf-eval cp-bench-baseline \
  --output-dir docs/hf-evaluation/cp-bench-p5-real-local-eval \
  --limit 1 \
  --framework CPMpy \
  --timeout-seconds 180 \
  --json
```

P5 已安装 `ml-research-loop[hf-cp-bench]` 可选依赖，并跑通公开 `user_eval.py` 的本地 evaluator。当前负控 baseline 使用真实 verified split 的 `csplib__csplib_001_car_sequencing`，结果为 `runtime_success=1/1`、`coverage_percent=1.59`、`final_solution_accuracy_percent=0.0`。这是真实 local evaluator proof，但不是 Hugging Face 官方提交或 leaderboard 成绩，见 [cp-bench-p5-real-local-eval/README.md](cp-bench-p5-real-local-eval/README.md)。

执行 CP-Bench P6 proposal guard against real baseline：

```bash
ml-loop hf-eval cp-bench-proposal-round \
  --baseline-report docs/hf-evaluation/cp-bench-p5-real-local-eval/cp-bench-local-eval-report.json \
  --proposal docs/hf-evaluation/cp-bench-p3-proposal-round/proposal.json \
  --output-dir docs/hf-evaluation/cp-bench-p6-real-proposal-round \
  --json
```

P6 证明 proposal guard 能基于真实 local baseline 工作：MiniZinc `framework_switch` proposal 现在是 `ready_for_guarded_execution`，但还没有执行改动，也没有产生效果提升结论。

执行 CP-Bench P7 submission gate against real baseline：

```bash
ml-loop hf-eval cp-bench-submission-gate \
  --submission docs/hf-evaluation/cp-bench-p5-real-local-eval/submission.jsonl \
  --source-report docs/hf-evaluation/cp-bench-p5-real-local-eval/cp-bench-local-eval-report.json \
  --output-dir docs/hf-evaluation/cp-bench-p7-real-submission-gate \
  --json
```

P7 是基于真实 local evaluator report 的人工提交包，仍是 `not_submitted`。

执行 CP-Bench P8 candidate round against real baseline：

```bash
ml-loop hf-eval cp-bench-candidate-round \
  --baseline-report docs/hf-evaluation/cp-bench-p5-real-local-eval/cp-bench-local-eval-report.json \
  --submission docs/hf-evaluation/cp-bench-p8-candidate-round/candidate-submission.jsonl \
  --proposal docs/hf-evaluation/cp-bench-p8-candidate-round/proposal.json \
  --output-dir docs/hf-evaluation/cp-bench-p8-candidate-round \
  --framework CPMpy \
  --dataset-version verified \
  --timeout-seconds 180 \
  --json
```

P8 证明 MCP/CLI 可以执行真实候选 submission 的本地 evaluator，并和 P5 baseline 做指标对比：`final_solution_accuracy_percent` 从 `0.0` 提升到 `1.59`，`decision=candidate_improved`。该结果只覆盖 verified split 的第一个问题，是 local evaluator proof，不是 Hugging Face 官方提交、leaderboard score 或排名。

MCP 客户端可调用 `run_cp_bench_candidate_round` 触发同一条 P8 路径。该工具只运行本地 evaluator 和 proof bundle 写入，不上传 Hugging Face。

执行 CP-Bench P9 multi-candidate smoke：

```bash
ml-loop hf-eval cp-bench-baseline \
  --output-dir docs/hf-evaluation/cp-bench-p9-multi-candidate-round/baseline-negative-control \
  --limit 3 \
  --framework CPMpy \
  --dataset-version verified \
  --timeout-seconds 180 \
  --json

ml-loop hf-eval cp-bench-candidate-round \
  --baseline-report docs/hf-evaluation/cp-bench-p9-multi-candidate-round/baseline-negative-control/cp-bench-local-eval-report.json \
  --submission docs/hf-evaluation/cp-bench-p9-multi-candidate-round/candidate-submission.jsonl \
  --proposal docs/hf-evaluation/cp-bench-p9-multi-candidate-round/proposal.json \
  --output-dir docs/hf-evaluation/cp-bench-p9-multi-candidate-round \
  --framework CPMpy \
  --dataset-version verified \
  --timeout-seconds 180 \
  --json
```

P9 把 P8 扩展为 3 题本地 smoke。3 题负控 baseline 为 `final_solution_accuracy_percent=0.0`；candidate round 中第一题通过，后两题保留负控失败，最终 `final_solution_accuracy_percent=1.59`，`model_outcomes` 能逐题标出 `final_passed=true/false`。这证明多题 evaluator、逐题诊断和失败定位可用，但不证明已经具备大规模自动解题竞争力。

执行 CP-Bench P10 three-real-candidate smoke：

```bash
ml-loop hf-eval cp-bench-baseline \
  --output-dir docs/hf-evaluation/cp-bench-p10-three-real-candidates/baseline-negative-control \
  --limit 3 \
  --framework CPMpy \
  --dataset-version verified \
  --timeout-seconds 180 \
  --json

ml-loop hf-eval cp-bench-candidate-round \
  --baseline-report docs/hf-evaluation/cp-bench-p10-three-real-candidates/baseline-negative-control/cp-bench-local-eval-report.json \
  --submission docs/hf-evaluation/cp-bench-p10-three-real-candidates/candidate-submission.jsonl \
  --proposal docs/hf-evaluation/cp-bench-p10-three-real-candidates/proposal.json \
  --output-dir docs/hf-evaluation/cp-bench-p10-three-real-candidates \
  --framework CPMpy \
  --dataset-version verified \
  --timeout-seconds 180 \
  --json
```

P10 把 P9 的两个负控行替换成真实候选。结果为 `runtime_success=3/3`、`final_solution_accuracy_percent=3.17`，逐题 outcome 显示 car sequencing 和 vessel loading 通过，autocorrelation 失败。失败原因不是运行错误，而是候选按数学目标最小化得到 `E=36`，但公开 evaluator 的参考模型 self-consistency 口径返回 `E=900`，因此被判为 objective/consistency 不一致。P10 是失败定位 proof，不是官方成绩。

执行 CP-Bench P11 evaluator-compatible repair：

```bash
ml-loop hf-eval cp-bench-candidate-round \
  --baseline-report docs/hf-evaluation/cp-bench-p10-three-real-candidates/candidate-local-eval/cp-bench-local-eval-report.json \
  --submission docs/hf-evaluation/cp-bench-p11-evaluator-compatible-repair/candidate-submission.jsonl \
  --proposal docs/hf-evaluation/cp-bench-p11-evaluator-compatible-repair/proposal.json \
  --output-dir docs/hf-evaluation/cp-bench-p11-evaluator-compatible-repair \
  --framework CPMpy \
  --dataset-version verified \
  --timeout-seconds 180 \
  --json
```

P11 基于 P10 的失败原因做 evaluator-compatible repair。以 P10 candidate local eval 为 baseline，`final_solution_accuracy_percent` 从 `3.17` 提升到 `4.76`，三题 `model_outcomes` 均为 `final_passed=true`。该轮证明本地 proof loop 能发现口径问题、记录失败、执行受控修复并复核结果；不能宣传为 Hugging Face 官方 leaderboard、排名或大规模自动解题竞争力。

执行 CP-Bench P12 ten-row scale proof：

```bash
ml-loop hf-eval cp-bench-proposal-context \
  --current-report docs/hf-evaluation/cp-bench-p10-three-real-candidates/cp-bench-candidate-round-report.json \
  --output-dir docs/hf-evaluation/cp-bench-p12-ten-row-scale/proposal-context-from-p10 \
  --max-proposals 3 \
  --json

ml-loop hf-eval cp-bench-baseline \
  --output-dir docs/hf-evaluation/cp-bench-p12-ten-row-scale/baseline-negative-control \
  --limit 10 \
  --framework CPMpy \
  --dataset-version verified \
  --timeout-seconds 600 \
  --json

ml-loop hf-eval cp-bench-candidate-round \
  --baseline-report docs/hf-evaluation/cp-bench-p12-ten-row-scale/baseline-negative-control/cp-bench-local-eval-report.json \
  --submission docs/hf-evaluation/cp-bench-p12-ten-row-scale/candidate-submission.jsonl \
  --proposal docs/hf-evaluation/cp-bench-p12-ten-row-scale/proposal.json \
  --output-dir docs/hf-evaluation/cp-bench-p12-ten-row-scale \
  --framework CPMpy \
  --dataset-version verified \
  --timeout-seconds 600 \
  --json
```

P12 扩到 10 个 verified rows。负控 baseline 为 `final_solution_accuracy_percent=0.0`；reference replay candidate 为 `runtime_success=10/10`、`final_solution_accuracy_percent=15.87`，10 个 `model_outcomes` 全部通过。P12 同时写出 proposal context、failure summary、rollback evidence 和 manual submission decision。由于 candidate 使用公开 `model` 字段做 reference replay，人工提交决策为 `defer_external_submission`；该轮只证明本地 proof 管线扩容，不证明 autonomous solving 或官方榜单竞争力。

执行 CP-Bench P13 non-reference client candidate proof：

```bash
ml-loop hf-eval cp-bench-client-candidate \
  --output-dir docs/hf-evaluation/cp-bench-p13-client-generated-candidate/client-candidate \
  --limit 10 \
  --strategy handcrafted-small-cpmpy-v1 \
  --dataset-version verified \
  --json

ml-loop hf-eval cp-bench-candidate-round \
  --baseline-report docs/hf-evaluation/cp-bench-p12-ten-row-scale/baseline-negative-control/cp-bench-local-eval-report.json \
  --submission docs/hf-evaluation/cp-bench-p13-client-generated-candidate/client-candidate/candidate-submission.jsonl \
  --proposal docs/hf-evaluation/cp-bench-p13-client-generated-candidate/proposal.json \
  --output-dir docs/hf-evaluation/cp-bench-p13-client-generated-candidate \
  --framework CPMpy \
  --dataset-version verified \
  --timeout-seconds 600 \
  --json

ml-loop hf-eval cp-bench-proposal-context \
  --current-report docs/hf-evaluation/cp-bench-p13-client-generated-candidate/cp-bench-candidate-round-report.json \
  --output-dir docs/hf-evaluation/cp-bench-p13-client-generated-candidate/proposal-context \
  --max-proposals 3 \
  --json
```

P13 不读取公开 `model` 字段，不做 reference replay。`source-audit.json` 记录 `reference_model_field_accessed=false`、`generated_count=3`、`fallback_count=7`。本地 evaluator 结果为 `runtime_success=10/10`、`final_solution_accuracy_percent=4.76`，3 个 hand-written client solver 通过，7 个 fallback 失败并进入 proposal context。该轮证明非 reference replay 的 client-generated candidate path 可以产生本地提升；仍不证明官方榜单竞争力或大规模 autonomous solving。

执行 CP-Bench P14 client solver expansion proof：

```bash
ml-loop hf-eval cp-bench-client-candidate \
  --output-dir docs/hf-evaluation/cp-bench-p14-client-solver-expansion/client-candidate \
  --limit 10 \
  --strategy handcrafted-small-cpmpy-v1 \
  --dataset-version verified \
  --json

ml-loop hf-eval cp-bench-candidate-round \
  --baseline-report docs/hf-evaluation/cp-bench-p12-ten-row-scale/baseline-negative-control/cp-bench-local-eval-report.json \
  --submission docs/hf-evaluation/cp-bench-p14-client-solver-expansion/client-candidate/candidate-submission.jsonl \
  --proposal docs/hf-evaluation/cp-bench-p14-client-solver-expansion/proposal.json \
  --output-dir docs/hf-evaluation/cp-bench-p14-client-solver-expansion \
  --framework CPMpy \
  --dataset-version verified \
  --timeout-seconds 600 \
  --json

ml-loop hf-eval cp-bench-proposal-context \
  --current-report docs/hf-evaluation/cp-bench-p14-client-solver-expansion/cp-bench-candidate-round-report.json \
  --output-dir docs/hf-evaluation/cp-bench-p14-client-solver-expansion/proposal-context \
  --max-proposals 3 \
  --json
```

P14 继续保持 non-reference replay 边界：`source-audit.json` 记录 `reference_model_field_accessed=false`、`generated_count=9`、`fallback_count=1`。本地 evaluator 结果为 `runtime_success=10/10`、`final_solution_accuracy_percent=14.29`，9 个 client solver 通过，只剩 crossfigures fallback 失败并进入 proposal context。该轮是当前最强的 CP-Bench 非 reference local proof；仍不声明官方 leaderboard、外部提交或排名。

执行 Smol AI WorldCup P0 live verification：

```bash
ml-loop hf-eval smol-worldcup-verify \
  --output-dir .demo_runs/hf-eval/smol-worldcup-p0 \
  --json
```

MCP 客户端可调用同名能力：

- `write_smol_worldcup_live_verification`
- `write_smol_worldcup_prompt_leakage_audit`
- `run_smol_worldcup_local_baseline`
- `run_smol_worldcup_model_eval`
- `run_smol_worldcup_rescore`
- `write_smol_worldcup_rescore_proof_archive`
- `write_smol_worldcup_submission_probe`

执行 Smol AI WorldCup P1 local baseline：

```bash
ml-loop hf-eval smol-worldcup-baseline \
  --output-dir .demo_runs/hf-eval/smol-worldcup-p1 \
  --json
```

执行 prompt leakage audit：

```bash
ml-loop hf-eval smol-worldcup-leakage-audit \
  --output-dir .demo_runs/hf-eval/smol-worldcup-p3-leakage-audit \
  --prompt-profile p3-routing-v1 \
  --json
```

执行 Smol AI WorldCup P2 LM Studio 本地模型评测：

```bash
ml-loop hf-eval smol-worldcup-model-eval \
  --output-dir .demo_runs/hf-eval/smol-worldcup-p2 \
  --base-url http://127.0.0.1:1234/v1 \
  --model openai/gpt-oss-20b \
  --limit 5 \
  --json
```

Codex/Claude 通过 MCP 时调用 `run_smol_worldcup_model_eval`，传入
`output_dir`、`base_url`、`model`、`limit`、`temperature` 和 `max_tokens`
即可触发同一条本地评测路径。

如需启用本地 rubric judge 诊断，可额外传入：

- `prompt_profile=p3-routing-v1`
- `prompt_profile=p3-dev-v2`：仅用于 dev split 的受控后续迭代，不能在看过 canary 后继续调参。
- `judge_mode=openai-compatible`
- `judge_model=openai/gpt-oss-20b`
- `judge_base_url=http://127.0.0.1:1234/v1`

如需避免继续在同一批公开题上调参，可传入：

- `evaluation_split=dev`：用于未来调参和 proposal loop。
- `evaluation_split=canary`：用于未来最终检查。

历史 round-001/002/003 已经使用全部公开 125 题，因此新增 canary split 不能回溯证明历史结果是 untouched holdout。

这些命令和 MCP 工具只做规划、公开入口核对、本地评分和本地文件输出，不会提交 Hugging Face，不会上传模型或结果，也不会声明官方成绩。

当前 P0 状态：

- 数据集和 Space 入口可访问，可进入本地 baseline。
- `/api/results` 当前为空，外部榜单结果仍需后续提交或人工确认。
- 当前只允许声明 `verified_with_limitations`，不能声明 official leaderboard score。

当前 P1 状态：

- `local-abstain-baseline` 已跑完 125 题，输出 baseline report、prediction、score breakdown、failure cases 和 runtime profile。
- 当前本地诊断指标为 `H=62.5`、`I=0.073529`、`SHIFT=25.044117`。
- 因为这不是实际模型推理，`PIR`、`WCS_local_diagnostic` 和 `official_wcs` 都保持 `null`。
- 下一步应接入真实小模型输出或 proposal loop，而不是把 abstain baseline 当成打榜成绩。

当前 P2 接入状态：

- CLI 子命令 `smol-worldcup-model-eval` 已接入 OpenAI-compatible endpoint，默认指向 LM Studio `http://127.0.0.1:1234/v1`。
- MCP 工具 `run_smol_worldcup_model_eval` 已纳入 manifest、required tools、workflow 和 skills。
- 输出 artifact 包括 `smol-worldcup-model-eval-report.json`、`prediction.jsonl`、`score-breakdown.json`、`failure-cases.json`、`runtime-profile.json`、`proposal-rounds/` 和 `multi-round-report.json`。
- 2026-05-18 已完成 LM Studio `openai/gpt-oss-20b` 小样本 smoke：CLI 3 题 `H=66.666667`、`I=0.0`、`SHIFT=26.666667`；MCP 1 题也能写出完整 artifact。摘要见 [smol-worldcup-p2-smoke/README.md](smol-worldcup-p2-smoke/README.md)。
- 这一步仍是本地模型评测，不上传 Hugging Face，也不声明官方 leaderboard score。

当前 P3 迭代状态：

- 2026-05-18 已完成 `openai/gpt-oss-20b` 完整 125 题 round-001 本地评测：`H=65.75`、`I=34.080086`、`SHIFT=46.748052`、`WCS_local_diagnostic=68.372547`。
- 基于 failure proposal 增加 `prompt_profile=p3-routing-v1`，并修复本地 code scorer 对 JSON `code` 字段的解析。
- 完整 125 题 round-002 结果：`H=80.25`、`I=43.037029`、`SHIFT=57.922217`、`WCS_local_diagnostic=76.106647`。
- 对比原始 round-001 artifact，`SHIFT +11.174165`；对比修复 scorer 后的 round-001 rescored，`SHIFT +8.350636`。
- 摘要见 [smol-worldcup-p3-round-002/README.md](smol-worldcup-p3-round-002/README.md)。
- 2026-05-19 已完成 round-003：在 `prompt_profile=p3-routing-v1` 上启用 `judge_mode=openai-compatible`，用本地 `openai/gpt-oss-20b` 作为 rubric judge 评估 `llm_judge` 类题目。完整 125 题结果为 `H=79.075`、`I=77.647059`、`SHIFT=78.218235`、`WCS_local_diagnostic=88.441074`、failure count `47`。
- Round-003 摘要见 [smol-worldcup-p3-round-003-judge/README.md](smol-worldcup-p3-round-003-judge/README.md)。它证明本地评测 adapter 已支持更真实的 rubric judge 路径，但由于 judge 口径改变，不能把 round-003 与 round-002 的差值直接宣传成纯模型能力提升。
- 2026-05-19 已补充 prompt leakage audit：`p3-routing-v1` 全 125 题 `leak_count=0`，artifact 位于 `.demo_runs/hf-eval/smol-worldcup-p3-leakage-audit-20260519/prompt-leakage-audit.json`。
- 已新增 deterministic `dev` / `canary` split。`canary` 当前为 25 题；它只能用于后续 untouched holdout 纪律，不能回溯改变历史 round-001/002/003 的证据等级。
- 2026-05-19 已新增 `prompt_profile=p3-dev-v2`，针对 dev split 的 `reasoning`、`confidence_calibration` 和 `self_correction` 失败模式做受控 prompt/routing 迭代，并通过 prompt leakage audit：全 125 题 `leak_count=0`。
- Dev split 对比：`p3-routing-v1` 为 `SHIFT=77.108639`、`WCS_local_diagnostic=87.811525`，`p3-dev-v2` 为 `SHIFT=78.464044`、`WCS_local_diagnostic=88.579932`；failure count 均为 `38`。提升主要来自 `reasoning` 类别，`confidence_calibration` 和 `self_correction` 仍需 scorer/normalization 审计。
- `p3-dev-v2` 只做了一次 canary 检查：25 题 `SHIFT=79.333334`、`WCS_local_diagnostic=89.069262`、failure count `10`。不能根据 canary 继续反向调 prompt。
- 2026-05-19 已完成 scorer-v2 审计：`answer_match` / `numeric_match` 增加 response normalizer，`confidence_calibration` 对齐 expected confidence band，`self_correction` 对齐 `final_answer` 口径。对已有 predictions 的离线 rescore 保留原 `llm_judge` rubric 分数；round-004 dev scorer-v2 后为 `SHIFT=86.712799`、`WCS_local_diagnostic=93.119708`、failure count `30`。2026-05-20 已固化正式 CLI/MCP：`ml-loop hf-eval smol-worldcup-rescore` / `run_smol_worldcup_rescore`，并新增 `confidence-calibration-audit.json` 双轨报告；round-004 dev 的 confidence band 为 `75.555556`，answer correctness 为 `44.444444`。这是评分口径修正，不是新模型跑分或官方成绩。
- 2026-05-20 已把 formal rescore 纳入 proof archive：dev archive 为 [smol-worldcup-round-004-dev-formal-rescore-20260520](../evidence/proof-archives/smol-worldcup-round-004-dev-formal-rescore-20260520/proof-archive.json)，canary archive 为 [smol-worldcup-round-004-canary-formal-rescore-20260520](../evidence/proof-archives/smol-worldcup-round-004-canary-formal-rescore-20260520/proof-archive.json)。两者均为 `archivable`，各包含 12 个 hash-indexed artifact，`official_scores_claimed=false`。
- 2026-05-20 已新增真实 HF submission path probe：[smol-worldcup-submission-probe-20260520](smol-worldcup-submission-probe-20260520/hf-submission-path.md)。结论是 `/evaluate/gradio_api/openapi.json` 暴露 `start_eval`，但公开 Space source 对 `model_id not in SUPPORTED_MODELS` 做限制；虽然 Gradio config 的 dropdown 标记 `allow_custom_value=true`，源码校验会覆盖该 UI 选项。本地 `openai/gpt-oss-20b` / LM Studio predictions 当前不能直接作为该 Space 的官方提交结果。
- Round-004 摘要见 [smol-worldcup-p3-round-004-dev-v2/README.md](smol-worldcup-p3-round-004-dev-v2/README.md)。
- 这仍是本地诊断评测，不是 Hugging Face 官方提交或 leaderboard 成绩。

当前 P4/P5 submission 状态：

- `submission_path_status=blocked_for_local_predictions`。
- Space 当前接受 13 个固定模型 ID；若要走真实 HF submission，需要选择受支持的 HF model ID 触发 Space eval，或 fork/PR Space 增加我们的模型/provider/submission 合同。
- 任何真实提交前都必须由人工确认 token、成本、外部规则、日志留存和结果公开路径；提交后需要把 openapi/config、命令、日志、结果页/API 响应和 publication guard 纳入 proof archive。

## 与现有架构的关系

这条轨道复用现有分层：

- Codex/Claude：选择目标、读数据、分析失败样例、提出 proposal；
- Skills：约束 workflow、声明边界、人工确认点；
- MCP/CLI：执行候选清单读取、baseline、patch/eval 和 artifact 写入；
- proof archive：保存可复核证据；
- public claims map：控制可宣传内容。

## 信息来源

- Hugging Face Competition Space 文档：https://huggingface.co/docs/competitions/main/competition_space
- Hugging Face Leaderboards and Evaluations 文档：https://huggingface.co/docs/leaderboards/en/index
- Hugging Face Space API endpoint 文档：https://huggingface.co/docs/hub/en/spaces-api-endpoints
- Smol AI WorldCup 数据集：https://huggingface.co/datasets/ginigen-ai/smol-worldcup
- Smol AI WorldCup Space source：https://huggingface.co/spaces/ginigen-ai/smol-worldcup/raw/main/app.py
- TuringBench-2 Questions 数据集：https://huggingface.co/datasets/roc-hci/TuringBench-2-Questions
- Frugal AI Challenge submission portal：https://huggingface.co/spaces/frugal-ai-challenge/submission-portal
