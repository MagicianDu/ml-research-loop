# Fresh Checkout 验证说明

## 目标

fresh checkout 验证用于证明公开 GitHub 仓库不是“只在本机可运行”，而是可以从一个全新目录完成安装、MCP 客户端验收、skills dry-run 和一个 bounded demo。

## 推荐命令

```bash
python3 scripts/fresh_checkout_check.py \
  --repo-url https://github.com/MagicianDu/ml-research-loop.git \
  --ref main
```

脚本会执行：

1. `git clone --depth 1 --branch <ref>`。
2. `python -m venv .venv`。
3. `.venv/bin/python -m pip install -e ".[dev]"`。
4. `scripts/mcp_client_acceptance.py`。
5. `ml-loop init-mcp-config --client codex`。
6. `ml-loop init-skills --client codex --dry-run`。
7. `scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30`。

成功时 JSON 顶层应为：

```json
{
  "status": "passed"
}
```

关键检查项：

- `mcp-client-acceptance.returncode == 0`
- `render-codex-config.returncode == 0`
- `skills-dry-run.returncode == 0`
- `mcp-golden-path.returncode == 0`

## 发布前要求

发布 `v0.1.0-preview` 前必须至少跑一次 fresh checkout 验证。若只是快速检查安装和 MCP contract，可加 `--skip-golden-path`，但正式 release 前不能跳过 golden path。

## 失败处理

- 安装失败：优先检查 `pyproject.toml` 依赖和 Python 版本。
- MCP client acceptance 失败：先调用 `get_service_manifest`，确认 `contract_version`、required tools 和 skill contracts。
- golden path 失败：检查 `ML_RESEARCH_LOOP_PYTHON`、runtime root 权限和训练日志。
