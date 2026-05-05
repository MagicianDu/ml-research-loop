# v0.1.0-preview 试用反馈指南

## 目标

这一版最需要真实用户反馈：别人能不能从 GitHub clone 后独立跑通，并理解 ML Research Loop 作为 Codex/Claude 可调用 MCP + Skills 执行层的价值。

## 5 分钟试用

```bash
git clone https://github.com/MagicianDu/ml-research-loop.git
cd ml-research-loop
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python3 scripts/mcp_client_acceptance.py --python "$(which python3)"
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30
```

如果你要接入客户端：

```bash
ml-loop init-mcp-config --client codex
ml-loop init-mcp-config --client claude-code --output /tmp/ml-research-loop.mcp.json
ml-loop init-skills --client codex --dry-run
ml-loop init-skills --client claude --dry-run
```

## 希望反馈什么

请优先反馈三类问题：

1. 安装是否成功：Python 版本、依赖安装、`mcp_client_acceptance.py` 是否通过。
2. MCP 是否能被客户端识别：Codex、Claude Code 或 Claude Desktop 是否能看到 `mlResearchLoop`。
3. 哪个环节最卡：文档、配置、skills、demo、实验耗时、错误信息或概念理解。

## 建议反馈格式

```text
使用系统：
Python 版本：
客户端：Codex / Claude Code / Claude Desktop / 其他
contract_version：

是否跑通 5 分钟试用：
是否接入 MCP 客户端：
最卡的步骤：
错误输出或截图：
你希望下一版优先改什么：
```

## 提交入口

- GitHub Issues: <https://github.com/MagicianDu/ml-research-loop/issues/new/choose>
- 固定反馈帖：<https://github.com/MagicianDu/ml-research-loop/issues/1>
- Preview release: <https://github.com/MagicianDu/ml-research-loop/releases/tag/v0.1.0-preview>

如果只是想说“我跑通了”，也很有价值。请附上系统、Python 版本、客户端和大概耗时。
