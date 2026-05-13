# fastText AG News 真实本地 baseline 证据

日期：2026-05-13

## 结论

本次运行用完整 AG News CSV 和本机编译的官方 fastText binary 跑通了 `Bag of Tricks for Efficient Text Classification` 的核心 supervised text classification baseline。

结果为：

- 测试样本数：`7600`
- `P@1` / accuracy：`0.914`
- 当前目标值：`0.924`
- tolerance：`0.02`
- 是否落入 tolerance：是
- `official_scores_claimed`：`false`

这说明项目已经具备“接入完整公开数据、调用真实训练 runtime、归档日志、解析指标、对齐论文目标值”的本地复现执行链路。它仍不是官方 leaderboard 成绩，也不是完整复现论文所有表格。

## 运行命令

```bash
.venv/bin/python scripts/full_reproduction_run.py \
  --target-spec docs/reproduction-pilot/full-reproduction-target.json \
  --output-dir .demo_runs/p2ppp-fasttext-real-baseline \
  --run-fasttext-baseline \
  --ag-news-train-csv .demo_runs/p2ppp-ag-news-current/train.csv \
  --ag-news-test-csv .demo_runs/p2ppp-ag-news-current/test.csv \
  --fasttext-binary .external/fastText/fasttext \
  --max-train-seconds 900 \
  --json
```

## 数据

数据来源：

- train：`https://raw.githubusercontent.com/mhjabreel/CharCnn_Keras/master/data/ag_news_csv/train.csv`
- test：`https://raw.githubusercontent.com/mhjabreel/CharCnn_Keras/master/data/ag_news_csv/test.csv`

行数校验：

- train：`120000`
- test：`7600`

下载文件 SHA-256：

- train：`76a0a2d2f92b286371fe4d4044640910a04a803fdd2538e0f3f29a5c6f6b672e`
- test：`521465c2428ed7f02f8d6db6ffdd4b5447c1c701962353eb2c40d548c3c85699`

`dataset-provenance.json` 记录的 MD5：

- train：`b1a00f826fdfbd249f79597b59e1dc12`
- test：`d52ea96a97a2d943681189a97654912d`

## Runtime

- binary：`.external/fastText/fasttext`
- 源码：`facebookresearch/fastText`
- 本地源码 commit：`1142dc4`
- binary probe：`official_binary_available`
- baseline 训练参数：`-thread 1 -seed 0`

`.external/` 是本机外部依赖缓存，不纳入 git。复验时可以重新 clone/build fastText，或显式传入另一个兼容 binary。

## 关键 artifacts

输出目录：`.demo_runs/p2ppp-fasttext-real-baseline`

- `dataset-provenance.json`
- `fasttext-runtime-probe.json`
- `logs/fasttext-train.log`
- `logs/fasttext-test.log`
- `fasttext-baseline-report.json`
- `client-handoff.json`
- `model.bin`
- `model.vec`

`logs/fasttext-test.log` 中记录：

```text
N	7600
P@1	0.914
R@1	0.914
```

## 声明边界

可以说：

- 项目已经完成一个真实本地 fastText/AG News baseline proof。
- 项目可以把完整公开数据、真实训练 runtime、指标解析、日志归档和 client handoff 串成闭环。
- 该 baseline 与当前 fastText AG News target 在本地 tolerance 内对齐。

不能说：

- 这是官方 leaderboard 成绩。
- 已经完整复现论文所有实验。
- 已经证明任意论文都能自动复现。
- 已经完成 Codex/Claude 驱动的自动改进闭环。

下一步应进入 P3：在该可信 baseline 上接入 client patch / hyperparameter proposal loop，记录每轮 diff、配置、指标、回滚和人工复核。
