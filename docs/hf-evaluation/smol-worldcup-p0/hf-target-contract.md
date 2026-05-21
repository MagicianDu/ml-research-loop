# Smol AI WorldCup P0 Target Contract

schema_version: `2026-05-18.smol-worldcup-live-verification.v1`
official_scores_claimed: `false`
status: `verified_with_limitations`
ready_for_local_baseline: `true`
external_submission_status: `needs_operator_confirmation`

## 目标

- Dataset: `ginigen-ai/smol-worldcup`
- Space: `ginigen-ai/smol-worldcup`
- Runtime: `https://ginigen-ai-smol-worldcup.hf.space`
- Primary metric: `WCS`

## 数据合同

- row_count: `125`
- fields: `id, shift_axis, category, subcategory, difficulty, prompt, answer_key, explanation, grading_rule, auto_grade, max_score, anchor, season, version, language, language_name`
- missing_required_fields: `none`
- sample_id: `S1-H1-001`
- sample_auto_grade: `json_field_check`

## Space / Runtime 合同

- routes_detected: `/evaluate, /api/results`
- env_vars_detected: `HF_TOKEN, OPENAI_API_KEY, DARWIN_API`
- supported_model_count: `13`
- missing_runtime_files_in_repo_tree: `results.json, smol_worldcup_s1.json`
- runtime_results_count: `0`

## 限制

- llm_judge_requires_openai_key
- runtime_results_api_empty
- space_repo_missing_results.json
- space_repo_missing_smol_worldcup_s1.json

## 下一步

- 进入 P1：实现本地 125 题读取、评分和 baseline artifact。
- 人工确认 `/evaluate` 是否允许自定义模型或是否需要向 Space owner 发起 PR。
- 继续保持 `official_scores_claimed=false`，直到公开提交证据存在。

## 声明边界

P0 只证明公开数据、Space 代码和运行时入口当前可访问，并不证明已完成 Hugging Face 官方提交或取得 leaderboard 成绩。
