# 机构 Pilot 和教学试用指南

本指南面向高校课程、研究生读书班和科研实验室试用 ML Research Loop。当前项目仍处于 preview 到 beta 的产品化阶段：它可以作为 Codex / Claude 的本地科研执行层，生成可复查的任务、日志、实验结果和 proof artifacts；但不能宣称任意论文无人值守复现、不能宣称官方 benchmark 成绩，也不能替代机构内部的数据安全审查。

## 适用边界

推荐试用对象：

- 本科高年级课程：理解 LLM planner 如何驱动受限 ML 实验。
- 硕博和科研工程师：练习把论文主张拆成可执行复现任务。
- PI / 实验室负责人：评估本地执行层、证据归档和失败反馈流程是否适合组内试用。

暂不推荐的用途：

- 直接处理含隐私、商业机密、未脱敏临床/教育/企业数据的任务。
- 把本地 demo 指标作为论文、基金或官方排行榜结果引用。
- 在无人审查的情况下自动修改真实研究仓库并长期运行。

## 试用前准备和预期输入/输出 Artifact

输入 artifact：

- 一台可安装 Python 3.10 或 3.13 的本地机器。
- 已 clone 的 `ml-research-loop` 仓库。
- Codex、Claude Code 或 Claude Desktop 中任一 MCP 客户端。
- 如需论文复现 mini lab，准备一篇公开论文、公开数据入口和可共享的目标 claim。
- 如需实验室 benchmark trial，准备一个脱敏后的本地任务目录或使用仓库内 fixture。

基础安装：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python3 scripts/mcp_client_acceptance.py --python "$(which python3)"
```

预期输出 artifact：

- MCP client acceptance 日志。
- `.demo_runs/.../task.json`、`result.json`、训练日志和 review artifact。
- 失败时的 redacted feedback bundle。
- 试用记录：场景、命令、耗时、是否通过、失败原因、后续建议。

## 30 分钟本科实验

目标：让学生在不需要 GPU、论文全文或外部 API 的情况下，观察一次受限 byte-LM 实验如何被创建、运行、记录和反馈。

适合对象：

- 机器学习、软件工程或 AI 工具课程中的本科高年级学生。
- 第一次接触 MCP / agentic workflow 的教学助教。

建议流程：

1. 5 分钟：解释 Codex / Claude 是 planner，ML Research Loop 是本地执行层。
2. 5 分钟：完成环境检查和 MCP client acceptance。
3. 10 分钟：运行 byte-LM smoke demo。
4. 5 分钟：查看 `best_metric`、`result_file`、`task_file` 和日志。
5. 5 分钟：生成或填写反馈。

运行命令：

```bash
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
ml-loop demo run --template byte-lm-smoke --runtime-root .demo_runs/pilot/student-byte-lm --json
```

预期输出：

- JSON 中包含 `status`、`task_id`、`best_metric`、`task_file`、`result_file`。
- `.demo_runs/pilot/student-byte-lm` 下保留可复查 artifact。
- 若失败，应能定位到 Python 环境、安装依赖或路径权限问题。

## 2 小时硕博论文复现 Mini Lab

目标：把一篇公开论文中的一个小 claim 拆成 evidence、reproduction spec、受限实验和失败复盘，而不是追求完整复现整篇论文。

适合对象：

- 研究生课程、论文研讨班、实验室新成员 onboarding。
- 希望评估 agentic research loop 能否帮助拆解复现任务的科研工程师。

建议流程：

1. 20 分钟：选择一个公开论文 claim，记录论文链接、数据入口和目标 metric。
2. 20 分钟：用 MCP client 生成 research/reproduction 任务，人工审查 claim boundary。
3. 40 分钟：运行本地 reproduction smoke 或 paper-guided byte-LM 模板。
4. 20 分钟：检查日志、result、rubric 或 review artifact。
5. 20 分钟：填写失败反馈，标明哪些证据不足、哪些依赖阻塞。

本地 smoke 命令：

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_reproduction_demo.py --max-experiments 1 --experiment-duration 30 --json
```

或先初始化 paper-guided 模板，让 Codex / Claude 通过 MCP 检查任务：

```bash
ml-loop demo init --template paper-guided-byte-lm --runtime-root .demo_runs/pilot/reproduction-mini
```

预期输出：

- reproduction spec 或 task artifact。
- 至少一次受限实验结果和日志。
- 明确的 claim boundary：本地 smoke / debug proof，不是论文完整复现，也不是官方 benchmark。

## 1 天实验室 Benchmark Trial

目标：让实验室负责人或科研工程师评估 ML Research Loop 是否能纳入组内 proof-run 流程，包括环境 probe、benchmark readiness、setup bundle、publication guard 和 archive。

适合对象：

- PI、实验室负责人、平台工程师、科研工程师。
- 需要评估 MLE-bench / PaperBench shaped workflow 的机构用户。

建议流程：

1. 1 小时：完成 clean checkout、依赖安装和 `ml-loop check --json`。
2. 1 小时：运行 benchmark readiness / probe / proof-plan。
3. 2 小时：生成 setup bundle，人工评估是否能进入外部官方环境。
4. 2 小时：使用本地 fixture 或已批准的脱敏 artifact 运行 compatibility smoke。
5. 1 小时：生成 publication / archive artifact，检查 hash 和 claim boundary。
6. 1 小时：整理失败日志、反馈 bundle 和访谈问题。

核心命令：

```bash
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

预期输出：

- readiness / probe / proof-plan JSON。
- proof setup bundle。
- 本地 smoke artifact 或阻塞原因。
- `official_scores_claimed=false` 的 proof/archive 记录。

## 数据安全注意事项

- 默认只使用公开数据、合成数据或教学 fixture。
- 不要把 token、私有数据路径、学生个人信息、企业项目名或未公开论文附件贴到 issue。
- 运行反馈 bundle 前先人工检查输出目录；如包含敏感路径或日志，先脱敏再提交。
- 不要把 `ML_RESEARCH_LOOP_ALLOWED_ROOTS` 指到包含隐私数据或密钥的上级目录。
- 机构内部试用应先在隔离目录、临时机器或受控账户中运行。
- 如果要处理真实研究数据，先完成 IRB / 数据使用协议 / 机构安全审批；本项目文档不能替代这些流程。

## 失败反馈模板

提交 GitHub pilot feedback issue 时，建议按以下结构填写：

```text
用户角色：
客户端：Codex / Claude Code / Claude Desktop
OS：
Python version：
demo command：
失败阶段：install / MCP acceptance / demo run / benchmark probe / publication/archive
failure log：
redacted feedback bundle path：
是否愿意访谈：
补充说明：哪些文档不清楚、哪些 artifact 缺失、是否有安全顾虑
```

生成反馈 bundle 示例：

```bash
ml-loop feedback-bundle \
  --runtime-root .demo_runs/pilot/student-byte-lm \
  --task-id demo-byte-lm-smoke \
  --output-dir .demo_runs/pilot-feedback-bundle
```

提交前请确认 bundle 已脱敏，并在 issue 中只填写可共享路径或压缩包名称。

## Pilot 验收口径

一次 pilot 可以记为通过，当且仅当：

- 参与者能从文档找到适合自己的试用场景。
- 至少一个本地 demo 或 readiness/probe 流程生成了可复查 artifact。
- 失败时能产出足够定位问题的日志或 feedback bundle。
- 反馈中保留 preview/beta/stable 边界，没有把本地 proof 说成官方 benchmark 成绩。

这不是 stable 认证。进入 stable 前仍需要更多外部用户反馈、长期运行证据、环境兼容性证据和 release gate 记录。
