# 真实论文复现演示

这份文档用于展示 ML Research Loop 如何把 ml-intern 的论文读取能力和 autoresearch 的本地实验闭环合在一起，形成一个可由 Codex/Claude 推进的复现骨架。

## 演示目标

从一个论文标识符开始，读取论文证据，生成 hypothesis，跑一个固定预算实验，再用复现 readiness、grade report 和 experiment state 判断下一步。

## 推荐命令

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_reproduction_demo.py --max-experiments 1 --experiment-duration 30 --json
```

## 客户端调用顺序

```text
read_paper
  -> propose_hypotheses
  -> run_hypothesis_experiment
  -> review_research_results
  -> inspect experiment_state.reproduction.readiness
  -> inspect grade_report
  -> decide next client patch or run_next_experiment_from_review
```

## 验收字段

成功演示至少应返回：

- `status == completed`
- `reproduction.readiness.status == ready`
- `grade_report.score > 0`
- `experiment_state.dataset_profile.exists == true`
- `experiment_state.metric_stop_policy.decision in {"continue", "stop"}`
- `experiment_state.failure_diagnostics.failed_count == 0`

## 讲解重点

- `read_paper` 提供论文证据入口，不要求服务端大模型参与。
- Codex/Claude 根据 evidence snippets 和 hypotheses 决定实验方向。
- MCP 服务执行 bounded experiment，并把日志、结果、工作区和复现状态回传。
- 若要继续自动优化，客户端应优先读取 `metric_stop_policy` 和 `code_change_plan.next_experiment_plan`，再选择 `run_next_experiment_from_review` 或 `apply_client_code_patch`。

## 边界

当前 preview 版提供的是轻量复现骨架，不等价于完整 PaperBench 级别的 GPU sandbox 或长时评测。对于正式论文复现，建议把数据下载、训练命令、评测脚本和 required files 写入 task config 的 `reproduction_spec`，再通过 MCP 工具逐步验收。
