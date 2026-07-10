# MLE-bench Official-Debug Bridge Smoke Result: Spooky Author Identification

日期：2026-05-07
更正日期：2026-07-02

## 更正说明

本文早期版本声称本地跑出了一次真实的 log loss 改善（`1.08468` → `0.45383` → `0.37038`，
TF-IDF + calibrated SGD / word+char TF-IDF + logistic regression，超过 median
threshold）。经复核，仓库里没有任何代码路径能产生这些数字：

- 唯一对应这个 feature 的可执行脚本 `scripts/mle_bench_official_bridge_demo.py`
  自称是 `deterministic ... smoke test`，它用的 `mlebench` 可执行文件是一段写死的
  fake scorer（[`_write_fake_mlebench`](../../scripts/mle_bench_official_bridge_demo.py)），
  无论提交什么内容都固定打印 `score: 1.08468`。
- 该脚本里的 "patch" 只是把 `solve.py` 里一行 `print` 语句从
  `wrote {submission}` 改成 `wrote patched {submission}`，不包含任何 TF-IDF
  或 logistic regression 逻辑；仓库里也没有为 MLE-bench 写过这样的 solver。
- 数据同样是脚本内写死的 1 行 fixture（`train.csv` 只有一行 `1,hello,EAP`），
  不是「官方 prepare + Kaggle 数据」。
- 原文引用的 `.demo_runs/hard-results/mle-spooky-20260507-1735/...` 证据路径
  在本机磁盘上不存在，也从未提交到仓库。

2026-07-02 重新实际执行了这个脚本（见下方"可复现结果"），确认 baseline 和 patch
round 的 score 完全相同（`1.08468` = `1.08468`），`above_median` 实际是 `false`，
而不是原文声称的 `true`。原结论已撤回。

## 这个 bridge 实际证明了什么

它证明的是**产品闭环插件本身能跑通**，而不是任何模型分数：

1. MCP/CLI 能从 prepared-data fixture 创建 agent-editable workspace。
2. 客户端可以提交一个 bounded diff 作为 patch。
3. 服务端负责 patch preflight、执行、调用 `mlebench_executable`（可指向真实或
   fake 的 `mlebench` 二进制）评分、写日志和报告。
4. 评分反馈能驱动下一轮 patch round。
5. 最终结果能进入 publication guard 和 hash archive。

`grade_official_mle_submission`（[`lib/benchmarks/official_mle_bridge.py`](../../lib/benchmarks/official_mle_bridge.py)）
确实支持传入真实的官方 `mlebench` 可执行文件，所以这条链路具备跑真实评测的能力；
但**这个具体的 smoke demo 从未这样用过**，之前的结论把「smoke test 用 fake
grader 跑通了插件」误写成了「模型真的把 log loss 从 1.08 降到 0.37」。

## 可复现结果（2026-07-02 重新执行）

在仓库根目录运行：

```bash
PYTHONPATH=. python3 scripts/mle_bench_official_bridge_demo.py \
  --runtime-root .demo_runs/mle-bridge-smoke --json
```

得到（字段来自脚本当次真实输出，任何人都可以重新跑一遍验证）：

- `status`: `passed`（表示插件闭环跑通，不代表模型效果）
- `baseline_round.grade.report.score`: `1.08468`
- `patch_round.round.grade.report.score`: `1.08468`（与 baseline **完全相同**，
  因为 fake grader 不读提交内容）
- `patch_round.round.grade.report.above_median`: `false`
- `patch_proof.archive.bundle.status`: `archivable`
- `official_scores_claimed`: `false`（全程一致，这一点是真的）
- `patch_proof.manifest_path` 指向的 `manifest.json` 里 `run_mode` 字段固定为
  `official_debug_patch_round`（[`lib/benchmarks/mle_patch_proof.py:157`](../../lib/benchmarks/mle_patch_proof.py)
  写死的真实 code constant），标记这次调用走的是 official-debug + patch-round
  合约路径——这个标签本身是准确的，只是路径里跑的数据和 scorer 都是 fake 的。

## 不能声明的内容

- 这不是任何真实模型的 log loss 结果。
- 这不是官方 leaderboard 成绩。
- 这不是完整 MLE-bench agent run-group / Docker / 多任务评测。
- 这不是 medal 级或 above-median 结果。
- 对外传播时必须保留 `official_scores_claimed=false`。

## 下一步

1. 如果要宣传一个真实 MLE-bench 分数，需要先写一个真正的 solver（例如 TF-IDF +
   sklearn），接官方 `mlebench` CLI 和官方 prepared Kaggle 数据跑一遍，并把
   baseline/patch 的 `grade-report.json`、日志、proof archive 提交进仓库
   （而不是只留在 gitignore 掉的 `.demo_runs/` 里）才能构成可复核证据。
2. 补一次 PaperBench official debug dummy run；当前主要卡点是 Git LFS 数据 hydration。
3. 准备真实 grader key 后再跑 PaperBench real judge path。
4. 在更长任务上验证多轮 patch/grade loop 的稳定性。
