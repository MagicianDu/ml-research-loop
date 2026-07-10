# ArGuard B1 P0 Live Verification

本目录记录 `arguard-b1-binary-classification` 的只读 P0 验证结果。

## 结论

- Codabench competition 页面可访问。
- ArGuard public repository README 可访问。
- Task B README 可访问，并确认 B1 是 `safe` / `unsafe` 二分类。
- 公开说明中的 primary metric 是 `macro-F1`。
- 预期 B1 输出格式是 TSV，header 为 `id`, `label`, `run_id`。
- 当前状态是 `verified_with_asset_blockers`。
- hard blocker: `released_train_dev_scorer_not_confirmed`。
- `official_scores_claimed=false`，未提交 Codabench，未宣称榜单成绩。

## 下一步

先确认 released train/dev/scorer/format checker 是否已经可获取。只有确认这些资产后，才进入本地 baseline 和 3-5 轮 optimizer/gate 搜索。

## 复跑命令

```bash
PYTHONPATH=. python scripts/cli.py hf-eval arguard-b1-verify \
  --output-dir docs/hf-evaluation/arguard-b1-p0-live-verification \
  --timeout-seconds 20 \
  --no-raw \
  --json
```
