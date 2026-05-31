# Benchmark Evidence Index

本文索引当前项目中已经完成的可复核 benchmark evidence。所有结果都按证据强度和声明边界区分，避免把本地 debug 或 dummy 结果包装成 leaderboard 成绩。

全局声明边界：本索引只发布 benchmark proof evidence 文档和限制说明，`official_scores_claimed=false`。当前没有声明 official leaderboard、official PaperBench score 或完整官方 run-group 成绩。当前 checkout 已新增真实论文 bounded pilot 和 fastText/AG News 完整核心实验轨道的 committed proof archives（见 `docs/evidence/proof-archives/`）以及 release artifact hash（见 `dist/SHA256SUMS`），但本 benchmark index 中的 MLE-bench/PaperBench 历史 `.demo_runs` 原始 artifact 仍未作为 official benchmark release bundle 提交，不能把这些 benchmark 文档宣传为官方成绩。

P17 文档级证据索引已经分成三类，不得混写：

- official-debug hard result：MLE-bench `spooky-author-identification` 使用官方 prepared data 和 `mlebench grade-sample` 本地 scorer feedback，证明 patch/grade/proof archive 闭环；不能宣传 leaderboard。
- debug dummy harness：PaperBench debug split `rice` 使用 dummy solver + dummy judge 跑通官方 rollout/reproduction/grading path，`score=1.0` 只说明 harness 连通；不是官方 PaperBench score。
- Codex-assisted review：对同一 `rice` dummy run 做非官方 rubric 审查，`codex_review_score=0.0`、`PaperBench official score=null`；不是官方 PaperBench score。

## 已完成

| Benchmark | Evidence | 结果 | 可宣传边界 |
| --- | --- | --- | --- |
| MLE-bench | `docs/evidence/mle-bench-spooky-20260507-cn.md` | official-debug hard result：`spooky-author-identification` 从 baseline log loss `1.08468` 改善到 `0.37038`，超过 median threshold `0.418785` | 可以宣传本地 official scorer proof run 超过 median；不能宣传 leaderboard；`official_scores_claimed=false` |
| PaperBench | `docs/evidence/paperbench-debug-dummy-20260507-cn.md` | debug dummy harness：official debug split `rice` dummy solver + dummy judge 跑通，mean score `1.0`，三类 failure 均为 `0` | 可以宣传 official debug harness 全链路跑通；不能宣传真实论文复现质量；不是官方 PaperBench score；`official_scores_claimed=false` |
| PaperBench | `docs/evidence/paperbench-codex-review-rice-20260507-cn.md` | Codex-assisted review：对同一 `rice` debug dummy run 产出非官方 rubric review，审查分 `0.0`，proof archive `archivable` 且包含 `14` 个 artifact | 可以宣传 keyless Codex-assisted review 和诚实证据边界；不是官方 PaperBench score；`official_scores_claimed=false` |
| fastText AG News | `docs/evidence/fasttext-ag-news-real-baseline-20260513-cn.md` | 完整 AG News CSV + 本机官方 fastText binary 跑出 `P@1=0.914`，落入当前 `0.924±0.02` target tolerance，并归档 train/test logs、runtime probe、baseline report 和 handoff | 可以宣传真实本地 baseline proof；不能宣传 leaderboard、完整论文所有表格或自动改进闭环 |
| fastText AG News | `docs/evidence/fasttext-ag-news-p3-patch-round-20260513-cn.md` | 基于可信 baseline 执行一次客户端风格 proposal `-wordNgrams 2`，`P@1` 从 `0.914` 提升到 `0.916`，delta `+0.002`，并归档 proposal、diff、train/test logs、improvement report 和 handoff | 可以宣传真实本地受控 patch loop proof；不能宣传 leaderboard、完整论文所有表格或任意自动优化 |
| fastText AG News | `docs/evidence/fasttext-ag-news-p4-proof-bundle-20260514-cn.md` | 将 P3 patch round 打包为 `approved_with_limitations` proof bundle，包含 `10` 个 artifact、`human-review-report.json`、`proof-manifest.json`、`artifact-index.json` 和 `SHA256SUMS` | 可以宣传真实本地 proof bundle 和 hash-indexed evidence；不能宣传 leaderboard、完整论文所有表格或无人值守自动科研 |
| fastText AG News | `docs/evidence/proof-archives/fasttext-ag-news-full-reproduction-20260517/proof-archive.json` + `docs/reproduction-pilot/fasttext-full-reproduction-user-trial-cn.md` | 执行 2 轮 proposal，其中 1 轮 `wordNgrams=2` 成功、1 轮非法 `bucket=100` 被记录为失败，best `P@1=0.916`，rollback events `1`，并生成已脱敏、可 checksum 复核的 public `release-proof-bundle.tar.gz` | 可以宣传 fastText/AG News 核心实验轨道的真实本地复现、受控提升、失败/回滚和可下载 proof archive；不能宣传 leaderboard、完整论文所有表格或任意自动优化 |
| Smol AI WorldCup Qwen3-8B 本地诊断 | `docs/hf-evaluation/smol-worldcup-qwen3-8b-20260521/README.md` | LM Studio 本地 `qwen/qwen3-8b` 关闭 thinking 后完成 125 题本地诊断：`SHIFT=77.973529`、`WCS_local_diagnostic=88.302621`、failure count `48`；非 `llm_judge` 确定性子集为 `84.47%`。随后用 `p3-dev-v2` 做 dev/canary 受控迭代，dev `SHIFT` 相比同集合 baseline `+3.187698`，canary `SHIFT` `+1.380953`。新增 `p3-semantic-v1` 失败/回滚样例：dev `llm_judge +3.625` 但 `SHIFT -1.731795`；新增保守 `p3-semantic-v2`：dev `SHIFT +0.940298`、`llm_judge +2.625`，canary 相比 `p3-dev-v2` `SHIFT -0.333334` | 可以宣传本地 Qwen3-8B provider 已纳入同一评测/proposal/proof 管线，并证明 `p3-dev-v2` 对 confidence calibration 有本地收益，`p3-semantic-v2` 是有 dev 收益但未通过 canary 替代默认 profile 的可选语义候选；不能宣传 Hugging Face 官方提交、leaderboard score、hidden-test 结果或全面模型能力提升 |
| Hugging Face 外部评测候选 | `docs/hf-evaluation/hf-external-eval-track-cn.md` + `docs/hf-evaluation/cp-bench-submittable-proof-cn.md` + `docs/hf-evaluation/target-shortlist.json` + `docs/hf-evaluation/hf-submittable-targets-20260522-cn.md` + `docs/hf-evaluation/cp-bench-p17-client-solver-expansion/` + `docs/hf-evaluation/cp-bench-p17-manual-submission-gate/` + `docs/hf-evaluation/smol-worldcup-qwen3-8b-20260521/` | 已将第一优先级从 Smol AI WorldCup 调整为 CP-Bench Leaderboard，并完成 CP-Bench P0-P17 证据链。P17 是当前最强非 reference local proof：34-row verified slice 上 `runtime_success=34/34`、`final_solution_accuracy_percent=52.38`、33/34 通过，仅剩 crossfigures 失败；`leaderboard-competitiveness-audit.json` 显示当前公开 verified storage 最低结果为 `46.03`，P17 本地结果若提交预计为 `17/18`，因此已生成 manual submission gate。Smol AI WorldCup 仍保留为本地诊断和 proposal loop 训练场。 | 可以宣传“CP-Bench 本地 proof 已达到人工提交复核门槛，并生成可复核 submission gate”。当前没有 CP-Bench 或其他 HF submission、leaderboard 成绩或官方外部排名；P17 仍是 local evaluator proof，不是官方 leaderboard 成绩；CP-Bench 上游已归档并推荐 DCP-Bench-Open；正式提交前不得宣传 leaderboard score，所有相关 artifact 保持 `official_scores_claimed=false` |

## 待完成

- MLE-bench：完整 agent run-group / Docker / 多任务评分。
- PaperBench：real judge debug path。
- PaperBench：客户端模型驱动的真实 reproduction attempt。
- Public artifact：fastText/AG News 已提交仓库内脱敏 public proof archive；后续还需把 release proof bundle 附到 GitHub release 或外部可下载存储，并补充第三方独立复核说明。
- Hugging Face 外部评测：CP-Bench 已被选为下一条第一优先级可提交 proof 线，并完成 P0-P17；其中 P17 已扩展到 34 个 verified rows，33 个非 reference client solver 通过，`final_solution_accuracy_percent 0.0 -> 52.38`，本地分数超过当前公开 verified storage 最低结果 `46.03`，并生成 manual submission gate。下一步不是再证明“是否可提交”，而是做人工风险复核、确认 CP-Bench archived 边界、选择是否上传 CP-Bench 或转向 DCP-Bench-Open。Smol AI WorldCup P0/P1/P2/P3、本地 provider diagnostics、正式 scorer-v2 rescore、confidence 双轨审计和 proof archive 已完成；Space `/evaluate` 提交通路已探测，当前对本地模型结果为 `blocked_for_local_predictions`。正式提交前不得宣传 leaderboard score。

## 可用审查路径

- CLI：`ml-loop benchmark paperbench-codex-review-bundle --run-dir <paperbench-run-dir> --paper-dir <paperbench-paper-dir> --output-dir <review-bundle> --json`
- CLI：`ml-loop benchmark paperbench-codex-review-report --bundle <review-bundle/codex-review-bundle.json> --review-file <codex-review.json> --output-dir <review-report> --json`
- MCP：`prepare_paperbench_codex_review_bundle` -> Codex/Claude 审查 packet -> `write_paperbench_codex_review_report`
