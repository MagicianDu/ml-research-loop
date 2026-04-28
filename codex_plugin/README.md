# ML Research Loop — Codex 插件

> 让任何 Codex 用户用自然语言驱动 ML 实验循环

## 功能

ML Research Loop Codex 插件提供三个工具：

1. **run_ml_experiment** — 启动 ML 实验循环
2. **get_ml_experiment_status** — 查询实验进度
3. **get_ml_experiment_results** — 获取实验结果

## 使用示例

### 启动实验

```python
adapter.run_ml_experiment({
    "task_id": "mnist-optimize-001",
    "objective": "minimize val_bpb on MNIST",
    "metric": "val_bpb",
    "max_experiments": 50,
    "experiment_duration_seconds": 300,
    "hyperparameter_space": {
        "lr": {"type": "log_uniform", "min": 1e-5, "max": 1e-2},
        "depth": {"type": "choice", "values": [4, 6, 8, 10]}
    }
})
```

### 查询状态

```python
adapter.get_ml_experiment_status("mnist-optimize-001")
# 返回: {"status": "running", "experiment_index": 23, "max_experiments": 50, "best_val": 0.342, ...}
```

### 获取结果

```python
adapter.get_ml_experiment_results("mnist-optimize-001")
# 返回: {"best_val": 0.301, "best_params": {"lr": 0.0032, "depth": 10}, ...}
```

## 与 Codex 集成

Codex 插件通过 plugin.json manifest 注册。
Codex 会将 run_ml_experiment 等工具暴露给 LLM，
用户可以用自然语言调用：

```
"帮我把 MNIST 模型的 val_bpb 降到 0.8 以下"
```

## 技术架构

- 复用 ml-research-loop 的所有已有组件
- codex_adapter.py 是"薄封装层"
- 零修改复用 autoresearch_run.py 逻辑
