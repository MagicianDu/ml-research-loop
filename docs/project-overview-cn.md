# ML Research Loop 项目整体说明

## 项目定位

ML Research Loop 是一个面向 Codex/Claude 等强模型客户端的 AI-native 机器学习研究执行层。项目目标不是再做一个独立聊天 agent，而是把 ml-intern 的研究检索和证据整理能力、autoresearch 的固定预算实验和结果复盘能力，封装成可审计、可复用、可由 MCP 调用的本地研究闭环。

项目目标和设计原则以 `docs/product/target-architecture-cn.md` 为准。任何新增 MCP 工具、skill、memory adapter、benchmark adapter 或宣传材料，都不能改变该文档定义的分层职责、非目标和 claim boundary。

下一阶段产品形态应明确为 **MCP + Skills**：

- **MCP** 负责工具执行、路径 sandbox、实验运行、artifact 管理、结构化结果和 contract compatibility。
- **Skills** 负责告诉 Codex/Claude 什么时候调用哪些工具、如何判断证据质量、如何推进实验循环、何时停止或升级到人工确认。

这意味着项目的核心不是让服务端替代 Codex/Claude 的大模型能力，而是把本地研究和实验能力变成强模型可稳定调用的执行底座。

最新架构决策是新增 **Research Memory Layer**：用 Graphiti + cognee 作为可选长期记忆基础设施，让过去的论文复现经验、模型配置、超参、patch、失败原因和 proof archive 能被后续任务检索和复用。项目自己的 `ResearchMemoryCard`、artifact provenance、claim boundary、MCP contract 和 privacy policy 仍然是主控层。

## 当前融合结果

### ml-intern 侧

当前已吸收并产品化的能力包括：

- 论文、数据集、代码来源的研究上下文组织。
- `read_paper`、`research_task`、`propose_hypotheses` 等工具入口。
- provider coverage、source rankings、retrieval diagnostics、rate-limit recovery hints。
- evidence citations，将 findings 绑定到具体来源片段，降低无证据推理风险。
- query fanout 和 cache-aware 检索恢复路径。

后续还需要继续增强真实 provider 的覆盖率、缓存命中质量、证据去重和 citation 可追溯性。

最新 P2 迭代已把这部分状态进一步结构化到 MCP 返回值中：

- `deduplication_report`：展示原始来源数、去重后来源数、重复来源和 provider/source type 计数。
- `cache_summary`：展示 backend 数、命中/未命中、cache 文件和 freshness 范围。
- `provider_quality_matrix`：按 provider 和 source type 聚合证据质量、来源类别和评分。

### autoresearch 侧

当前已吸收并产品化的能力包括：

- `program.md` 驱动的任务说明和固定预算实验。
- `train.py` 工作区、参数采样、结果 JSON、日志和 progress artifact。
- `run_hypothesis_experiment`、`review_research_results`、`run_next_experiment_from_review`。
- SEARCH REGION 级别的受控超参 patch。
- real-code patch preflight、rollback、post-run review 和 loop decision。
- dataset profile、code change plan、next experiment plan。

后续还需要继续增强真实任务上的自动 patch 选择、失败诊断、实验树搜索策略和跨轮停止条件。

最新 P2 迭代已增加：

- `failure_diagnostics`：把失败实验归类为 timeout、missing file、training divergence、runtime exception 等可行动原因。
- `metric_stop_policy`：把 experiment tree、loop policy 和当前 best metric 合并成客户端可直接使用的继续/停止建议。
- `benchmark_summary`：在 real task/code benchmark 中固定回传 data source、patch mode、changed files、failure diagnostics 和 metric stop policy。

### AIDE / PaperBench 模式吸收

项目已吸收 AIDE 和 PaperBench 的架构模式，但不直接依赖其运行栈：

- AIDE 贡献的是 experiment tree、best node、draft/improve/debug stage 和 next action 思路。
- PaperBench 贡献的是 reproduction spec、rubric task、required files readiness 和 grade report 思路。
- 上游 Docker、GPU、nanoeval、alcatraz、Kaggle-specific runtime 不进入当前默认产品路径。

这个边界很重要：本项目保留轻量、本地、MCP-first 的服务形态，同时借鉴成熟项目的研究和评测组织方式。

## 产品架构

```text
Codex/Claude
  强模型 planner，理解目标、读结果、决定下一步

Skills
  工作流、调用顺序、证据门槛、停止条件、人工确认规则

MCP Service
  stdio tools、manifest、tool contracts、sandbox、execution metadata

Research Memory Layer
  ResearchMemoryCard、memory extraction、Graphiti 关系图谱、cognee 语义检索

Research + Experiment Runtime
  papers/cache/tasks/results/workdir/snapshots/archive
```

默认情况下，服务端不会隐式调用 LLM。只有显式调用 `run_ai_autoresearch` 时，才会让服务端 LLM provider 参与无人值守自动实验。

Research Memory Layer 同样保持显式边界：它可以给 Codex/Claude 提供历史经验和候选建议，但不能替代 release gate、proof archive 或人工/客户端强模型判断。Graphiti/cognee 在第一阶段是 optional adapter，不进入默认最小安装路径。

## 主要入口

- `get_service_manifest`：读取版本化工具契约、schema、推荐工作流和兼容性要求。
- `research_task` / `read_paper`：准备研究证据。
- `propose_hypotheses`：把研究证据转成可验证假设。
- `run_hypothesis_experiment`：执行 hypothesis-backed 实验。
- `review_research_results`：返回研究复盘、实验树、复现 readiness、code change plan 和 planner actions。
- `run_next_experiment_from_review`：根据 review 自动执行下一轮 task patch。
- `run_client_patch_experiment`：验证 Codex/Claude 提出的单参数改动。
- `apply_client_code_patch`：在受控 workspace 内执行代码 diff preflight、rollback 和后续实验。
- `list_runtime_artifacts`、`archive_runtime_artifacts`、`clean_runtime_artifacts`：管理本地 artifact。

## 当前状态

当前项目状态是 **preview MCP product**，适合本地试用、内部评审和继续产品化迭代。

已完成的产品化阶段：

- P0：安全执行、真实任务 readiness、subprocess lifecycle hardening。
- P1：真实 provider 检索质量、证据引用、patch planning 和 auto-next。
- P2：安装、接入、artifact lifecycle 和产品文档。
- P3：客户端 planner patch loop 和 real-code patch 执行。
- P4：真实 provider / 真实任务 benchmark。
- P5：execution metadata、compatibility check 和 migration hints。
- P6：experiment tree、reproduction spec、rubric grade report。
- P7：MCP + Skills 产品层，包括 planner、reproduction、experiment optimizer 和 operator skills。

## 验收方式

当前 release gate：

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/release_check.py --json
```

成功时应看到 `status: passed`，并覆盖 ruff、pytest、MCP stdio smoke、client acceptance、golden path、多轮实验、auto-next、client patch、provider benchmark、real-data、real-code patch 和 reproduction demo。

## 文档地图

- 产品说明：`docs/product-overview-cn.md`
- 开源定位说明：`docs/open-source-positioning-cn.md`
- 演示 transcript：`docs/demo-transcript-cn.md`
- 5 分钟发布演示：`docs/launch-demo-cn.md`
- fresh checkout 验收：`docs/fresh-checkout-validation-cn.md`
- 真实论文复现演示：`docs/real-paper-reproduction-demo-cn.md`
- 后续路线图：`docs/development-roadmap-cn.md`
- 目标架构与设计原则：`docs/product/target-architecture-cn.md`
- Skills 使用说明：`docs/skills-setup-cn.md`
- MCP 客户端接入：`docs/mcp-client-setup.md`
- 混合架构要求：`docs/hybrid-mcp-architecture.md`
- Research Memory Layer 决策：`docs/product/research-memory-layer-cn.md`
- 客户端 planner 模板：`docs/client-planner-template.md`
- 发布检查清单：`docs/release-checklist.md`
- 产品化 TODO：`docs/productization-todos.md`
- 历史开发计划：`docs/superpowers/plans/`
