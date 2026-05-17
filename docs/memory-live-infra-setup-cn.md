# Graphiti/cognee 可选记忆基础设施本地安装与验收

本文记录本项目的可选 Research Memory Layer 基础设施安装方式。Graphiti/cognee 不是 fresh checkout 的默认依赖；默认路径仍是本地 JSONL memory store。只有在显式安装和显式传参时，MCP/CLI 才会访问外部记忆服务。Graphiti/cognee live smoke 只作为 optional integration evidence，不进入默认 release gate；其中 Graphiti live smoke 已可通过，Cognee 仍是 experimental。

## 当前本机安装状态

- Python optional extra：已在项目 `.venv` 中安装 `.[memory]`，包含 `graphiti-core`、`cognee`、`neo4j` Python client。
- Neo4j：已通过 Homebrew 安装并启动，Bolt 地址为 `bolt://localhost:7687`。
- Neo4j 本地账号：`neo4j`，当前本机开发密码为 `mlresearchloop`。
- Docker：不是当前必需项。本机 Docker Desktop 未提供可用 daemon，本次改用 Homebrew Neo4j。
- 本地 OpenAI-compatible 服务：`http://127.0.0.1:1234/v1` 可返回 LM Studio 模型列表，但当前模型对 Graphiti/cognee 所需的结构化输出不稳定。

## 基础安装

```bash
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -e ".[memory]"
brew install neo4j
/opt/homebrew/opt/neo4j/bin/neo4j-admin dbms set-initial-password mlresearchloop --verbose
brew services start neo4j
```

验证 Neo4j：

```bash
/opt/homebrew/opt/cypher-shell/bin/cypher-shell \
  -a bolt://localhost:7687 \
  -u neo4j \
  -p mlresearchloop \
  'RETURN 1 AS ok;'
```

## Graphiti 配置

最低配置：

```bash
export ML_RESEARCH_LOOP_GRAPHITI_URI=bolt://localhost:7687
export ML_RESEARCH_LOOP_GRAPHITI_USER=neo4j
export ML_RESEARCH_LOOP_GRAPHITI_PASSWORD=mlresearchloop
```

如果不用 Graphiti 默认 OpenAI 模型，可以显式指定：

```bash
export ML_RESEARCH_LOOP_GRAPHITI_LLM_BASE_URL=http://127.0.0.1:1234/v1
export ML_RESEARCH_LOOP_GRAPHITI_LLM_API_KEY=lm-studio
export ML_RESEARCH_LOOP_GRAPHITI_LLM_MODEL=google/gemma-4-31b
export ML_RESEARCH_LOOP_GRAPHITI_LLM_SMALL_MODEL=google/gemma-4-31b
export ML_RESEARCH_LOOP_GRAPHITI_LLM_STRUCTURED_OUTPUT=chat_json_schema
export ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_BASE_URL=http://127.0.0.1:1234/v1
export ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_API_KEY=lm-studio
export ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
export ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_DIM=768
```

注意：Graphiti 需要严格结构化输出。默认 Graphiti client 使用 OpenAI Responses parse；LM Studio 本地服务当前更适合 `chat.completions + json_schema`，因此本地验收应显式设置 `ML_RESEARCH_LOOP_GRAPHITI_LLM_STRUCTURED_OUTPUT=chat_json_schema`。本机探测中 `google/gemma-4-31b` 比 `openai/gpt-oss-20b` 更稳定地返回 schema 字段。

项目写入 Graphiti 时会把 `ResearchMemoryCard` 当作独立 episode，并显式禁用 previous episode 上下文，避免重复 live smoke 后上下文膨胀并超过本地模型窗口。

## cognee 配置

cognee 对本地 OpenAI-compatible embedding 服务应使用 `openai_compatible` provider，避免把本地 embedding 模型名交给 tiktoken 自动映射：

```bash
export DATA_ROOT_DIRECTORY=$PWD/.demo_runs/cognee-live/data
export SYSTEM_ROOT_DIRECTORY=$PWD/.demo_runs/cognee-live/system
export CACHE_ROOT_DIRECTORY=$PWD/.demo_runs/cognee-live/cache
export COGNEE_LOGS_DIR=$PWD/.demo_runs/cognee-live/logs
export ENABLE_BACKEND_ACCESS_CONTROL=false
export CACHING=false
export COGNEE_SKIP_CONNECTION_TEST=true
export LLM_PROVIDER=custom
export LLM_MODEL=openai/openai/gpt-oss-20b:2
export LLM_ENDPOINT=http://127.0.0.1:1234/v1
export LLM_API_KEY=lm-studio
export LLM_INSTRUCTOR_MODE=json_schema_mode
export LLM_TEMPERATURE=0
export LLM_MAX_COMPLETION_TOKENS=768
export ML_RESEARCH_LOOP_COGNEE_TIMEOUT_SECONDS=60
export ML_RESEARCH_LOOP_COGNEE_CHUNKS_PER_BATCH=1
export EMBEDDING_PROVIDER=openai_compatible
export EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
export EMBEDDING_ENDPOINT=http://127.0.0.1:1234/v1
export EMBEDDING_API_KEY=lm-studio
export EMBEDDING_DIMENSIONS=768
export ML_RESEARCH_LOOP_COGNEE_DATASET=ml_research_loop_live_smoke
```

注意：cognee 在 OpenAI provider 下容易走 tool-calling 结构化输出；本地 LM Studio 对 `tool_choice` 兼容不足，因此本地验收建议使用 `LLM_PROVIDER=custom` 和 `LLM_INSTRUCTOR_MODE=json_schema_mode`。项目写入 cognee 时会使用紧凑事实卡和 research-memory 专用 graph prompt，而不是完整嵌套 JSON 或默认通用 KG prompt，降低抽图/摘要阶段的上下文压力。

本机模型选择的真实边界：

- `openai/google/gemma-4-31b`：结构化输出质量相对更好，但在 cognee `extract_graph_and_summarize` 阶段容易长时间等待。
- `openai/openai/gpt-oss-20b:2`：cognee 抽图速度明显更快，但输出质量较差，可能产生 `??`、`...` 或粗糙节点。adapter 会过滤明显坏质量 search 结果，但这不能替代更强模型或专用 schema。

当前本机验收状态：cognee 已能进入 ingest/cognify/search pipeline；`gpt-oss-20b:2` 能返回可检索 chunk，但 `cognify` 仍可能超时或返回嵌套 `PipelineRunErrored`，典型错误是 Cognee 内部 async lock 绑定到不同 event loop。adapter 与 live smoke 已将这类嵌套 pipeline error 识别为失败，避免把“search 有结果但 indexing 部分失败”的状态误报为 `passed`。Cognee 仍是 experimental；它不阻塞 beta/stable，也不进入默认 release gate。

## 验收命令

先生成 dependency-free baseline memory store：

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
  .venv/bin/python scripts/memory_smoke.py \
  --output-dir .demo_runs/memory-smoke-live-infra \
  --json
```

再跑可选 adapter smoke：

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
  .venv/bin/python scripts/memory_adapter_live_smoke.py \
  --store .demo_runs/memory-smoke-live-infra/memory.jsonl \
  --query "fastText AG News P@1" \
  --adapter graphiti \
  --json
```

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
  .venv/bin/python scripts/memory_adapter_live_smoke.py \
  --store .demo_runs/memory-smoke-live-infra/memory.jsonl \
  --query "fastText AG News P@1" \
  --adapter cognee \
  --json
```

验收口径：

- `scripts/memory_smoke.py` 必须通过，且 `official_scores_claimed=false`。
- Graphiti/cognee 未配置时必须返回 `skipped`，不能破坏 release gate。
- Graphiti/cognee 配置齐全时，只有当 adapter 完成 upsert 并检索到至少一条未被质量门禁过滤的结果，才可记为 `passed`；该结果只作为 optional integration evidence。
- Cognee sync payload 中只要出现顶层或嵌套 `status=failed`、`PipelineRunErrored`、`PipelineRunFailedError` 等失败态，live smoke 必须返回 `failed`；不能因为后续 search 有结果而通过。
- 当前本机状态是“基础设施已装好，Neo4j 可用，optional adapters 可被启用；Graphiti live smoke 已可通过；cognee 已有超时、专用 prompt、坏质量过滤和嵌套失败识别保护，但完整 live smoke 仍未通过”，不能宣传为 Graphiti/cognee 双 adapter live integration 已完全通过。

最近一次 Cognee + `openai/openai/gpt-oss-20b:2` 验收 artifact：

- 输出文件：`.demo_runs/cognee-live-gptoss2-nested-status-20260516d/smoke-output.txt`
- 结果：`status=failed`，`reason=one or more adapter sync operations failed`
- 关键证据：`search.match_count=2`，但 sync 中存在 `cognee cognify returned a failed pipeline status` 和嵌套 `PipelineRunErrored`
