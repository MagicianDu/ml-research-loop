# Benchmark Proof Publication Guard

This bundle is not an official leaderboard score report unless score evidence is present in the artifact bundle.

- status: `publishable_with_limitations`
- benchmark_name: `smol_worldcup`
- run_mode: `local_formal_scorer_v2_rescore`
- official_scores_claimed: `false`
- score_claim_policy: `not_allowed`

## Allowed Public Claims

- debug proof-run artifacts are available
- commands, config, environment, logs, reports, and limitations are published

## Blocked Public Claims

- official leaderboard score
- deterministic local fixture score as official benchmark performance

## Missing Artifacts

- none

## Limitations

- formal scorer-v2 rescore 是已有 prediction.jsonl 的本地评分适配器审计。
- 该 proof archive 不包含 Hugging Face submission、leaderboard 成绩或 hidden-test 成绩。
- scorer-v2 口径修正不能宣传为新的模型输出或新的模型能力提升。
- llm_judge 行默认保留原 rubric judge 分数，仍存在 judge independence 风险。

This is not an official leaderboard score.
