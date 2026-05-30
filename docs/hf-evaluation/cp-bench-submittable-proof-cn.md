# CP-Bench 可提交 Proof 说明

本文档记录 CP-Bench 作为 Hugging Face 可提交外部 proof 线的当前边界。

## 目标

用 CP-Bench 验证 ML Research Loop 的真实产品能力：

- Codex/Claude 生成受约束 proposal；
- MCP/CLI 生成和校验 `.jsonl` submission；
- 本地 evaluator 运行并写出可复核 artifact；
- 人工确认后再决定是否上传 Hugging Face；
- 公开 leaderboard 结果出现前不声明官方成绩。

## 当前状态

- P0：已完成 live verification，公开 dataset、leaderboard README、UI 和 `user_eval.py` 均可访问，见 `cp-bench-p0/`。
- P1：已完成 dry-run local baseline，证明 submission 格式、summary parser 和 artifact manifest 可写，见 `cp-bench-p1/`。
- P2：已接入真实 local evaluator dependency gate，见 `cp-bench-p2/`。本机当前缺少 `datasets`、`cpmpy`、`minizinc`、`ortools`，因此结果为 `blocked_missing_dependencies`。
- P3：已接入 proposal contract guard 和 rollback evidence，见 `cp-bench-p3-proposal-round/`。当前样例 proposal 因 P2 baseline 未跑出真实 local eval score，被正确阻塞为 `blocked_pending_local_eval`。
- P4：已生成 manual submission gate bundle，见 `cp-bench-p4-submission-gate/`。该 bundle 可人工复核，但仍是 `not_submitted`，不代表 Hugging Face 上传或官方成绩。
- P5：已安装可选 evaluator 依赖并跑通真实 local evaluator，见 `cp-bench-p5-real-local-eval/`。负控 baseline 使用真实 CP-Bench verified split 的 `csplib__csplib_001_car_sequencing`，`runtime_success=1/1`，`final_solution_accuracy_percent=0.0`。
- P6：基于 P5 真实 local baseline 重新运行 proposal guard，见 `cp-bench-p6-real-proposal-round/`。MiniZinc `framework_switch` proposal 已从 blocked 变为 `ready_for_guarded_execution`，但还未执行改动。
- P7：基于 P5 真实 local eval 重新生成 manual submission gate，见 `cp-bench-p7-real-submission-gate/`。仍为 `not_submitted`，不代表 Hugging Face 上传或官方成绩。
- P8：已新增 candidate round 闭环，见 `cp-bench-p8-candidate-round/`。该轮使用第一题 `csplib__csplib_001_car_sequencing` 的公开 description/input_data 手写 CPMpy 候选模型，在本地 `user_eval.py` 上将 `final_solution_accuracy_percent` 从 P5 负控 baseline 的 `0.0` 提升到 `1.59`，状态为 `improved`。这证明本地候选生成、执行、比较和回滚证据链可跑通，但仍不是 Hugging Face 官方提交或 leaderboard 成绩。
- P9：已新增多题 candidate round smoke，见 `cp-bench-p9-multi-candidate-round/`。该轮先跑 3 题负控 baseline，再提交 3 行候选：第一题为可行 CPMpy 模型，后两题保留负控以验证失败定位。结果为 `submitted_models=3`、`runtime_success=3/3`、`final_solution_accuracy_percent 0.0 -> 1.59`，并在 report 中写出逐题 `model_outcomes`。这证明多题本地 evaluator、逐题结果解析和失败定位可用，但还不是规模化自动解题能力。
- P10：已将 P9 两个负控行替换为真实候选，见 `cp-bench-p10-three-real-candidates/`。三题均可执行，其中 car sequencing 和 vessel loading 通过，autocorrelation 因数学目标最小化结果与公开 evaluator 的参考模型 self-consistency 口径不一致而失败；本地指标从 `0.0` 提升到 `3.17`。这是一条有价值的失败定位证据。
- P11：已基于 P10 失败原因做 evaluator-compatible repair，见 `cp-bench-p11-evaluator-compatible-repair/`。以 P10 candidate local eval 为 baseline，修复 autocorrelation 口径后，三题全部 `final_passed=true`，`final_solution_accuracy_percent 3.17 -> 4.76`。该结果证明失败分析、受控修复、逐题 outcome 和本地 proof 闭环可用，但仍不是官方 leaderboard 或规模化自动解题能力。
- P12：已扩展到 10 个 verified rows，见 `cp-bench-p12-ten-row-scale/`。本轮先基于 P10 失败 report 生成 proposal prompt context，再跑 10 题负控 baseline 和 10 题 reference replay candidate。结果为 `runtime_success=10/10`、`final_solution_accuracy_percent 0.0 -> 15.87`、10 个 `model_outcomes` 全部 `final_passed=true`，并写出 `failure_summary`、`rollback-evidence.json` 和 `manual-submission-decision.*`。P12 证明的是本地 evaluator/proof 管线扩容，不是 autonomous solving；因此人工 Hugging Face submission gate 决策为 `defer_external_submission`。
- P13：已新增非 reference replay 的 client candidate 生成入口，见 `cp-bench-p13-client-generated-candidate/`。`cp-bench-client-candidate` 只读取公开题目元信息，不读取公开 `model` 字段；本轮在 10 个 verified rows 上生成 3 个 hand-written client solver 和 7 个 negative-control fallback，source audit 记录 `reference_model_field_accessed=false`。本地 evaluator 结果为 `final_solution_accuracy_percent 0.0 -> 4.76`，3/10 通过，剩余 7 个失败样本已写入 proposal context。P13 证明非 reference replay 的 client-generated candidate path 可带来本地提升，但仍不是 leaderboard 竞争力证明。
- P14：已扩展非 reference client solver 覆盖，见 `cp-bench-p14-client-solver-expansion/`。同一 `handcrafted-small-cpmpy-v1` strategy 覆盖 9 个 verified rows，保留 crossfigures 作为唯一 fallback；source audit 记录 `reference_model_field_accessed=false`。本地 evaluator 结果为 `runtime_success=10/10`、`final_solution_accuracy_percent 0.0 -> 14.29`，9/10 通过，剩余 1 个失败样本已写入 proposal context。P14 是 P15 前的最强非 reference local proof，仍不是官方 leaderboard 成绩或外部提交。
- P15：已把同一非 reference client solver 路径扩到 21 个 verified rows，见 `cp-bench-p15-client-solver-expansion/`。候选包生成 20 个公开输入推导的 solver，继续保留 crossfigures 作为唯一 negative-control fallback；source audit 记录 `reference_model_field_accessed=false`、`generated_count=20`、`fallback_count=1`。本地 evaluator 结果为 `runtime_success=21/21`、`final_solution_accuracy_percent 0.0 -> 31.75`，20/21 通过，失败样本继续进入 proposal context。同步写入 `leaderboard-competitiveness-audit.json`：当前公开 verified storage 最低结果为 `46.03`，P15 若提交会排在公开结果之后，因此决策仍是 `defer_external_submission`。P15 是当前最强的 CP-Bench 非 reference local proof，但仍不是官方 leaderboard 成绩或外部提交。

## 可选依赖

P1 dry-run 不依赖 CP-Bench evaluator。P2 及之后需要：

```bash
pip install 'ml-research-loop[hf-cp-bench]'
```

MiniZinc 路径还可能需要单独安装 MiniZinc binary 和 solver；Python 包可 import 不等于 solver 可用。

## 运行方式

P0：

```bash
ml-loop hf-eval cp-bench-verify \
  --output-dir docs/hf-evaluation/cp-bench-p0 \
  --no-raw \
  --json
```

P1 dry-run：

```bash
ml-loop hf-eval cp-bench-baseline \
  --output-dir docs/hf-evaluation/cp-bench-p1 \
  --limit 1 \
  --framework CPMpy \
  --dry-run \
  --json
```

P2 local evaluator dependency gate：

```bash
ml-loop hf-eval cp-bench-baseline \
  --output-dir docs/hf-evaluation/cp-bench-p2 \
  --limit 1 \
  --framework CPMpy \
  --timeout-seconds 15 \
  --json
```

P3 proposal round：

```bash
ml-loop hf-eval cp-bench-proposal-round \
  --baseline-report docs/hf-evaluation/cp-bench-p2/cp-bench-local-eval-report.json \
  --proposal docs/hf-evaluation/cp-bench-p3-proposal-round/proposal.json \
  --output-dir docs/hf-evaluation/cp-bench-p3-proposal-round \
  --json
```

P4 submission gate：

```bash
ml-loop hf-eval cp-bench-submission-gate \
  --submission docs/hf-evaluation/cp-bench-p2/submission.jsonl \
  --source-report docs/hf-evaluation/cp-bench-p2/cp-bench-local-eval-report.json \
  --output-dir docs/hf-evaluation/cp-bench-p4-submission-gate \
  --json
```

P5 real local evaluator baseline：

```bash
ml-loop hf-eval cp-bench-baseline \
  --output-dir docs/hf-evaluation/cp-bench-p5-real-local-eval \
  --limit 1 \
  --framework CPMpy \
  --timeout-seconds 180 \
  --json
```

P6 proposal round against real local baseline：

```bash
ml-loop hf-eval cp-bench-proposal-round \
  --baseline-report docs/hf-evaluation/cp-bench-p5-real-local-eval/cp-bench-local-eval-report.json \
  --proposal docs/hf-evaluation/cp-bench-p3-proposal-round/proposal.json \
  --output-dir docs/hf-evaluation/cp-bench-p6-real-proposal-round \
  --json
```

P7 submission gate against real local baseline：

```bash
ml-loop hf-eval cp-bench-submission-gate \
  --submission docs/hf-evaluation/cp-bench-p5-real-local-eval/submission.jsonl \
  --source-report docs/hf-evaluation/cp-bench-p5-real-local-eval/cp-bench-local-eval-report.json \
  --output-dir docs/hf-evaluation/cp-bench-p7-real-submission-gate \
  --json
```

P8 candidate round against real local baseline：

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

P9 multi-candidate smoke：

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

P10 three-real-candidate smoke：

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

P11 evaluator-compatible repair：

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

P12 ten-row scale proof：

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

P13 non-reference client candidate proof：

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

P14 client solver expansion proof：

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

P15 client solver expansion proof：

```bash
ml-loop hf-eval cp-bench-client-candidate \
  --output-dir docs/hf-evaluation/cp-bench-p15-client-solver-expansion/client-candidate \
  --limit 21 \
  --strategy handcrafted-small-cpmpy-v1 \
  --dataset-version verified \
  --json

ml-loop hf-eval cp-bench-baseline \
  --output-dir docs/hf-evaluation/cp-bench-p15-client-solver-expansion/baseline-negative-control \
  --limit 21 \
  --framework CPMpy \
  --dataset-version verified \
  --timeout-seconds 900 \
  --json

ml-loop hf-eval cp-bench-candidate-round \
  --baseline-report docs/hf-evaluation/cp-bench-p15-client-solver-expansion/baseline-negative-control/cp-bench-local-eval-report.json \
  --submission docs/hf-evaluation/cp-bench-p15-client-solver-expansion/client-candidate/candidate-submission.jsonl \
  --proposal docs/hf-evaluation/cp-bench-p15-client-solver-expansion/proposal.json \
  --output-dir docs/hf-evaluation/cp-bench-p15-client-solver-expansion \
  --framework CPMpy \
  --dataset-version verified \
  --timeout-seconds 1200 \
  --json

ml-loop hf-eval cp-bench-proposal-context \
  --current-report docs/hf-evaluation/cp-bench-p15-client-solver-expansion/cp-bench-candidate-round-report.json \
  --output-dir docs/hf-evaluation/cp-bench-p15-client-solver-expansion/proposal-context \
  --max-proposals 3 \
  --json
```

MCP 客户端调用：

- `write_cp_bench_live_verification`
- `run_cp_bench_local_baseline`
- `run_cp_bench_proposal_round`
- `run_cp_bench_candidate_round`
- `build_cp_bench_proposal_context`
- `write_cp_bench_client_candidate_submission`
- `write_cp_bench_submission_gate`

其中 `run_cp_bench_local_baseline` 的 `dry_run=true` 是格式 proof；`dry_run=false` 进入真实 evaluator 依赖门和 runner。
`run_cp_bench_proposal_round` 只记录 proposal guard、before/after summary 边界和 rollback evidence，不自动执行外部上传。
`run_cp_bench_candidate_round` 运行客户端候选 submission 的本地 evaluator，对比 baseline 和 candidate summary，并写出 `candidate-local-eval/` proof；它不自动上传 Hugging Face。
`build_cp_bench_proposal_context` 从 candidate-round report 的失败分类生成 proposal prompt context，供 Codex/Claude 提出下一轮本地 candidate；它不执行 evaluator，也不上传 Hugging Face。
`write_cp_bench_client_candidate_submission` 生成非 reference replay 的本地 candidate submission，并写出 `source-audit.json`；它不读取公开 `model` 字段，不执行 evaluator，也不上传 Hugging Face。
`write_cp_bench_submission_gate` 只生成待人工确认的提交包和校验清单，不自动上传。

## 宣传边界

可以说：

- CP-Bench 已被选为第一条 Hugging Face 可提交 proof 线；
- P0-P15 artifact 已纳入证据链；
- 当前系统已经具备 submission 生成、格式校验、依赖探测、真实 local evaluator 运行、proposal 守卫、candidate round 指标对比、失败/回滚 artifact 和人工提交包写入能力；
- P8/P9 在真实 CP-Bench verified 问题上取得本地 evaluator 非零提升：`final_solution_accuracy_percent 0.0 -> 1.59`；
- P10/P11 已证明多题真实候选、失败定位和 evaluator-compatible 修复闭环：`0.0 -> 3.17 -> 4.76`；
- P12 已把本地 evaluator proof 扩到 10 个 verified rows，写出逐题 `model_outcomes`、`failure_summary`、`rollback-evidence.json` 和人工提交决策；
- P13 已证明非 reference replay 的 client-generated candidate path 可以在 10-row local proof 上产生本地提升：`0.0 -> 4.76`，3/10 通过；
- P14 已把非 reference client solver 覆盖扩到 9/10：`0.0 -> 14.29`，只剩 crossfigures fallback；
- P15 已把非 reference client solver 覆盖扩到 20/21：`0.0 -> 31.75`，仍只有 crossfigures fallback；
- P15 已完成公开 verified storage 竞争力审计：当前本地 `31.75` 低于公开最低 `46.03`，因此暂缓外部提交；
- P9-P15 已能在多题 summary 中解析逐题 `model_outcomes`，区分通过题、负控失败题和 evaluator 口径失败题。

不能说：

- 已提交 Hugging Face；
- 已取得 CP-Bench leaderboard score 或排名；
- P2 blocked artifact 是模型效果成绩；
- P3 blocked proposal 是效果提升结果；
- P4 submission gate 已经上传到 Hugging Face；
- P5 真实 local evaluator 结果是官方 leaderboard 成绩；
- P6 ready proposal 已经完成算法改动或效果提升；
- P7 submission gate 已经上传到 Hugging Face；
- P8 本地 candidate round 是官方 leaderboard 成绩、排名或规模化竞争力证明；
- P9 多题 smoke 是官方 leaderboard 成绩、排名或稳定规模化自动解题证明；
- P10/P11 三题本地结果是官方 leaderboard 成绩、排名或大规模自动解题证明；
- P11 autocorrelation repair 是数学目标更优算法证明；它只是公开 evaluator 口径兼容修复；
- P12 10 题 reference replay 是 autonomous solving 或 leaderboard 竞争力证明；
- P12 已经进入人工 Hugging Face submission gate；当前决策是 `defer_external_submission`；
- P13 的 3/10 非 reference candidate 结果已经足以提交 Hugging Face 或证明大规模 autonomous solving；
- P14 的 9/10 local evaluator 结果已经是官方 leaderboard score、排名或已提交 Hugging Face；
- P15 的 20/21 local evaluator 结果已经是官方 leaderboard score、排名或已提交 Hugging Face；
- 当前已经完成自动 proposal 到官方榜单提升闭环。

所有相关 artifact 在外部提交和公开结果完成前必须保持 `official_scores_claimed=false`。
