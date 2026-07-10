# Hugging Face External Evaluation Proof Plan

schema_version: `2026-05-18.hf-external-eval-plan.v1`
official_scores_claimed: `false`
target_id: `arguard-b1-binary-classification`
name: ArGuard Subtask B1 Binary Classification
hf_kind: `codabench_competition`
task_family: `arabic_prompt_safety_classification`
primary_metric: `macro-F1`

## Claim Boundary

Current first pilot external leaderboard target. Until Codabench submission and public result verification both complete, only local B1 readiness and submission-compatible proof may be claimed; official_scores_claimed=false.

## URLs

- competition: https://www.codabench.org/competitions/16652/
- task_website: https://araieval.github.io/ArGuard2026/taskB/
- repository: https://github.com/araieval/ArGuard-2026-tasks
- task_readme: https://github.com/araieval/ArGuard-2026-tasks/blob/main/taskB/README.md

## Why This Target

- It is a real external leaderboard target with a live Codabench competition page and public task repository.
- The binary classification surface is small enough for 3-5 optimizer/gate rounds while still testing real method search, validation discipline and submission packaging.
- The task is close to LLM safety and harmful prompt detection, so LLM-generated proposal traces and failure analysis are product-relevant rather than generic tabular tuning.

## Risks

- The task repository currently describes some released assets as planned or TBD, so P0 must verify which train/dev/scorer files are actually available before claiming readiness.
- Arabic prompt safety may need language-specific preprocessing and review to avoid brittle translation-only baselines.
- Codabench submission requires account/auth and must remain manual-gated until a submission adapter and public result verifier are in place.

## Acceptance

- P0 records live Codabench, task website, repository, data, scorer, format checker and submission status without submitting.
- P1 builds a local baseline and dev gate from released train/dev data, with macro-F1 and confusion/failure slices.
- P2 runs 3-5 optimizer/gate rounds that generate candidate methods, evaluate locally and update GateFeedbackMemory.
- P3 writes a Codabench submission gate bundle and blocks upload until explicit human approval.
- P4 fetches and verifies public Codabench result before any official or public score claim.

## Phases


### P0: live verification

- 确认公开 URL、leaderboard 或 submission portal 当前可访问。
- 记录是否需要 HF_TOKEN、Space、模型仓库或人工审核。
- 不上传、不提交、不声明官方成绩。

### P1: local baseline

- 读取公开数据或样例规则。
- 生成 baseline manifest、原始输出和 metric parser。
- 保存 artifact hashes 和限制说明。

### P2: client-guided iteration

- Codex/Claude 基于失败样例提出一轮 proposal。
- MCP/CLI 执行受控改动并比较指标。
- 失败 proposal 和 rollback 也进入 artifact。

### P3: external submission gate

- 生成提交文件、Space API 或 model-card eval result dry-run。
- 人工确认后才允许外部上传。
- 提交成功后把公开 URL、时间、hash 和截图/响应纳入 proof archive。

## Blocked Public Claims

- official HF leaderboard score before public submission evidence exists
- arbitrary model improvement from a single local run
- competition result without reproducible proof archive
