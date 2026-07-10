# Codex / Claude 调用 ML Research Loop 的示例 transcript

> 这是面向演示和用户教育的压缩 transcript，字段来自当前 MCP contract 和 deterministic demo。路径已泛化，真实运行时以本机 runtime root 为准。

## 1. 用户提出目标

```text
用户：基于 TinyStories/字节级语言建模方向，帮我找一个有研究依据的改动，跑一个小实验，并告诉我下一步该怎么改。
```

## 2. 客户端先读取 manifest

```text
Codex/Claude -> get_service_manifest
```

关键返回：

```json
{
  "service_name": "ml-research-loop",
  "product_status": "preview",
  "contract_version": "2026-07-10.preview.v1",
  "architecture": "hybrid_client_planner_server_executor",
  "client_model_role": "Codex/Claude acts as the planner",
  "mcp_server_role": "execute research lookup, bounded experiments, result review, artifact reads, and log summaries",
  "recommended_skills": [
    "ml-research-loop-planner",
    "ml-research-loop-reproduction",
    "ml-research-loop-experiment-optimizer",
    "ml-research-loop-operator"
  ]
}
```

客户端判断：

```text
contract_version 匹配，服务端 LLM 默认关闭。本轮由 Codex/Claude 负责 planner，MCP 负责执行。
```

## 3. 检索研究上下文

```text
Codex/Claude -> research_task
arguments:
  objective: minimize val_bpb on a local byte language modeling task
  query: byte transformer architecture ablation
  paper_limit: 1
  dataset_limit: 1
  github_limit: 1
  include_github_code: true
  cache_dir: <runtime-root>/research-cache
```

关键返回：

```json
{
  "status": "research_context_ready",
  "query_plan": [
    {"query": "byte transformer architecture ablation", "reason": "primary"}
  ],
  "provider_coverage_gate": {
    "met": true,
    "known_provider_ratio": 1.0
  },
  "evidence_quality": {
    "evidence_backed": true,
    "source_class_counts": {
      "paper_abstract": 1,
      "dataset_card": 1,
      "code_reference": 1
    }
  },
  "retrieval_diagnostics": {
    "recommended_recovery": []
  }
}
```

客户端判断：

```text
证据来自可识别 provider，citation trace 可用，可以进入 hypothesis 阶段。
```

## 4. 生成可实验验证的假设

```text
Codex/Claude -> propose_hypotheses
```

关键返回：

```json
{
  "hypotheses": [
    {
      "hypothesis_id": "hyp-001",
      "title": "Validate research-backed change for minimize val_bpb on a local byte language modeling task",
      "expected_metric": "val_bpb",
      "expected_direction": "minimize",
      "proposed_changes": [
        "modify one SEARCH REGION parameter before broader code edits"
      ]
    }
  ]
}
```

## 5. 跑 bounded 实验

```text
Codex/Claude -> run_hypothesis_experiment
arguments:
  task_config: <runtime-root>/tasks/mcp-real-data.json
  workspace: <runtime-root>/workdir/mcp-real-data
  runtime_root: <runtime-root>
  max_experiments: 1
  experiment_duration: 30
```

关键返回：

```json
{
  "status": "completed",
  "experiments": 1,
  "best_result": {
    "experiment_id": "exp-001",
    "val": 5.7,
    "params": {
      "batch_size": 1,
      "depth": 1,
      "dim": 16,
      "window_size": 64
    }
  }
}
```

## 6. 复盘结果并生成下一轮动作

```text
Codex/Claude -> review_research_results
arguments:
  task_id: mcp-real-data
  runtime_root: <runtime-root>
  workspace: <runtime-root>/workdir/mcp-real-data
```

关键返回：

```json
{
  "research_review": {
    "decision": "continue_from_best",
    "experiment_strategy": {
      "mode": "local_refinement",
      "recommended_max_experiments": 3
    }
  },
  "experiment_state": {
    "dataset_profile": {
      "exists": true,
      "risks": []
    },
    "experiment_tree": {
      "best_node_id": "exp-001"
    },
    "loop_policy": {
      "decision": "continue",
      "recommended_next_action": "run_next_refinement"
    },
    "code_change_plan": {
      "recommended_action": "tune_search_region",
      "target": "BATCH_SIZE",
      "next_experiment_plan": {
        "mode": "local_refinement",
        "proposed_task_patch": {
          "hyperparameter_space": {
            "batch_size": {
              "type": "choice",
              "values": [1, 2]
            }
          }
        }
      }
    },
    "planner_actions": [
      {
        "action_id": "run-next-experiment",
        "tool": "run_hypothesis_experiment",
        "requires_client_edit": false
      }
    ]
  }
}
```

客户端输出给用户：

```text
本轮实验完成，当前 best val_bpb 约为 5.7。数据文件存在，复现 readiness 未阻塞，实验树建议继续围绕 exp-001 做局部搜索。下一步优先验证 BATCH_SIZE 的小范围变化，可以直接调用 run_next_experiment_from_review 或让客户端生成一个受控 patch。
```

## 7. 下一轮可以自动继续

```text
Codex/Claude -> run_next_experiment_from_review
arguments:
  task_id: mcp-real-data
  runtime_root: <runtime-root>
  workspace: <runtime-root>/workdir/mcp-real-data
  include_final_review: true
```

这一步会消费 `code_change_plan.next_experiment_plan.proposed_task_patch`，并返回下一轮实验结果、final review 和 loop decision。
