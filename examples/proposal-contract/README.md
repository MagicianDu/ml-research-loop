# Proposal Contract Smoke Fixture

这个目录提供最小本地 fixture，用来验证 `context -> validate -> reflect` 闭环。

- 数据只表达本地诊断结果，不代表官方成绩。
- dev 上的收益必须由 canary 或 holdout 支撑后，才可视作 candidate。
- rejected proposal 故意混入多变量修改和官方榜单表述，用于验证 contract 会拒绝。
