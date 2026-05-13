# 本科 30 分钟 Byte-LM Pilot

这个 pilot 用本地 byte-LM smoke demo 演示一次最小科研实验闭环。它适合课堂和助教演示，不需要 GPU、外部 API 或论文数据。

## 适合对象

- 本科高年级机器学习、软件工程、AI 工具课程学生。
- 第一次试用 Codex / Claude + ML Research Loop 的教学助教。

## 运行命令

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python3 scripts/mcp_client_acceptance.py --python "$(which python3)"
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
ml-loop demo run --template byte-lm-smoke --runtime-root .demo_runs/pilot/student-byte-lm --json
```

## 预期输出

- 终端 JSON 包含 `status`、`task_id`、`best_metric`、`task_file`、`result_file`。
- `.demo_runs/pilot/student-byte-lm` 下包含任务、结果、日志和本地 workspace。
- 结论只能表述为本地教学 smoke 通过或失败，不能表述为模型能力 benchmark。

## 常见失败

- `ml-loop` 找不到：确认已激活 `.venv` 并执行 `pip install -e ".[dev]"`。
- MCP acceptance 失败：记录 OS、Python version、命令输出和 client 类型。
- demo 写入失败：确认 `.demo_runs/pilot/student-byte-lm` 可写，且没有被其他进程占用。
- Python 版本不匹配：优先使用 README 支持的 Python 3.10 或 3.13。

## 应提交的反馈文件

- `scripts/mcp_client_acceptance.py` 的终端输出。
- `.demo_runs/pilot/student-byte-lm/result.json`。
- `.demo_runs/pilot/student-byte-lm` 下相关日志文件。
- 已脱敏的 feedback bundle 路径：

```bash
ml-loop feedback-bundle \
  --runtime-root .demo_runs/pilot/student-byte-lm \
  --task-id demo-byte-lm-smoke \
  --output-dir .demo_runs/pilot/student-byte-lm-feedback
```
