# ML Research Loop 后续开发路线图

## 路线原则

后续开发不再只围绕“增加 MCP 工具”推进，而是转向 **MCP + Skills** 的 AI-native 产品结构：

- MCP 保持稳定、可验收、可审计，负责真实执行。
- Skills 固化 Codex/Claude 的工作流、判断标准和安全边界。
- 服务端 LLM 自动实验保持显式调用，默认不替代客户端强模型 planner。
- 每一阶段都必须能通过本地 release gate 或新增验收脚本证明。

## P7: MCP + Skills 产品层

目标：让 Codex/Claude 不只是“能看到工具”，而是能稳定理解如何使用 ML Research Loop 完成研究和实验闭环。

计划交付：

- `ml-research-loop-planner`：主入口 skill，负责从用户目标到 MCP tool sequence 的规划。
- `ml-research-loop-reproduction`：论文复现 skill，负责论文证据、复现拆解、rubric readiness 和 grade report。
- `ml-research-loop-experiment-optimizer`：实验优化 skill，负责读取 review、判断下一轮 patch、执行停止条件。
- `ml-research-loop-operator`：安装、验收、artifact 管理和 release check skill。
- skills 安装说明，覆盖 Codex 和 Claude 的使用方式。

验收标准：

- skills 文档明确 MCP 工具调用顺序、输入输出、失败恢复和人工确认边界。
- 主 skill 要求先调用 `get_service_manifest`，再根据任务选择 research、experiment、reproduction 或 artifact flow。
- 每个 skill 都声明默认不隐式使用服务端 LLM，除非用户明确选择 `run_ai_autoresearch`。
- README、项目整体说明和 MCP setup 文档都能指向 skills 入口。

## P8: 真实研究检索质量

目标：进一步增强 ml-intern 侧的真实研究能力，让检索结果更适合被 Codex/Claude 用于实验决策。

计划交付：

- 更强 provider cache：按 query、provider、source type 和 freshness 组织缓存，并返回 `cache_scope`、`source_count`、`source_types` 和 `freshness_seconds`。
- 更严格 evidence quality：区分 `paper_fulltext_ready`、`paper_abstract`、`dataset_card`、`code_reference` 和弱证据。
- 更好的 citation trace：每个 finding 能追溯到 source id、snippet id、provider、URL 和 query variant。
- provider fallback 策略：rate limit、空结果、低覆盖率时给出明确恢复动作。
- research benchmark pack：固定一组 paper-heavy、dataset-heavy、code-heavy 查询用于回归测试。

验收标准：

- `research_task` 返回的 provider coverage、retrieval diagnostics、evidence citations 可稳定解释。
- benchmark 能区分缓存命中、provider 失败和真实空结果。
- 弱证据不会被标记为强支持，缺证据时必须触发 recovery hints。

## P9: 自动实验智能

目标：增强 autoresearch 侧对真实任务、真实数据集和真实代码改动的自动实验能力。

计划交付：

- MLE-bench adapter spike：先提供本地 deterministic fixture、run-group metadata、submission 和 benchmark report，明确 `official_mle_bench=false`，不宣称官方 leaderboard 分数。
- 更强 experiment tree policy：支持从失败、改进、复现 readiness 中选择下一轮动作。
- 更强 patch execution loop：支持多文件小范围 diff、测试选择、失败 rollback 和后续 review。
- metric-aware stop policy：将 best metric、variance、预算、失败原因合并为继续/停止判断。
- dataset-aware plan：数据太小、缺标签、路径错误、训练过快/过慢时给出不同处理策略。
- reproducibility pack：把任务配置、数据摘要、patch、日志、结果和 grade report 打包为可交付 artifact。

验收标准：

- MLE-bench spike 的 `benchmark_report.json` 保留 `competition_id`、`run_group`、`submission_path`、`metadata_path`、`grade_command_hint`、`task_file`、`result_file` 和 `best_metric`，并持续标记非官方运行。
- 真实本地任务上可以连续跑多轮，并返回可解释的 loop decision。
- patch 被拒绝时必须说明是 stale state、syntax/test failure、sandbox violation 还是 metric regression。
- reproduction readiness 和 experiment tree 能影响下一轮推荐动作。

## P9.5: PaperBench 兼容适配 Spike

目标：先用 dependency-free 的本地 fixture 验证 ML Research Loop 能表达
PaperBench 的 Agent Rollout、Reproduction、Grading 三阶段，并输出可交给
Codex/Claude 继续复现的 artifact。

计划交付：

- `lib/benchmarks/paperbench.py`：本地 PaperBench-shaped fixture、rubric
  grading 和 benchmark report 组装。
- `scripts/paperbench_adapter_demo.py`：一条命令跑通 submission、reproduction
  report、grade report 和 paperbench report。
- 文档和测试明确该阶段是兼容性 spike，不是官方 PaperBench leaderboard
  submission，报告必须保留 `official_paperbench=false`。

验收标准：

- demo JSON 包含 `agent_rollout.status`、`reproduction.status`、
  `grading.status`、`paper_id`、submission 路径和报告路径。
- grade report 复用现有 reproduction/rubric 结构，且 deterministic fixture
  的 score 大于 0。
- 不改变 MCP contracts，不声称官方 PaperBench 分数。

## P10: 发布和分发

目标：从 preview MCP product 推进到可对外发布的 beta/stable。

计划交付：

- 版本策略：contract version、schema version、migration notes 和 release notes。
- 安装体验：`pipx` / editable install / local MCP config 的最短路径。
- 客户端兼容矩阵：Codex、Claude Code、Claude Desktop。
- artifact retention 策略：默认保留、清理、归档和敏感信息提示。
- CI release gate：将本地 `scripts/release_check.py --json` 升级为可持续运行的发布检查。

验收标准：

- 新 checkout 能按文档完成安装、注册 MCP、跑 client acceptance 和一个 bounded demo。
- release notes 能说明 breaking change、migration hints 和已知限制。
- stable 前不再改变已发布 tool contract，除非提高 contract version。

## P13-P15: 公开 Benchmark 证明路径

目标：把当前 MCP + Skills + 自动实验/复现能力放进公开可理解的 benchmark 形态中，逐步从 compatibility spike 走向可复核 proof run。

计划交付：

- P13 Benchmark Adapter Productization：统一 MLE-bench-shaped 和 PaperBench-shaped adapter，补 combined smoke、artifact bundle 和 readiness 暴露。
- P14 Official Harness Feasibility：增加只读官方 harness probe，明确 credentials、数据、环境、运行成本和本地/CI/独立评测环境选择。
- P15 Public Proof Run：先跑官方 debug 或最小公开任务，保留命令、配置、日志、报告和限制说明，再考虑正式 leaderboard。

验收标准：

- compatibility demo 继续明确 `official_mle_bench=false` 和 `official_paperbench=false`。
- official harness probe 不启动长任务，只报告可行性和缺口。
- 对外文档不把本地 fixture 分数包装成官方 benchmark 分数。

## 当前推荐推进顺序

1. P13：先把两个 benchmark compatibility adapter 集成进主线，并补 combined smoke。
2. P14：再做官方 harness 可行性 probe，避免盲目宣称能打榜。
3. P15：最后做一个可公开复核的 proof run。

这个顺序的原因是：项目已经具备 MCP + Skills、研究检索、自动实验和开源发布基础；下一阶段的核心不再是“多一个 demo”，而是把能力映射到公开 benchmark 的证据链里。
