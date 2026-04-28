# ML Research Loop — 工作目录说明

## 目录结构

```
ml-research-loop/
├── base/               # 原始代码，AI 不可修改
│   ├── train_base.py   # train.py 模板起点
│   └── prepare.py      # 数据准备脚本
│
├── scripts/            # 可执行脚本
│   ├── autoresearch_run.py    # 主入口
│   ├── generate_program_md.py # program.md 动态生成
│   └── sample_hyperparams.py  # 超参采样
│
├── ml_intern/          # ml-intern 集成
│   ├── autoresearch_manager.py
│   └── tools/
│       └── run_autoresearch.py
│
├── lib/                # 共享库
│   ├── task_protocol.py
│   ├── experiment_store.py
│   ├── progress_reporter.py
│   ├── metrics.py
│   └── exceptions.py
│
├── tasks/              # 任务定义（运行时写入）
├── results/            # 实验结果（运行时生成）
├── snapshots/          # 代码快照（每次实验后存档）
└── workdir/           # 工作目录（per-task）
```

## 运行时文件

以下目录在首次运行时自动创建，包含运行时生成的文件：

- `tasks/*.json` — 任务定义
- `results/*.json` — 实验结果
- `results/*-progress.json` — 实时进度
- `snapshots/<task_id>/<experiment_id>/` — 代码快照
- `workdir/<task_id>/train.py` — 当前可修改的 train.py
- `workdir/<task_id>/program.md` — 当前 program.md
- `workdir/<task_id>/experiments.json` — 实验记录

默认情况下，运行时根目录会解析为当前源码目录。也可以通过环境变量覆盖：

```bash
export ML_RESEARCH_LOOP_ROOT=/path/to/ml-research-loop-runtime
```

训练子进程默认优先使用可执行的 `.venv/bin/python3`，否则回退到当前 Python。也可以显式指定：

```bash
export ML_RESEARCH_LOOP_PYTHON=$(which python3)
```

## AI 可修改区域

train.py 中只有以下区域 AI 可以修改：

```
# ======= AUTORESEARCH SEARCH REGION START =======
LR = 0.001
BATCH_SIZE = 32
DEPTH = 4
# ... 其他超参数
# ======= AUTORESEARCH SEARCH REGION END =======
```

其他区域为固定代码，AI 不可修改。
