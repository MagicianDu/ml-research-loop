# Benchmark Adapter Roadmap

本文说明当前 benchmark adapter 的产品定位：它是 ML Research Loop 从 MCP preview 走向公开研究复现/自动实验评测的桥，不是官方榜单成绩声明。

## 当前已证明

- MLE-bench 方向已经能生成本地 deterministic fixture、任务文件、run-group metadata、`submission.csv` 和 `benchmark_report.json`。
- PaperBench 方向已经能表达 Agent Rollout、Reproduction、Grading 三阶段，并生成 submission、reproduction report、grade report 和 benchmark report。
- `ml-loop benchmark readiness --json` 和 MCP manifest 已经能暴露当前 adapter readiness。
- `ml-loop benchmark smoke --runtime-root <dir> --json` 已经能一条命令跑完两条 compatibility demo。
- `ml-loop benchmark probe --json` 已经能只读检查官方 harness 的命令、repo、数据和 credential 前置条件。
- `ml-loop benchmark proof-plan --json` 已经能把只读 probe 转成公开 proof-run 决策：当前是否 blocked、推荐在哪类环境跑、缺哪些前置条件、哪些命令安全、哪些命令仍被阻止。
- `ml-loop benchmark setup-bundle --output-dir <dir> --json` 已经能写出外部 evaluation 环境准备包，包括 env example、手动 setup 命令、官方引用和 artifact requirements；它不安装依赖、不下载数据、不写 secrets、不声明官方成绩。
- `ml-loop benchmark publication-bundle --manifest <file> --artifact-root <dir> --output-dir <dir> --json` 已经能检查未来官方 debug/small run 的 artifacts 是否完整，并阻止缺证据的官方分数声明。
- `ml-loop benchmark archive-proof --manifest <file> --artifact-root <dir> --output-dir <dir> --json` 已经能把完整 proof-run artifacts 复制归档，生成 SHA-256 索引，并嵌入 publication guard。
- 同一套 proof lifecycle 已暴露为 MCP tools：`get_benchmark_harness_probe`、`plan_benchmark_proof_run`、`write_benchmark_proof_setup_bundle`、`write_benchmark_proof_publication_bundle`、`write_benchmark_proof_archive`，Codex/Claude 可以直接通过 MCP 调用。
- 在已经完成官方 MLE-bench `prepare` 的前提下，`ml-loop benchmark mle-workspace --competition-id <id> --prepared-competition-dir <dir> --runtime-root <dir> --json` 可以生成 agent 可编辑 workspace：只复制 `prepared/public`，写入 `solve.py`、`submission.csv`、`agent_instructions.md` 和 `benchmark_contract.json`。
- `ml-loop benchmark mle-grade --competition-id <id> --submission <file> --data-dir <dir> --mlebench <exe> --output-dir <dir> --json` 可以调用官方 `mlebench grade-sample`，把本地 scorer feedback 写成 `grade-report.json` 和 `grade.log`。
- `ml-loop benchmark mle-round --competition-id <id> --workspace <workspace> --data-dir <dir> --mlebench <exe> --output-dir <dir> --json` 可以把一次客户端改动后的 `solve.py` 执行、`submission.csv` 生成、官方 `grade-sample` 本地评分和 `round-report.json` 串成一个可审计 round。
- `ml-loop benchmark mle-patch-round --competition-id <id> --workspace <workspace> --data-dir <dir> --mlebench <exe> --output-dir <dir> --patch-file <patch.diff> --json` 可以把客户端生成的 bounded diff、guarded patch、solver round、local scorer feedback 和 loop decision 合成一个闭环。
- `ml-loop benchmark mle-patch-proof --patch-round-report <rounds/round-id/patch-round-report.json> --output-dir <proof-dir> --json` 可以把 patch-round 的 diff、报告、日志、snapshot 和限制说明打包进 publication guard + hashed archive。
- 对应 MCP tools 已暴露为 `prepare_official_mle_bench_workspace`、`run_official_mle_bench_round`、`run_official_mle_bench_patch_round`、`write_official_mle_bench_patch_round_proof_bundle` 和 `grade_official_mle_bench_submission`。这让 Codex/Claude 能通过强模型规划代码/提交改动，再由 MCP 服务执行 workspace 创建、patch preflight、单轮 solve/grade、本地评分反馈和 proof archive。
- 已拿到一份真实 MLE-bench official-debug hard result：`spooky-author-identification` baseline log loss `1.08468`，客户端 patch 后最佳 log loss `0.37038`，超过 median threshold `0.418785`，proof archive 状态为 `archivable`，且 `official_scores_claimed=false`。详见 `docs/evidence/mle-bench-spooky-20260507-cn.md`。
- 已跑通 PaperBench official debug dummy path / debug dummy harness：`rice` debug sample 完成 rollout、reproduction、grading 三阶段，dummy judge score `1.0`，三类 failure 均为 `0`，但不是官方 PaperBench score。详见 `docs/evidence/paperbench-debug-dummy-20260507-cn.md`。
- 已新增 PaperBench Codex-assisted review path：`ml-loop benchmark paperbench-codex-review-bundle` 可以把 paper/rubric/run/submission artifacts 打成审查包，`ml-loop benchmark paperbench-codex-review-report` 可以把客户端 Codex/Claude 的 rubric review 固化为报告。公开口径必须保留：Codex-assisted rubric review is not an official PaperBench score，且 `official_scores_claimed=false`。
- 对应 MCP tools 已暴露为 `prepare_paperbench_codex_review_bundle` 和 `write_paperbench_codex_review_report`，方便 Codex/Claude 在没有 real judge API key 时先做证据约束的人工/模型辅助审查。
- 两条路径都复用现有 ML Research Loop 能力：研究/实验 artifact、bounded local execution、reproduction spec、rubric grade report、日志和结果路径。
- compatibility adapter 仍明确输出非官方标记：`official_mle_bench=false`、`official_paperbench=false`；官方 MLE bridge 则标记 `official_mle_bench=true`，但始终保持 `official_scores_claimed=false`。
- 这些产物足够让 Codex/Claude 作为客户端 planner 读取状态、定位证据、判断下一轮实验或复现动作。

## 尚未证明

- 尚未执行完整官方 MLE-bench agent run-group / Docker / `mlebench grade` 多任务评分；当前已证明的是 prepared-data workspace + `grade-sample` 本地反馈闭环。
- 尚未执行官方 PaperBench real judge / LLM judge path；debug dummy path 已跑通，但 `score=1.0` 只能证明 harness 全链路连通，不能证明论文复现质量。Codex-assisted review 能生成诚实的审查报告，但也不能替代官方 real judge；real judge 仍需要真实 `OPENAI_API_KEY` 或 `GRADER_OPENAI_API_KEY`。
- 尚未形成可公开复核的 leaderboard 级结果，也不应该把 compatibility spike 的 demo 分数当成 benchmark score。
- 尚未验证长时间、多任务、外部数据下载和失败恢复在官方 harness 下的稳定性。

## 下一步路线

1. **P13: Benchmark Adapter Productization**
   - 已完成统一的 benchmark compatibility smoke，一次跑完 MLE-bench-shaped 和 PaperBench-shaped demo。
   - 已在 CLI 和 MCP manifest 中暴露 benchmark readiness，而不是只靠文档说明。
   - 把两个 benchmark report 打包进 feedback/reproducibility bundle。

2. **P14: Official Harness Feasibility**
   - 已增加只读 probe，检查本机是否具备 MLE-bench / PaperBench 官方 harness 的必要条件。
   - 已明确依赖：credentials、数据、Docker/环境、运行时间、费用和磁盘需求。
   - 下一步要决定官方评测应在本机、CI、还是独立 evaluation 环境执行。

3. **P15: Public Proof Run**
   - 已增加 proof-run plan，先把官方 debug 或最小公开任务的环境决策、缺口、安全命令、blocked commands 和 artifact requirements 固化。
   - 已增加 setup bundle，把外部 evaluation 环境需要补齐的材料写成可复核文件。
   - 已增加 publication guard，让未来 artifacts 发布时自动区分可公开事实、限制说明和禁止声明的官方分数。
   - 已增加 proof archive，让外部 proof-run 完成后可以把 artifact 哈希归档并交给 MCP 客户端复核。
   - 已增加 MCP-first proof tools，让客户端不需要 shell CLI 就能执行 probe、plan、setup、publication、archive。
   - 已局部完成一条官方/debug proof 的文档发布闭环：MLE-bench official-debug hard result、PaperBench debug dummy harness、PaperBench Codex-assisted review 已进入 `docs/evidence/benchmark-results-index-cn.md`，并写明 `official_scores_claimed=false`。当前 checkout 未保留对应 `.demo_runs` 原始 artifact，因此不能把它说成 release-downloadable proof bundle。
   - 下一步是补外部可下载 release artifact、第三方复核路径、完整 MLE-bench run-group 和 PaperBench real judge / LLM judge。
   - 再考虑正式 leaderboard 或公开复现声明；对外传播时只说可复现的事实，不把本地 fixture 分数包装成官方能力证明，不能宣传 leaderboard。

4. **P16: Official MLE-bench Agent Loop**
   - 已新增 prepared-data bridge：官方 `prepare` 完成后，服务可以生成 agent workspace。
   - 已新增本地 `grade-sample` feedback：客户端模型可以改 `solve.py` 或 `submission.csv`，运行 `python solve.py`，再调用 scorer 验证。
   - 已新增 MCP/CLI 单轮闭环：`run_official_mle_bench_round` / `ml-loop benchmark mle-round` 会执行 solver、调用 scorer，并写出 solve log、grade report 和 round report。
   - 已新增 patch-round 闭环：`run_official_mle_bench_patch_round` / `ml-loop benchmark mle-patch-round` 会应用客户端 diff、运行 scorer，并返回 `loop_decision`，但代码生成仍由 Codex/Claude 负责。
   - 已新增 patch proof archive：`write_official_mle_bench_patch_round_proof_bundle` / `ml-loop benchmark mle-patch-proof` 会把 patch-round artifacts 打包为可发布前审核的 proof archive。
   - 已完成一次官方数据 + 官方本地 scorer 的 hard result：baseline `1.08468`，最佳 patch `0.37038`，`above_median=true`，artifact archive 可复核。
   - 当前仍不声明 leaderboard 成绩，`official_scores_claimed=false` 是硬边界。
   - 下一步是把多轮 patch/grade proof 串成 run-group 级 evidence，并扩展到真实 solver 生成而不是 sample-submission baseline。

5. **P17: PaperBench Codex-Assisted Review Loop**
   - 已新增 keyless 审查包：`paperbench-codex-review-bundle` 复制 paper/rubric/run/submission 证据并写出 Codex review prompt。
   - 已新增 keyless 审查报告：`paperbench-codex-review-report` 记录 `summary`、`codex_review_score`、leaf scores、evidence refs、missing evidence 和 confidence。
   - 已新增 MCP-first 工具：`prepare_paperbench_codex_review_bundle` 和 `write_paperbench_codex_review_report`。
   - 该路径解决“没有 judge API key 时如何诚实展示 PaperBench 复现审查”的问题，但不会生成官方 PaperBench 分数。
   - 已对 official debug `rice` artifact 产出一份真实 Codex-assisted review report：审查分 `0.0`，结论是 dummy run 只有 harness 连通证据，没有实质论文复现证据。
   - 已把 report 纳入 proof archive，archive 状态为 `archivable`，artifact count 为 `14`。详见 `docs/evidence/paperbench-codex-review-rice-20260507-cn.md`。

## 与最终目标的关系

最终目标是把项目做成 Codex/Claude 可调用的 MCP + Skills 产品，用客户端强模型做研究判断、代码修改和超参迭代，服务端负责可靠执行和审计。Benchmark adapter 的价值在于把这种能力放到公开可理解的评测形态里：MLE-bench 偏 ML engineering 自动实验，PaperBench 偏论文复现与证据质量。当前集成完成后，项目具备了评测形态的骨架；下一步要补官方 harness 和可复核 proof run。
