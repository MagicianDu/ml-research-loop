# ML Research Loop Skills 使用说明

## 为什么需要 Skills

MCP 只暴露工具和结构化返回；Skills 固化 Codex/Claude 应该如何选择工具、如何判断证据质量、如何处理失败、什么时候停止或请求人工确认。

目标架构见 `docs/product/target-architecture-cn.md`。Skills 必须遵守该文档定义的职责边界：Skills 可以指导客户端如何使用 Research Memory Layer，但不能让记忆建议绕过 MCP guardrails、proof archive 或 release gate。

当前仓库提供四个 skill：

- `skills/ml-research-loop-planner/SKILL.md`：主入口，负责研究目标到 MCP 工具链的规划。
- `skills/ml-research-loop-reproduction/SKILL.md`：论文复现、`reproduction_spec`、`required_files`、rubric 和 `grade_report`。
- `skills/ml-research-loop-experiment-optimizer/SKILL.md`：实验树、patch 提案、rollback 和 `loop_decision`。
- `skills/ml-research-loop-operator/SKILL.md`：安装、验收、release check、artifact 管理和 troubleshooting。

## Codex 安装

在本机 Codex 环境中，推荐使用 CLI 安装仓库内的 skill 包：

```bash
ml-loop init-skills --client codex
```

这会把 `skills/ml-research-loop-*` 复制到默认的 `~/.codex/skills`。如果你的
Codex 使用 `~/.agents/skills` 作为 skill root，可以指定目标目录：

```bash
ml-loop init-skills --client codex --target-root ~/.agents/skills
```

如果目标 skill 已存在，命令会拒绝覆盖；确认要更新时加 `--force`：

```bash
ml-loop init-skills --client codex --force
```

也可以手动复制：

```bash
mkdir -p ~/.codex/skills
cp -R skills/ml-research-loop-* ~/.codex/skills/
```

重启 Codex 或开启新会话后，提到 ML Research Loop、模型实验优化、论文复现或 MCP 运维时，对应 skill 应能自动触发。

## Claude 安装

Claude Code 的官方 Skills 文档使用 `~/.claude/skills/<skill-name>/SKILL.md` 作为个人 skill 目录，也支持项目内 `.claude/skills/<skill-name>/SKILL.md`。推荐安装方式：

```bash
ml-loop init-skills --client claude
```

项目级安装：

```bash
ml-loop init-skills --client claude --target-root .claude/skills
```

手动复制方式：

```bash
mkdir -p ~/.claude/skills
cp -R skills/ml-research-loop-* ~/.claude/skills/
```

项目级安装：

```bash
mkdir -p .claude/skills
cp -R skills/ml-research-loop-* .claude/skills/
```

Claude Skills 官方参考：

- Claude Code Skills: https://code.claude.com/docs/en/skills
- Claude Agent SDK Skills: https://code.claude.com/docs/en/agent-sdk/skills

## 推荐使用顺序

1. 先安装并注册 MCP，按 `docs/mcp-client-setup.md` 完成 `get_service_manifest` 和 client acceptance。
2. 安装 skills。
3. 在 Codex/Claude 中描述目标，例如“用 ML Research Loop 帮我复现这篇论文”或“根据上轮结果继续提升 val_bpb”。
4. 让客户端先读取 `get_service_manifest`，再按 skill 选择工具。
5. 如果 manifest 暴露 memory 工具，先用 `retrieve_research_memory` / `suggest_from_memory` 检索相关历史经验，并用 `audit_memory_trace` 检查 provenance。
6. 每轮实验后读取 `review_research_results`，再决定继续、debug、补检索或停止。
7. 当 memory record 工具可用时，用 `record_research_memory` 把 review、proof bundle、失败和有效配置记录为可复用 memory card；只有经过复核的 card 才用 `promote_memory_card` 提升为长期 procedure。

## 与 MCP Manifest 的绑定

`get_service_manifest` 会返回 `recommended_skills` 和 `skill_contracts`。
客户端应把当前安装的 skills 与 manifest 对齐：

- `recommended_skills` 是当前 contract 推荐安装的 skill 名称。
- `skill_contracts.<skill>.contract_version` 必须匹配 MCP `contract_version`。
- `skill_contracts.<skill>.required_tools` 应能在 `tool_contracts` 中找到。
- contract mismatch 时停止自动实验循环，先按 `migration_hints` 或 release notes 处理。

## 安全边界

- 默认不要让服务端隐式调用 LLM；只有用户明确需要无人值守自动实验时才调用 `run_ai_autoresearch`。
- 弱证据、contract mismatch、广义代码 patch、destructive artifact cleanup 都需要人工确认。
- patch 必须经过 MCP 的 stale check、syntax/test preflight、rollback 或 metric review。
- runtime root 和 workspace 必须满足 MCP sandbox；需要额外路径时配置 `ML_RESEARCH_LOOP_ALLOWED_ROOTS`。
- memory suggestion 不能直接执行；必须先由 Codex/Claude 检查当前证据、预算和风险，再调用受控 MCP 工具。
