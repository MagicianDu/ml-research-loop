# Graphiti/cognee 可选记忆基础设施本地安装与验收

本文记录本项目的可选 Research Memory Layer 基础设施安装方式。Graphiti/cognee 不是 fresh checkout 的默认依赖；默认路径仍是本地 JSONL memory store。只有在显式安装和显式传参时，MCP/CLI 才会访问外部记忆服务。

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
export ML_RESEARCH_LOOP_GRAPHITI_LLM_MODEL=openai/gpt-oss-20b
export ML_RESEARCH_LOOP_GRAPHITI_LLM_SMALL_MODEL=openai/gpt-oss-20b
export ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_BASE_URL=http://127.0.0.1:1234/v1
export ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_API_KEY=lm-studio
export ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
export ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_DIM=768
```

注意：Graphiti 需要严格结构化输出。本机 LM Studio + `openai/gpt-oss-20b` 能连通，但当前实际 `add_episode` 会返回非严格 JSON，导致 Graphiti 的 Pydantic schema 校验失败。因此这套本地模型只能证明基础设施可达，不能证明 Graphiti live smoke 已通过。

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
export LLM_PROVIDER=openai
export LLM_MODEL=openai/google/gemma-4-31b
export LLM_ENDPOINT=http://127.0.0.1:1234/v1
export LLM_API_KEY=lm-studio
export EMBEDDING_PROVIDER=openai_compatible
export EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
export EMBEDDING_ENDPOINT=http://127.0.0.1:1234/v1
export EMBEDDING_API_KEY=lm-studio
export EMBEDDING_DIMENSIONS=768
export ML_RESEARCH_LOOP_COGNEE_DATASET=ml_research_loop_live_smoke
```

注意：这套配置已经越过 tokenizer 映射问题，并进入 cognee ingest/cognify pipeline；但当前本地 LLM 在抽图/摘要阶段长时间无结果，尚未形成可复核的 `passed` live smoke。

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
- Graphiti/cognee 配置齐全时，只有当 adapter 完成 upsert 并检索到至少一条结果，才可记为 `passed`。
- 当前本机状态是“基础设施已装好，Neo4j 可用，optional adapters 可被启用；live smoke 卡在本地 LLM 结构化输出质量”，不能宣传为 Graphiti/cognee live integration 已完全通过。
