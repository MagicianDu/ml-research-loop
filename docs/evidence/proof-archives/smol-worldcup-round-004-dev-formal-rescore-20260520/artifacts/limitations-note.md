# Limitations

- formal scorer-v2 rescore 是已有 prediction.jsonl 的本地评分适配器审计。
- 该 proof archive 不包含 Hugging Face submission、leaderboard 成绩或 hidden-test 成绩。
- scorer-v2 口径修正不能宣传为新的模型输出或新的模型能力提升。
- llm_judge 行默认保留原 rubric judge 分数，仍存在 judge independence 风险。
