# 单篇论文复现 Case 模板

本模板用于把一篇真实论文转成 ML Research Loop 可执行、可审计、可恢复的 ResearchCase。它适用于单篇论文 bounded claim 复现，不适用于直接声明完整 SOTA 或官方 benchmark 成绩。

## 1. 论文准入

| 字段 | 填写要求 |
| --- | --- |
| `paper_id` | arXiv ID、DOI 或公开论文 URL。 |
| `title` | 论文标题。 |
| `arxiv_url` | 如果是 arXiv 论文，填写 `https://arxiv.org/abs/...`。 |
| `task` | 一句话描述要复现的任务。 |
| `metric` | 指标名称和方向。 |
| `dataset_plan` | 公开数据、小切片或替代数据计划。 |
| `algorithm_plan` | 最小算法、ablation 或 patch 思路。 |
| `resource_budget_minutes` | 本机短时运行预算。 |
| `target_claim` | 一个 bounded claim，不写完整 SOTA 主张。 |
| `official_scores_claimed` | 必须默认为 `false`，对外文字写作 `official_scores_claimed=false`。 |

准入失败时也要保留报告，说明拒绝原因和下一步选择。

## 2. Claim Extraction

每个 claim 必须写清：

- claim 文本；
- claim 来源；
- 证据强度；
- 是否可以本机短时验证；
- 对应 metric；
- 不能外推的范围。

示例：

```json
{
  "claim_id": "claim-routing",
  "text": "Intent-aware routing improves relevant evidence selection on the bounded task.",
  "status": "needs_evidence",
  "metric_name": "accuracy",
  "official_scores_claimed": false
}
```

## 3. Evidence Refs

证据可以来自：

- 论文正文；
- 附录；
- 代码仓库；
- 数据卡；
- 本地运行 artifact；
- 人工审查报告。

每条 evidence ref 至少包含：

- `source_id`
- `artifact_path`
- `quote` 或摘要；
- `strength`

## 4. Metric And Dataset

必须写明：

- metric 名称；
- metric 方向；
- 数据来源；
- 是否是替代数据；
- 是否可以公开；
- 数据准备命令；
- 数据缺失时的 repair plan。

如果使用替代数据，所有输出必须包含：

```json
{
  "substitute_data": true,
  "official_scores_claimed": false
}
```

## 5. Environment Probe

实验前必须运行环境检查，至少覆盖：

- Python 版本；
- 必要命令；
- 必要文件；
- 写权限；
- 数据路径；
- secret-risk 文件名；
- repair plan。

环境 blocked 时，不运行实验。

## 6. Bounded Baseline

最小 baseline 必须满足：

- 单次运行在预算内；
- 输出 JSON metrics；
- 记录命令和日志；
- 失败时输出 failure diagnostics；
- 不写入未授权目录。

## 7. Client Handoff

每次实验后，要把以下信息交给 Codex/Claude：

- case summary；
- target claim；
- metric before；
- gap 或 failure；
- allowed patch scope；
- suggested next actions；
- stop rules。

客户端强模型负责提出下一步代码、配置或超参改动；MCP 负责执行和归档。

## 8. Guarded Patch

patch 必须满足：

- 范围受限；
- 可预检；
- 可回滚或有 failure diagnostics；
- patch 前后 artifact 都保留；
- 不把指标提升外推为官方成绩。

## 9. Proof Archive

完成后生成 proof manifest：

```json
{
  "case_id": "case-id",
  "paper_id": "arxiv:xxxx.xxxxx",
  "claim": "bounded claim",
  "claim_strength": "local_substitute_data",
  "official_scores_claimed": false,
  "artifacts": [],
  "limitations": []
}
```

每个 artifact 必须有路径和 hash。

## 10. Claim Boundary

对外材料必须区分：

- `local proof`
- `debug fixture`
- `local_substitute_data`
- `official harness probe`
- `official benchmark run`
- `human-reviewed case`

缺少官方 harness 时，不得宣传官方成绩。

## 11. Stop / Continue Rules

停止条件包括：

- 目标 bounded claim 已有足够本地证据；
- 指标多轮无提升；
- 环境或数据 blocked；
- 预算耗尽；
- patch 风险超过允许范围；
- 证据不足，继续实验无法提升可信度。

继续条件包括：

- metric 有可解释改进空间；
- failure diagnostics 指向明确修复；
- patch 范围小且可回滚；
- 用户或客户端强模型明确选择继续。

## 12. Standard CLI Flow

把 `<paper-id>`、`<output-dir>`、`<proof-dir>` 和数据参数替换为下一篇论文对应值。以下流程是标准作业顺序：

```bash
python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id <paper-id> \
  --output-dir <output-dir> \
  --select-only \
  --json

python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id <paper-id> \
  --output-dir <output-dir> \
  --probe-only \
  --json

python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id <paper-id> \
  --output-dir <output-dir> \
  --run-baseline \
  --json

python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id <paper-id> \
  --output-dir <output-dir> \
  --run-iteration \
  --json

python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id <paper-id> \
  --output-dir <output-dir> \
  --write-review-report \
  --reviewer <reviewer-name> \
  --review-decision approved_with_limitations \
  --json

python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id <paper-id> \
  --output-dir <output-dir> \
  --archive-proof \
  --proof-dir <proof-dir> \
  --update-evidence-index \
  --json
```

如果使用 fixture 或替代数据，必须显式加上 `--use-fixture-data`，并在 proof manifest、evidence index 和 public claims map 中保留 `local_substitute_data` 与 `official_scores_claimed=false`。

如果使用项目内置的公开小切片，必须显式加上 `--use-public-mini-slice`。该路径会写入 `dataset-provenance.json`，claim strength 应为 `local_public_data`，但仍然只代表本地公开小样本证明，不代表官方 benchmark、完整复现或 SOTA。

在 `--archive-proof` 前必须先写 `human-review-report.json`。只有 `review_status=approved_with_limitations` 的 proof 才能在 public claims map 中把 bounded public-slice claim 标记为 `allowed_with_boundary`；其他复核状态必须阻断公开声明。
