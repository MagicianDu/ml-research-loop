# Smol AI WorldCup HF Submission Path Probe

本文件只记录公开 HF Space 提交通路探测结果，不触发评测、不上传预测、不声明官方成绩。

- status: `completed_with_limitations`
- submission_path_status: `blocked_for_local_predictions`
- submission_action: `not_launched`
- official_scores_claimed: `false`
- requested_model: `openai/gpt-oss-20b`
- requested_model_supported_by_space: `false`

## Accepted Model IDs

- `FINAL-Bench/Darwin-35B-A3B-Opus`
- `HuggingFaceTB/SmolLM2-1.7B-Instruct`
- `Qwen/Qwen3-0.6B`
- `Qwen/Qwen3-4B`
- `Qwen/Qwen3-8B`
- `Qwen/Qwen3.5-35B-A3B`
- `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B`
- `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B`
- `google/gemma-3-1b-it`
- `meta-llama/Llama-3.2-3B-Instruct`
- `microsoft/phi-4`
- `microsoft/phi-4-mini-instruct`
- `mistralai/Mistral-7B-Instruct-v0.3`

## Checks

- accepted_model_count: `13`
- gradio_config_allow_custom_value: `True`
- requested_model_supported_by_space: `False`
- runtime_results_empty: `True`
- source_validation_overrides_custom_dropdown: `True`
- space_source_restricts_supported_models: `True`
- start_eval_path_detected: `True`

## Limitations

- gradio_dropdown_allows_custom_value_but_source_restricts_models
- hf_submission_not_ready
- requested_model_not_supported_by_space:openai/gpt-oss-20b
- runtime_results_api_empty

## Next Actions

- 本地 LM Studio 预测不能直接作为该 Space 的官方提交结果。
- 选择 Space 支持的模型 ID 运行，或 fork/PR Space 增加目标模型和提交合同。
- 继续保持 official_scores_claimed=false，直到外部提交证据存在。

This probe only inspects the public HF Space API and source code. It does not launch evaluation, upload predictions, or claim official leaderboard scores.
