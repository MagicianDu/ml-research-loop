# fastText/AG News 完整复现与迭代提升试用说明

本文档用于回答一个试用者最关心的问题：**我怎么确认系统真的复现了一篇论文的核心实验，并且通过后续迭代让效果有提升？**

当前项目选择的第一条完整复现轨道是：

| 字段 | 内容 |
| --- | --- |
| 论文 | Bag of Tricks for Efficient Text Classification |
| 论文 ID | `arxiv:1607.01759` |
| 核心实验 | fastText supervised text classification on AG News |
| 数据 | 完整 AG News CSV，train `120000`，test `7600` |
| runtime | 本机编译的 `facebookresearch/fastText` binary |
| 指标 | `P@1` / accuracy |
| 公开声明 | `official_scores_claimed=false` |

## 一句话结论

当前证据证明：项目已经在一条真实公开数据 + 真实 fastText runtime 的核心实验轨道上完成 baseline 复现，并通过一个受控客户端 proposal 得到小幅提升。

| 阶段 | 指标 |
| --- | ---: |
| baseline | `P@1=0.914` |
| patch：`-wordNgrams 2` | `P@1=0.916` |
| delta | `+0.002` |
| 多轮 proposal | `2` 个 |
| 失败轮次 | `1` 个非法参数被记录 |
| rollback event | `1` 次，策略为 `keep_best_so_far` |

这不是 official leaderboard score，也不是论文所有表格的完整复现。

## 用户应该看哪些文件

从仓库 checkout 直接看这三个入口：

1. 总索引：`docs/evidence/proof-release-index/proof-release-index.md`
2. fastText proof archive：`docs/evidence/proof-archives/fasttext-ag-news-full-reproduction-20260517/proof-archive.json`
3. 可下载 proof bundle：`docs/evidence/proof-archives/fasttext-ag-news-full-reproduction-20260517/artifacts/release-proof-bundle.tar.gz`

最短检查命令：

```bash
jq '.artifact_manifest.metric_summary' \
  docs/evidence/proof-archives/fasttext-ag-news-full-reproduction-20260517/proof-archive.json

jq '.artifact_manifest.multi_round_summary' \
  docs/evidence/proof-archives/fasttext-ag-news-full-reproduction-20260517/proof-archive.json

cd docs/evidence/proof-archives/fasttext-ag-news-full-reproduction-20260517/artifacts
shasum -a 256 -c release-proof-bundle.sha256
```

预期能看到：

```json
{
  "name": "accuracy",
  "baseline_p_at_1": 0.914,
  "p_at_1": 0.916,
  "delta": 0.002,
  "improved": true,
  "within_tolerance": true
}
```

以及：

```json
{
  "included": true,
  "status": "completed_with_failures",
  "proposal_count": 2,
  "completed_count": 1,
  "failure_count": 1,
  "improved_count": 1,
  "rollback_events": 1,
  "best_metric": 0.916
}
```

## 怎么判断“论文被复现”

看 `release-proof-bundle.tar.gz` 解压后的 P4 证据：

- `p4-proof/artifacts/baseline-report.json`
- `p4-proof/artifacts/dataset-provenance.json`
- `p4-proof/artifacts/fasttext-patch-train.log`
- `p4-proof/artifacts/fasttext-patch-test.log`
- `p4-proof/human-review-report.json`

其中 `baseline-report.json` 应证明：

- 论文 ID 是 `arxiv:1607.01759`；
- 数据规模是完整 AG News：train `120000`、test `7600`；
- 指标 `P@1=0.914`；
- 与当前目标 `0.924±0.02` 对齐；
- `official_scores_claimed=false`。

## 怎么判断“迭代后效果有提升”

看 `p4-proof/artifacts/improvement-report.json`：

- baseline `P@1=0.914`；
- proposal 是 fastText allowlist 内的 `-wordNgrams 2`；
- patch 后 `P@1=0.916`；
- `delta=0.002`；
- `improved=true`。

看 `p4-proof/artifacts/patch-diff.patch` 可以确认改动范围只是 fastText 训练参数，不是事后篡改结果。

## 怎么判断“失败和回滚被记录”

看解压后的：

- `p5-multi-round/multi-round-report.json`

其中应能看到：

- `proposal_count=2`
- `failure_count=1`
- 非 allowlist 参数 `bucket=100` 被记录为失败；
- `rollback_strategy=keep_best_so_far`
- 最佳结果仍保留为 `P@1=0.916`。

这说明系统不是只展示成功样例，也会保留失败轮次和回滚证据。

## 不能怎么宣传

当前可以说：

- 已完成一篇论文的核心实验轨道复现 proof；
- 完整 AG News 数据和 fastText runtime 的 baseline 可复查；
- 一个受控 proposal 带来小幅提升；
- proof bundle、checksum、review checklist 和失败/回滚记录可下载复核。

当前不能说：

- 取得官方 leaderboard 成绩；
- 完整复现了论文所有表格；
- 能自动保证任意论文复现成功；
- 能无人值守保证任意模型持续提升。

## 下一步试用建议

如果试用者要亲自复跑，应先准备：

- 完整 AG News `train.csv` / `test.csv`；
- 可执行 fastText binary；
- 足够的本机训练时间预算。

然后按 `docs/reproduction-pilot/full-reproduction-fasttext-target-cn.md` 中 P2+++、P3、P4、P5 命令顺序执行。复跑完成后，再用 `scripts/publish_release_evidence.py --fasttext-release-manifest ...` 生成新的公开 proof archive。
