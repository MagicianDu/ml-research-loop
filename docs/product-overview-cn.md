# ML Research Loop 中文产品说明

## 一句话定位

ML Research Loop 是一个面向 Codex、Claude 等 MCP 客户端的机器学习研究执行服务。它把 ml-intern 的研究检索、论文/数据集/代码证据整理能力，与 autoresearch 的固定预算实验、代码/超参迭代、结果复盘能力合并成一个可审计的闭环。

## 适用对象

- 想让 Codex 或 Claude 辅助做模型实验和效果迭代的研究者。
- 需要把论文想法快速转成可验证实验的 ML 工程师。
- 希望在本地受控环境中运行自动实验，而不是把训练执行完全交给远端黑盒服务的团队。
- 想评估“读论文、提假设、跑实验、复盘、继续改代码/超参”这条链路是否能产品化的研发负责人。

## 核心价值

- **研究有证据**：`research_task`、`read_paper` 会返回 sources、findings、evidence citations、provider coverage 和 retrieval diagnostics，降低模型凭空规划的风险。
- **实验可复现**：任务、结果、日志、快照、复现 readiness 和 grade report 都落到 runtime artifacts 中。
- **迭代可控**：默认由 Codex/Claude 做 planner，MCP 服务只执行受限工具；服务端自主 LLM 循环必须显式调用 `run_ai_autoresearch`。
- **代码改动有护栏**：客户端 patch 需要通过 SEARCH REGION stale check、workspace path sandbox、syntax/test preflight 和 rollback。
- **产品契约可检查**：`get_service_manifest` 和 `mcp_client_acceptance.py` 提供 contract version、tool contracts、compatibility check 和 migration hints。

## 典型工作流

1. Codex/Claude 调用 `get_service_manifest`，确认 contract、tools、execution sandbox 和 compatibility。
2. 调用 `research_task` 或 `read_paper` 获取论文、数据集和证据上下文。
3. 调用 `propose_hypotheses` 生成可验证假设。
4. 调用 `run_hypothesis_experiment` 执行固定预算实验。
5. 调用 `review_research_results` 获取 research review、experiment tree、dataset profile、code change plan 和 planner actions。
6. Codex/Claude 根据 `experiment_state` 决定下一轮：
   - 使用 `run_next_experiment_from_review` 自动执行建议 patch。
   - 使用 `run_client_patch_experiment` 验证单参数 proposal。
   - 使用 `apply_client_code_patch` 应用受控代码 diff。
   - 需要无人值守时显式切到 `run_ai_autoresearch`。

## 已支持能力

- MCP stdio 服务，支持 Codex、Claude Code、Claude Desktop 接入。
- 真实 provider 检索质量报告：provider coverage、source rankings、retrieval diagnostics、rate-limit recovery hints。
- 自动实验闭环：任务配置、训练运行、结果读取、下一轮 patch、loop decision。
- 真实数据/真实代码 patch benchmark。
- AIDE-style experiment tree：best node、draft/improve/debug stage、next action。
- PaperBench-style lightweight reproduction：local reproduction spec、required files readiness、rubric grade report。
- Artifact lifecycle：list、archive、clean runtime artifacts。
- P5 product hardening：execution metadata、timeout policy、sandbox roots、artifact retention paths、contract compatibility gate。

## 架构边界

本项目采用混合 MCP 架构：

- **Codex/Claude 客户端模型**：理解目标、选择工具、阅读结果、提出下一步代码或超参改动。
- **ML Research Loop MCP 服务**：执行检索、假设生成、受控实验、日志读取、结果复盘、patch preflight、artifact 管理。
- **服务端 LLM 后端**：默认关闭，只在用户明确需要无人值守自动实验时启用。

AIDE 和 PaperBench 目前是架构模式来源，不是运行时依赖。项目吸收的是 experiment tree、reproduction、rubric 和 grading 思路，而不是直接引入上游 Docker/GPU/nanoeval/alcatraz 执行栈。

## 安全和可审计性

- 执行路径受 `ML_RESEARCH_LOOP_ALLOWED_ROOTS` 和 runtime root 约束。
- workspace 必须位于 runtime root 内。
- `apply_client_code_patch` 只接受 workspace-relative unified diff，并支持 syntax/test preflight 与失败 rollback。
- 每个执行类 payload 返回 `execution_metadata`，包括 wall time、Python executable、timeout policy、sandbox roots 和 artifact retention paths。
- `mcp_client_acceptance.py` 会输出 `compatibility_check`，不兼容时给出 migration hints。

## 当前产品状态

当前状态是 **preview MCP product**：

- 本地 release gate 已覆盖 lint、pytest、MCP stdio smoke、client acceptance、golden path、多轮闭环、auto-next、client patch、provider benchmark、real-data、real-code patch 和 reproduction demo。
- 适合本地试用、内部评审和继续产品化打磨。
- 尚未进入 stable release：还需要正式版本 tag、release notes、远端发布流程、安装分发体验和稳定合约策略。

## 快速验收

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/release_check.py --json
```

成功时应返回 `status: passed`，并在 checks 中看到 `ruff`、`pytest`、`mcp-client-acceptance`、`mcp-real-data`、`mcp-reproduction` 等通过。

## 相关文档

- MCP 接入说明：`docs/mcp-client-setup.md`
- 混合架构要求：`docs/hybrid-mcp-architecture.md`
- 发布检查清单：`docs/release-checklist.md`
- 产品化 TODO：`docs/productization-todos.md`
- 客户端 planner 模板：`docs/client-planner-template.md`
