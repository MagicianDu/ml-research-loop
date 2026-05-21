# Proposal Contract Smoke Fixture

这个目录提供最小本地 fixture，用来验证 `context -> validate -> reflect` 闭环。

- 数据只表达本地诊断结果，不代表官方成绩。
- dev 上的收益必须由 canary 或 holdout 支撑后，才可视作 candidate。
- rejected proposal 故意混入多变量修改和官方榜单表述，用于验证 contract 会拒绝。

真实诊断样例见 `smol-qwen3/`：它复用 Smol WorldCup/Qwen3-8B 本地评测、
dev/canary 迭代和 formal rescore archive 摘要，可直接作为
`ml-loop proposal context` 的小型输入目录。该样例仍只表达 local diagnostic，
不声明 Hugging Face 官方成绩。
