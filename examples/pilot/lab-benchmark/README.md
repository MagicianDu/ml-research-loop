# 实验室 1 天 Benchmark Trial

这个 pilot 面向 PI、科研工程师和平台负责人，用一天时间评估本地 proof-run 准备、benchmark readiness、setup bundle 和 claim boundary。它不提交官方排行榜，也不声称官方 benchmark 成绩。

## 适合对象

- 需要评估 ML Research Loop 是否适合组内 proof workflow 的实验室。
- 负责 MLE-bench / PaperBench shaped flow 的科研工程师。
- 关注审计、归档、hash、失败复盘和安全边界的平台负责人。

## 运行命令

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
ml-loop check --json
ml-loop benchmark readiness --json
ml-loop benchmark probe --json
ml-loop benchmark proof-plan --json
ml-loop benchmark setup-bundle --output-dir .demo_runs/pilot/lab-benchmark/proof-setup --json
```

可选本地 compatibility smoke：

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
ml-loop benchmark smoke --runtime-root .demo_runs/pilot/lab-benchmark/smoke --json
```

## 预期输出

- `ml-loop check --json` 的 release gate 输出。
- benchmark readiness、probe、proof-plan JSON。
- `.demo_runs/pilot/lab-benchmark/proof-setup` 下的外部 proof-run 准备包。
- 本地 compatibility smoke artifact 或明确 blocked reason。
- 所有公开描述保留 `official_scores_claimed=false` 边界。

## 常见失败

- 官方 harness 不存在：这是允许的 blocked state，提交 probe 输出即可。
- Docker、GPU、API key 或数据权限不足：不要绕过机构审批；记录缺口和 repair plan。
- `ml-loop check --json` 时间过长：先记录失败阶段，再运行更窄的 readiness/probe 命令。
- publication/archive 被阻塞：检查 manifest 是否缺少命令、配置、环境、日志、报告或限制说明。

## 应提交的反馈文件

- `ml-loop check --json` 输出或失败日志。
- `readiness`、`probe`、`proof-plan` JSON。
- `.demo_runs/pilot/lab-benchmark/proof-setup` 的脱敏文件清单。
- 本地 smoke 的 `result.json`、日志和 artifact index。
- 已脱敏的 feedback bundle 路径；不要提交 token、私有数据路径或未公开 benchmark 数据。
