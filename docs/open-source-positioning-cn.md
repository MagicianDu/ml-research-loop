# ML Research Loop 开源定位说明

## 一句话差异

ML Research Loop 不是再做一个聊天式研究 agent，而是把 Codex、Claude 这类强模型可以调用的 **本地 ML 研究执行层** 做完整：研究检索、证据质量、实验运行、结果复盘、patch 护栏、复现评分和 skills 工作流都进入同一个 MCP 产品契约。

项目目标架构已固化在 `docs/product/target-architecture-cn.md`：MCP + Skills + Research Memory Layer + Runtime Artifacts 共同构成产品边界，Graphiti/cognee 只是可选 adapter，不改变 Codex/Claude planner 与 MCP executor 的职责分离。

## 和单独使用 ml-intern 的区别

ml-intern 更偏研究侧：读论文、查数据集、组织工具、形成研究计划。ML Research Loop 保留这部分能力，但把输出约束成可以被实验验证的结构：

- sources、findings、hypotheses 可以进入实验任务；
- provider coverage 和 retrieval diagnostics 告诉客户端证据是否足够；
- evidence citations 把 finding 绑定到具体来源片段；
- cache 和 query fanout 让检索失败时有恢复路径。

这样 Codex/Claude 不只是“读到资料”，还能判断资料质量，并把资料转成下一步实验动作。

## 和单独使用 autoresearch 的区别

autoresearch 更偏实验侧：固定预算、修改 `train.py`、跑训练、记录结果。ML Research Loop 保留这部分能力，但补上研究上下文和客户端 planner handoff：

- hypothesis-backed task 会把研究依据写入 `program.md`；
- `review_research_results` 返回 experiment tree、dataset profile、code change plan 和 planner actions；
- `run_next_experiment_from_review` 可以消费 review 自动进入下一轮；
- `apply_client_code_patch` 支持受控 diff、syntax/test preflight 和失败 rollback。

这样实验不是孤立随机搜索，而是可以由研究证据和历史结果共同驱动。

## 和通用 MCP 工具集合的区别

很多 MCP server 只是把命令包装成工具。ML Research Loop 的目标更窄：让机器学习研究循环可被强模型稳定复用。

因此项目把这些内容做成显式产品契约：

- `get_service_manifest` 暴露 contract version、tool contracts、skill contracts 和 compatibility；
- 执行类工具返回 `execution_metadata`、timeout policy、sandbox roots 和 artifact retention；
- runtime artifacts 固定落到 tasks、results、workdir、snapshots、archive；
- 下一阶段用 Research Memory Layer 把过去的论文复现、实验、patch、失败、rollback 和 proof bundle 转成可复用记忆；
- client planner 必须读取 `experiment_state` 再决定下一步；
- 服务端 LLM 默认关闭，只有显式调用 `run_ai_autoresearch` 才启用。

## MCP + Skills 的产品形态

MCP 解决“能调用什么工具”，skills 解决“应该怎样调用这些工具”。本项目把两者绑定：

- MCP tools 负责真实执行和结构化结果；
- skills 负责调用顺序、证据门槛、停止条件、失败恢复和人工确认；
- manifest 把 recommended skills 和当前 contract version 绑定起来；
- Codex/Claude 可以复用自身大模型能力做 planner，而不是把核心智能硬塞进服务端。

这也是项目面向 AI-native 产品的核心判断：工具执行和模型推理应该解耦，但要通过稳定协议互相支撑。

## 借鉴 AIDE 和 PaperBench，但不生搬硬套

项目吸收的是架构模式：

- AIDE-style：experiment tree、best node、draft/improve/debug stage、loop policy；
- PaperBench-style：reproduction spec、required files readiness、rubric grade report。

项目没有把上游 Docker、GPU、Kaggle-specific runtime、nanoeval 或 alcatraz 作为默认依赖。这样可以保持本地 MCP 服务轻量、可安装、可审计。

新增的 Graphiti + cognee 记忆层也遵循同样原则：吸收成熟记忆系统的关系图谱和语义检索能力，但通过项目自己的 `ResearchMemoryCard`、artifact provenance 和 MCP contract 接入，避免把外部系统生搬硬套成默认运行时。

同时，项目已经把公开评测前的边界做成产品接口：`ml-loop benchmark
probe --json` 只读检查官方 harness 前置条件，`ml-loop benchmark
proof-plan --json` 把结果转成 blocked/ready 决策、缺失依赖、安全命令、阻止命令和 artifact requirements。它们用于准备 proof run，不等同于官方榜单成绩。

## 当前适合什么场景

适合：

- 本地试用 Codex/Claude 驱动 ML 实验闭环；
- 把论文想法快速变成可验证 hypothesis；
- 做受控小实验、多轮调参和 patch preflight；
- 为真实研究复现建立 artifact 和评分骨架；
- 评估 MCP + Skills 作为 AI-native ML 工具产品的形态。

暂不适合直接承诺：

- 无人值守的大规模 GPU 训练平台；
- 完全稳定的公共 API；
- 不受 rate limit 影响的实时全网检索；
- 替代专业 ML 工程师的生产模型发布流程。

## 开源发布阶段判断

当前是 **preview MCP product**。它已经具备本地可运行、客户端可接入、release gate 可验收的基础，但高强度公开传播前还应继续补强：

- P15 官方/debug benchmark proof 的文档发布闭环已局部完成：MLE-bench `spooky-author-identification` 是 official-debug hard result，PaperBench `rice` 是 debug dummy harness，PaperBench `rice` Codex-assisted review 是非官方审查报告；三者统一保持 `official_scores_claimed=false`，不是 official PaperBench score，也不能宣传 leaderboard。
- 当前 checkout 已补 committed real-task proof archives：`docs/evidence/proof-archives/memflow-real-paper-20260517/` 和 `docs/evidence/proof-archives/adam-real-paper-20260517/`。这两份证明 real-paper bounded pilot 可复核，但不等同于完整论文复现或官方 benchmark。
- 当前 checkout 已补可下载 release artifact：`dist/ml_research_loop-0.1.0-py3-none-any.whl`、`dist/ml_research_loop-0.1.0.tar.gz` 和 `dist/SHA256SUMS`。
- clean checkout 验证和首个 release tag；
- 更短的安装体验，例如 `pipx` 安装路径和 release asset 分发；
- 更丰富的 demo transcript、截图或录屏；
- 更多真实 provider 的稳定性和缓存质量；
- 更长轮次真实任务的 benchmark 报告。
- official/debug benchmark proof bundle、第三方复核路径、外部 pilot feedback，以及 PaperBench real judge / LLM judge 仍需后续补齐。

这意味着现在可以作为 preview 开源，但高调推广前还应该做一次 launch polish 和 beta release。
