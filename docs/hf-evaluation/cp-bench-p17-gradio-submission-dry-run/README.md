# CP-Bench P17 Gradio Submission Dry Run

本目录记录一次 CP-Bench Space Gradio 表单提交计划。
默认状态不会上传；只有显式确认公开上传并记录人工批准说明时，脚本才会调用 Gradio 客户端。

## 当前状态

- status: `dry_run_ready_for_human_approved_space_upload`
- Space: `https://huggingface.co/spaces/kostis-init/CP-Bench-Leaderboard`
- API: `/handle_upload`
- submission name: `ml_research_loop_p17`
- target result: `results/v1_verified/ml_research_loop_p17/summary.txt`
- `external_upload_performed_by_script=false`
- `official_scores_claimed=false`；公开结果文件出现前不得宣传榜单成绩或排名。

## 文件

- `gradio-submission-plan.json`: gate、Space API 合约、表单参数和声明边界。
- `artifact-manifest.json` / `SHA256SUMS`: 完整性记录。
