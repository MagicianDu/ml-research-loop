# 硕博 2 小时论文复现 Mini Lab

这个 pilot 用受限 reproduction smoke 或 paper-guided byte-LM 模板练习把论文 claim 转成可执行任务。目标是建立证据、日志和失败复盘，不是完整复现整篇论文。

## 适合对象

- 硕士、博士、论文研讨班成员。
- 需要评估 agentic research workflow 的科研工程师。
- 实验室 onboarding 中负责复现基线的同学。

## 运行命令

本地 reproduction smoke：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_reproduction_demo.py --max-experiments 1 --experiment-duration 30 --json
```

paper-guided 初始化路径：

```bash
ml-loop demo init --template paper-guided-byte-lm --runtime-root .demo_runs/pilot/reproduction-mini
```

## 预期输出

- reproduction spec、task artifact 或 paper-guided demo task。
- 至少一次本地受限实验结果、日志和 review artifact。
- 对 claim boundary 的明确记录：本地 mini lab 只证明流程可运行，不证明论文完整复现成功。

## 常见失败

- 公开论文或数据入口缺失：先换成公开、可下载、可引用的最小 claim。
- `PYTHONPATH` 中 Python 版本目录不存在：改成当前 `.venv/lib/python*/site-packages` 路径，或直接在已安装环境中运行。
- 实验超时：降低 `--experiment-duration` 或只初始化任务让 MCP client 审查。
- 证据不足：记录缺失的论文段落、数据卡、代码入口或 metric 定义，不要补写未经验证的 claim。

## 应提交的反馈文件

- 使用的论文链接、公开数据入口和目标 claim 摘要。
- reproduction demo 终端输出。
- `.demo_runs/pilot/reproduction-mini` 或默认 reproduction demo runtime 下的 `task.json`、`result.json`、日志和 review artifact。
- 已脱敏的 feedback bundle 路径；如果没有生成 bundle，请提交可共享日志片段和失败命令。
