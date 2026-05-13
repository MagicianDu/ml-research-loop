# Adam 单篇真实论文复现试点

本文档记录 `Adam: A Method for Stochastic Optimization`（arXiv:1412.6980）作为第二个单篇真实论文复现试点。它不是完整复现 Adam 论文，也不是优化器 benchmark 成绩；它只验证一个 bounded claim：在本地公开小切片的凸优化任务上，Adam 风格的一阶/二阶矩自适应更新相比固定步长 SGD 能提升受限进展指标。

## 试点边界

| 项目 | 内容 |
| --- | --- |
| 论文 | Adam: A Method for Stochastic Optimization |
| 论文 ID | `arxiv:1412.6980` |
| 公开来源 | `https://arxiv.org/abs/1412.6980` |
| 任务 | bounded optimizer convergence ablation |
| 指标 | `optimizer_progress_score`，越高越好 |
| 当前数据 | curated public mini-slice，来自公开算法描述抽象出的 4 个一维凸二次优化任务 |
| 当前 claim | adaptive moment estimates improve local optimizer progress on the bounded task |
| 禁止 claim | 完整复现 Adam、官方 benchmark/SOTA、泛化到真实深度学习训练任务 |

## 当前证据

已归档 proof：

- `proof_runs/real-paper-pilot/adam/proof-manifest.json`
- `proof_runs/real-paper-pilot/adam/artifacts/dataset-provenance.json`
- `proof_runs/real-paper-pilot/adam/artifacts/human-review-report.json`

本地 public mini-slice 结果：

| 指标 | baseline | Adam-style ablation | delta |
| --- | ---: | ---: | ---: |
| `optimizer_progress_score` | `0.422823` | `0.881488` | `0.458665` |

该结果只说明系统可以把第二类论文 claim 转成可审计的 bounded pilot：选题、环境 probe、baseline、受限迭代、人工复核、proof archive 和公开声明边界。它不能说明项目已经具备任意优化器论文复现能力。

## 标准命令

```bash
python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id arxiv:1412.6980 \
  --output-dir .demo_runs/real-paper-adam \
  --run-baseline \
  --use-public-mini-slice \
  --json

python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id arxiv:1412.6980 \
  --output-dir .demo_runs/real-paper-adam \
  --run-iteration \
  --use-public-mini-slice \
  --json

python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id arxiv:1412.6980 \
  --output-dir .demo_runs/real-paper-adam \
  --write-review-report \
  --reviewer local-operator \
  --review-decision approved_with_limitations \
  --json

python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id arxiv:1412.6980 \
  --output-dir .demo_runs/real-paper-adam \
  --archive-proof \
  --proof-dir proof_runs/real-paper-pilot/adam \
  --evidence-dir docs/evidence \
  --update-evidence-index \
  --json
```

## 下一步

1. 把 optimizer mini-slice 扩展到更多公开目标函数和随机梯度扰动设置。
2. 增加失败样例，例如 Adam 不优于 SGD 的任务，验证 review 和 stop rules 是否能阻断过度宣传。
3. 对接官方或社区优化器 benchmark 前，只能保留 `official_scores_claimed=false`。
