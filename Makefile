.PHONY: help install test test-python lint mcp-smoke-python run-demo run-demo-python run-fresh-demo-python run-ai-demo clean

help:
	@echo "ml-research-loop — AI autonomous ML research engine"
	@echo ""
	@echo "Available targets:"
	@echo "  install      Install dependencies with uv"
	@echo "  test         Run unit tests"
	@echo "  test-python  Run unit tests using python3 + local .venv site-packages"
	@echo "  lint         Run ruff linter"
	@echo "  mcp-smoke-python  Smoke-test the MCP stdio server"
	@echo "  run-demo     Run demo with synthetic data (random sampling)"
	@echo "  run-demo-python  Run short demo using python3 fallback"
	@echo "  run-fresh-demo-python  Run a fresh isolated demo every time"
	@echo "  run-ai-demo  Run AI-driven demo (LLM-guided research)"
	@echo "  clean        Remove generated files"

install:
	uv sync
	uv pip install -e .

test:
	uv run pytest tests/ -v

test-python:
	PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q

lint:
	uv run ruff check lib/ scripts/ ml_intern/

mcp-smoke-python:
	@printf '%s\n' \
		'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' \
		'{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | \
		PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 scripts/mcp_server.py

run-demo:
	@echo "Running demo with synthetic data..."
	uv run python scripts/autoresearch_run.py \
		--task-config tasks/demo-mnist-001.json \
		--workspace ./workdir/demo-mnist-001 \
		--max-experiments 3 \
		--experiment-duration 60 \
		--verbose

run-demo-python:
	@echo "Running short demo with python3 fallback..."
	ML_RESEARCH_LOOP_PYTHON=$$(which python3) PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 scripts/autoresearch_run.py \
		--task-config tasks/demo-mnist-001.json \
		--workspace ./workdir/demo-mnist-001 \
		--max-experiments 1 \
		--experiment-duration 30 \
		--verbose

run-fresh-demo-python:
	@echo "Running fresh isolated demo..."
	ML_RESEARCH_LOOP_PYTHON=$$(which python3) PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 scripts/fresh_demo.py \
		--max-experiments 1 \
		--experiment-duration 30

run-ai-demo:
	@echo "Running AI-driven demo with synthetic data..."
	uv run python scripts/ai_autoresearch_run.py \
		--task-config tasks/demo-mnist-001.json \
		--workspace ./workdir/ai-demo \
		--max-experiments 3 \
		--experiment-duration 60 \
		--mock \
		--verbose

clean:
	rm -rf workdir/*/ experiments.json
	rm -rf results/*-progress.json results/*.json
	rm -rf snapshots/*/
	rm -f tasks/*.lock
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
