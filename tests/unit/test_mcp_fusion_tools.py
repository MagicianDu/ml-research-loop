from __future__ import annotations

import json
from pathlib import Path

from lib import mcp_service
from lib.research_protocol import ResearchSource
from ml_intern import research_tools


def _request(request_id: int, method: str, params: dict | None = None) -> dict:
    request = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    return request


def test_mcp_lists_fusion_tools() -> None:
    response = mcp_service.handle_request(_request(1, "tools/list"))
    names = {tool["name"] for tool in response["result"]["tools"]}

    assert {
        "read_paper",
        "research_task",
        "propose_hypotheses",
        "run_hypothesis_experiment",
        "review_research_results",
    }.issubset(names)


def test_propose_hypotheses_returns_research_brief() -> None:
    response = mcp_service.handle_request(
        _request(
            2,
            "tools/call",
            {
                "name": "propose_hypotheses",
                "arguments": {
                    "objective": "minimize val_bpb",
                    "sources": [{"title": "ALiBi", "source_type": "paper"}],
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["objective"] == "minimize val_bpb"
    assert payload["hypotheses"][0]["hypothesis_id"] == "hyp-001"
    assert "ALiBi" in payload["hypotheses"][0]["rationale"]


def test_propose_hypotheses_preserves_research_sources() -> None:
    response = mcp_service.handle_request(
        _request(
            3,
            "tools/call",
            {
                "name": "propose_hypotheses",
                "arguments": {
                    "objective": "minimize val_bpb",
                    "sources": [
                        {
                            "source_type": "paper",
                            "title": "ALiBi",
                            "url": "https://arxiv.org/abs/2108.12409",
                            "summary": "Attention with linear biases.",
                        }
                    ],
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["sources"][0]["source_type"] == "paper"
    assert payload["sources"][0]["title"] == "ALiBi"


def test_propose_hypotheses_extracts_findings_from_sources() -> None:
    response = mcp_service.handle_request(
        _request(
            31,
            "tools/call",
            {
                "name": "propose_hypotheses",
                "arguments": {
                    "objective": "minimize val_bpb",
                    "sources": [
                        {
                            "source_type": "paper",
                            "title": "ALiBi",
                            "url": "https://arxiv.org/abs/2108.12409",
                            "summary": (
                                "Attention with linear biases improves length extrapolation. "
                                "It avoids changing the transformer block."
                            ),
                        }
                    ],
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["findings"] == [
        {
            "finding_id": "finding-001",
            "claim": "Attention with linear biases improves length extrapolation.",
            "evidence": ["paper:ALiBi"],
            "relevance": "Candidate evidence for minimize val_bpb",
        }
    ]
    assert "length extrapolation" in payload["hypotheses"][0]["rationale"]


def test_propose_hypotheses_prioritizes_ranked_sources() -> None:
    response = mcp_service.handle_request(
        _request(
            32,
            "tools/call",
            {
                "name": "propose_hypotheses",
                "arguments": {
                    "objective": "minimize val_bpb",
                    "sources": [
                        {
                            "source_type": "paper",
                            "title": "Generic Transformer Note",
                            "summary": "A generic baseline.",
                            "metadata": {"relevance_score": 0.5},
                        },
                        {
                            "source_type": "paper",
                            "title": "TinyStories Curriculum",
                            "summary": "Curriculum sampling improves TinyStories validation bpb.",
                            "metadata": {"relevance_score": 9.0},
                        },
                    ],
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["findings"][0]["evidence"] == ["paper:TinyStories Curriculum"]
    assert "TinyStories Curriculum" in payload["hypotheses"][0]["rationale"].split(" | ")[0]


def test_research_task_collects_sources_and_generates_hypotheses(monkeypatch) -> None:
    calls: list[tuple[str, str, int]] = []

    def fake_search_papers(query: str, limit: int = 5):
        calls.append(("papers", query, limit))
        return [
            ResearchSource(
                source_type="paper",
                title="Train Short, Test Long",
                url="https://arxiv.org/abs/2108.12409",
                summary="ALiBi improves length extrapolation.",
            )
        ]

    def fake_search_hf_datasets(query: str, limit: int = 5):
        calls.append(("hf_datasets", query, limit))
        return [
            ResearchSource(
                source_type="hf_dataset",
                title="roneneldan/TinyStories",
                url="https://huggingface.co/datasets/roneneldan/TinyStories",
                summary="Synthetic short stories.",
            )
        ]

    def fake_search_github_code(query: str, limit: int = 5):
        calls.append(("github_code", query, limit))
        return [
            ResearchSource(
                source_type="github_code",
                title="karpathy/nanoGPT:train.py",
                url="https://github.com/karpathy/nanoGPT/blob/master/train.py",
                summary="training loop reference",
            )
        ]

    monkeypatch.setattr(research_tools, "search_papers", fake_search_papers)
    monkeypatch.setattr(research_tools, "search_hf_datasets", fake_search_hf_datasets)
    monkeypatch.setattr(research_tools, "search_github_code", fake_search_github_code)

    response = mcp_service.handle_request(
        _request(
            4,
            "tools/call",
            {
                "name": "research_task",
                "arguments": {
                    "objective": "reduce val_bpb on TinyStories",
                    "query": "alibi tiny stories train.py",
                    "paper_limit": 1,
                    "dataset_limit": 1,
                    "github_limit": 1,
                    "include_github_code": True,
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["status"] == "research_context_ready"
    assert payload["query"] == "alibi tiny stories train.py"
    assert payload["query_plan"][0] == {
        "query": "alibi tiny stories train.py",
        "reason": "primary",
    }
    assert [source["source_type"] for source in payload["sources"]] == [
        "paper",
        "hf_dataset",
        "github_code",
    ]
    assert payload["source_counts"] == {
        "paper": 1,
        "hf_dataset": 1,
        "github_code": 1,
    }
    assert payload["hypotheses"][0]["hypothesis_id"] == "hyp-001"
    assert "Train Short, Test Long" in payload["hypotheses"][0]["rationale"]
    assert ["paper:Train Short, Test Long"] in [
        finding["evidence"] for finding in payload["findings"]
    ]
    assert calls == [
        ("papers", "alibi tiny stories train.py", 1),
        ("hf_datasets", "alibi tiny stories train.py", 1),
        ("github_code", "alibi tiny stories train.py", 1),
    ]


def test_research_task_returns_partial_context_when_one_backend_fails(monkeypatch) -> None:
    def fake_search_papers(query: str, limit: int = 5):
        del query, limit
        raise RuntimeError("arXiv unavailable")

    def fake_search_hf_datasets(query: str, limit: int = 5):
        del query, limit
        return [
            ResearchSource(
                source_type="hf_dataset",
                title="roneneldan/TinyStories",
                url="https://huggingface.co/datasets/roneneldan/TinyStories",
            )
        ]

    monkeypatch.setattr(research_tools, "search_papers", fake_search_papers)
    monkeypatch.setattr(research_tools, "search_hf_datasets", fake_search_hf_datasets)

    response = mcp_service.handle_request(
        _request(
            5,
            "tools/call",
            {
                "name": "research_task",
                "arguments": {
                    "objective": "reduce val_bpb",
                    "query": "tiny stories",
                    "paper_limit": 1,
                    "dataset_limit": 1,
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["status"] == "research_context_partial"
    assert payload["sources"][0]["source_type"] == "hf_dataset"
    assert payload["warnings"] == ["papers: arXiv unavailable"]


def test_read_paper_returns_source_findings_and_hypotheses(monkeypatch) -> None:
    def fake_read_paper(identifier: str):
        assert identifier == "2108.12409"
        return ResearchSource(
            source_type="paper",
            title="Train Short, Test Long",
            url="https://arxiv.org/abs/2108.12409",
            summary=(
                "Attention with linear biases improves length extrapolation. "
                "The method changes attention scores without adding parameters."
            ),
            metadata={"arxiv_id": "2108.12409"},
        )

    monkeypatch.setattr(research_tools, "read_paper", fake_read_paper)

    response = mcp_service.handle_request(
        _request(
            56,
            "tools/call",
            {
                "name": "read_paper",
                "arguments": {
                    "identifier": "2108.12409",
                    "objective": "minimize val_bpb with length extrapolation",
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["status"] == "paper_ready"
    assert payload["source"]["title"] == "Train Short, Test Long"
    assert payload["source"]["metadata"]["arxiv_id"] == "2108.12409"
    assert payload["findings"][0]["claim"] == (
        "Attention with linear biases improves length extrapolation."
    )
    assert payload["evidence_snippets"] == [
        {
            "snippet_id": "snippet-001",
            "source": "paper:Train Short, Test Long",
            "section": "abstract",
            "text": "Attention with linear biases improves length extrapolation.",
            "relevance_score": 2.0,
        },
        {
            "snippet_id": "snippet-002",
            "source": "paper:Train Short, Test Long",
            "section": "abstract",
            "text": "The method changes attention scores without adding parameters.",
            "relevance_score": 0.0,
        },
    ]
    assert payload["hypotheses"][0]["hypothesis_id"] == "hyp-001"
    assert "Train Short, Test Long" in payload["hypotheses"][0]["rationale"]


def test_read_paper_extracts_section_evidence_snippets(monkeypatch) -> None:
    def fake_read_paper(identifier: str):
        assert identifier == "2401.00001"
        return ResearchSource(
            source_type="paper",
            title="Curriculum Sampling",
            url="https://arxiv.org/abs/2401.00001",
            summary="",
            metadata={
                "sections": [
                    {
                        "title": "method",
                        "text": "Curriculum sampling improves validation bpb. It changes data order.",
                    },
                    {
                        "title": "results",
                        "text": "Validation bits per byte improves on small models.",
                    },
                ]
            },
        )

    monkeypatch.setattr(research_tools, "read_paper", fake_read_paper)

    response = mcp_service.handle_request(
        _request(
            57,
            "tools/call",
            {
                "name": "read_paper",
                "arguments": {
                    "identifier": "2401.00001",
                    "objective": "improve validation bpb",
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert [snippet["section"] for snippet in payload["evidence_snippets"]] == [
        "method",
        "method",
        "results",
    ]
    assert payload["evidence_snippets"][0]["text"] == (
        "Curriculum sampling improves validation bpb."
    )


def test_research_task_deduplicates_and_ranks_sources(monkeypatch) -> None:
    def fake_search_papers(query: str, limit: int = 5):
        del query, limit
        return [
            ResearchSource(
                source_type="paper",
                title="TinyStories Transformer Scaling",
                url="https://arxiv.org/abs/2401.00001",
                summary="TinyStories transformer training improves validation bits per byte.",
            ),
            ResearchSource(
                source_type="paper",
                title="Duplicate TinyStories Transformer Scaling",
                url="https://arxiv.org/abs/2401.00001",
                summary="Duplicate source should not appear twice.",
            ),
        ]

    def fake_search_hf_datasets(query: str, limit: int = 5):
        del query, limit
        return [
            ResearchSource(
                source_type="hf_dataset",
                title="roneneldan/TinyStories",
                url="https://huggingface.co/datasets/roneneldan/TinyStories",
                summary="Synthetic stories for small language models.",
            )
        ]

    monkeypatch.setattr(research_tools, "search_papers", fake_search_papers)
    monkeypatch.setattr(research_tools, "search_hf_datasets", fake_search_hf_datasets)

    response = mcp_service.handle_request(
        _request(
            52,
            "tools/call",
            {
                "name": "research_task",
                "arguments": {
                    "objective": "reduce val_bpb on TinyStories transformer",
                    "query": "tiny stories transformer",
                    "paper_limit": 2,
                    "dataset_limit": 1,
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert [source["title"] for source in payload["sources"]] == [
        "TinyStories Transformer Scaling",
        "roneneldan/TinyStories",
    ]
    assert payload["source_counts"] == {"paper": 1, "hf_dataset": 1}
    assert payload["sources"][0]["metadata"]["relevance_score"] > 0
    assert payload["source_rankings"][0] == {
        "rank": 1,
        "source_type": "paper",
        "title": "TinyStories Transformer Scaling",
        "url": "https://arxiv.org/abs/2401.00001",
        "relevance_score": payload["sources"][0]["metadata"]["relevance_score"],
        "evidence": "paper:TinyStories Transformer Scaling",
    }


def test_review_research_results_adds_hypothesis_outcomes(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    result_file = results_dir / "hypothesis-task.json"
    result_file.write_text(
        json.dumps({
            "task_id": "hypothesis-task",
            "status": "completed",
            "best_result": {"experiment_id": "exp-001", "val": 0.82},
            "hypotheses": [
                {
                    "hypothesis_id": "hyp-001",
                    "title": "Try ALiBi",
                    "expected_metric": "val_bpb",
                    "expected_direction": "minimize",
                }
            ],
            "experiments": [
                {
                    "experiment_id": "exp-001",
                    "hypothesis_id": "hyp-001",
                    "metrics": {"val_bpb": 0.82},
                    "accepted": True,
                },
                {
                    "experiment_id": "exp-002",
                    "hypothesis_id": "hyp-001",
                    "metrics": {"val_bpb": 0.87},
                    "accepted": False,
                },
            ],
            "summary": {"total_experiments": 2, "accepted": 1, "failed": 0},
        }),
        encoding="utf-8",
    )

    response = mcp_service.handle_request(
        _request(
            51,
            "tools/call",
            {
                "name": "review_research_results",
                "arguments": {
                    "task_id": "hypothesis-task",
                    "runtime_root": str(tmp_path),
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["research_review"]["decision"] == "continue_from_best"
    assert payload["research_review"]["hypothesis_outcomes"] == [
        {
            "hypothesis_id": "hyp-001",
            "title": "Try ALiBi",
            "experiments": 2,
            "accepted": 1,
            "failed": 0,
            "best_experiment_id": "exp-001",
            "best_val": 0.82,
            "status": "supported",
        }
    ]
    assert payload["research_review"]["next_actions"][0] == (
        "Continue locally around best params from exp-001."
    )
    assert payload["research_review"]["recommended_search_space"] == {
        "strategy": "local_refinement",
        "center_params": {},
        "avoid_params": [],
        "parameter_hints": {},
    }


def test_review_research_results_returns_codex_planner_state(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    workspace = tmp_path / "workdir" / "planner-task"
    workspace.mkdir(parents=True)
    (workspace / "train.py").write_text(
        "\n".join([
            "# ======= AUTORESEARCH SEARCH REGION START =======",
            "LR = 0.001",
            "DEPTH = 4",
            "# ======= AUTORESEARCH SEARCH REGION END =======",
        ]),
        encoding="utf-8",
    )
    (workspace / "program.md").write_text(
        "# Program\n\nKeep the next run local around the best result.",
        encoding="utf-8",
    )
    (results_dir / "planner-task.json").write_text(
        json.dumps({
            "task_id": "planner-task",
            "status": "completed",
            "best_result": {
                "experiment_id": "exp-002",
                "val": 0.7,
                "params": {"lr": 0.001, "depth": 4},
            },
            "experiments": [
                {
                    "experiment_id": "exp-001",
                    "params": {"lr": 0.01, "depth": 4},
                    "metrics": {"val_bpb": 0.9},
                    "accepted": False,
                    "error": "loss exploded",
                },
                {
                    "experiment_id": "exp-002",
                    "params": {"lr": 0.001, "depth": 4},
                    "metrics": {"val_bpb": 0.7},
                    "accepted": True,
                },
            ],
            "summary": {"total_experiments": 2, "accepted": 1, "failed": 1},
        }),
        encoding="utf-8",
    )

    response = mcp_service.handle_request(
        _request(
            52,
            "tools/call",
            {
                "name": "review_research_results",
                "arguments": {
                    "task_id": "planner-task",
                    "runtime_root": str(tmp_path),
                    "workspace": str(workspace),
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])
    state = payload["experiment_state"]

    assert state["planner_handoff"]["client_model_role"] == "decide_next_code_or_param_change"
    assert state["planner_handoff"]["recommended_next_tool"] == "run_hypothesis_experiment"
    assert state["current_code"]["search_region"] == {"LR": "0.001", "DEPTH": "4"}
    assert state["current_code"]["program_md_excerpt"].startswith("# Program")
    assert state["recent_experiments"] == [
        {
            "experiment_id": "exp-001",
            "params": {"lr": 0.01, "depth": 4},
            "metrics": {"val_bpb": 0.9},
            "accepted": False,
            "error": "loss exploded",
            "hypothesis_id": None,
            "snapshot_path": None,
        },
        {
            "experiment_id": "exp-002",
            "params": {"lr": 0.001, "depth": 4},
            "metrics": {"val_bpb": 0.7},
            "accepted": True,
            "error": None,
            "hypothesis_id": None,
            "snapshot_path": None,
        },
    ]
    assert state["failure_summary"] == {
        "failed_count": 1,
        "recent_errors": [{"experiment_id": "exp-001", "error": "loss exploded"}],
    }
    assert state["artifacts"]["workspace"] == str(workspace)
    assert state["artifacts"]["train_py"] == str(workspace / "train.py")
    assert state["artifacts"]["program_md"] == str(workspace / "program.md")
    assert state["next_round"]["task_patch"] == payload["research_review"]["next_task_patch"]


def test_review_research_results_recommends_next_search_space(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    (results_dir / "search-space-task.json").write_text(
        json.dumps({
            "task_id": "search-space-task",
            "status": "completed",
            "best_result": {
                "experiment_id": "exp-002",
                "val": 0.7,
                "params": {"lr": 0.001, "depth": 4},
            },
            "hypotheses": [
                {
                    "hypothesis_id": "hyp-001",
                    "title": "Tune lr",
                    "expected_metric": "val_bpb",
                    "expected_direction": "minimize",
                }
            ],
            "experiments": [
                {
                    "experiment_id": "exp-001",
                    "hypothesis_id": "hyp-001",
                    "params": {"lr": 0.01, "depth": 4},
                    "metrics": {"val_bpb": 0.9},
                    "accepted": False,
                },
                {
                    "experiment_id": "exp-002",
                    "hypothesis_id": "hyp-001",
                    "params": {"lr": 0.001, "depth": 4},
                    "metrics": {"val_bpb": 0.7},
                    "accepted": True,
                },
            ],
        }),
        encoding="utf-8",
    )

    response = mcp_service.handle_request(
        _request(
            53,
            "tools/call",
            {
                "name": "review_research_results",
                "arguments": {
                    "task_id": "search-space-task",
                    "runtime_root": str(tmp_path),
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["research_review"]["recommended_search_space"] == {
        "strategy": "local_refinement",
        "center_params": {"lr": 0.001, "depth": 4},
        "avoid_params": [{"lr": 0.01, "depth": 4}],
        "parameter_hints": {
            "lr": {
                "type": "q_log_uniform",
                "min": 0.0005,
                "max": 0.002,
                "q": 0.0001,
            },
            "depth": {"type": "choice", "values": [3, 4, 5]},
        },
    }
    assert payload["research_review"]["experiment_strategy"] == {
        "mode": "local_refinement",
        "focus_params": ["lr", "depth"],
        "avoid_params_count": 1,
        "recommended_max_experiments": 3,
        "stop_conditions": [
            "stop after a locally refined configuration improves the current best metric",
            "stop if all local candidates are rejected or fail",
        ],
    }
    assert payload["research_review"]["next_task_patch"] == {
        "hyperparameter_space": payload["research_review"]["recommended_search_space"]["parameter_hints"],
        "sampling_constraints": {
            "avoid_params": [{"lr": 0.01, "depth": 4}],
        },
        "budget": {
            "max_experiments": 3,
        },
        "program_md_overrides": {
            "hints": [
                "Continue locally around best params from exp-002.",
                "Run one narrower follow-up experiment before widening the search space.",
                "Strategy: local_refinement.",
                "Stop condition: stop after a locally refined configuration improves the current best metric",
                "Stop condition: stop if all local candidates are rejected or fail",
            ],
        },
    }


def test_review_research_results_keeps_architecture_hints_runnable(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    (results_dir / "safe-hints-task.json").write_text(
        json.dumps({
            "task_id": "safe-hints-task",
            "status": "completed",
            "best_result": {
                "experiment_id": "exp-001",
                "val": 0.7,
                "params": {"dim": 32, "window_size": 256, "depth": 1},
            },
            "hypotheses": [
                {
                    "hypothesis_id": "hyp-001",
                    "title": "Tune safe architecture params",
                    "expected_metric": "val_bpb",
                    "expected_direction": "minimize",
                }
            ],
            "experiments": [
                {
                    "experiment_id": "exp-001",
                    "hypothesis_id": "hyp-001",
                    "params": {"dim": 32, "window_size": 256, "depth": 1},
                    "metrics": {"val_bpb": 0.7},
                    "accepted": True,
                },
            ],
        }),
        encoding="utf-8",
    )

    response = mcp_service.handle_request(
        _request(
            54,
            "tools/call",
            {
                "name": "review_research_results",
                "arguments": {
                    "task_id": "safe-hints-task",
                    "runtime_root": str(tmp_path),
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])
    hints = payload["research_review"]["recommended_search_space"]["parameter_hints"]

    assert hints["dim"] == {"type": "choice", "values": [16, 32, 64]}
    assert hints["window_size"] == {"type": "choice", "values": [256, 512]}
    assert hints["depth"] == {"type": "choice", "values": [1, 2]}


def test_run_hypothesis_experiment_injects_research_context_into_task_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    task_file = tmp_path / "base-task.json"
    task_file.write_text(
        json.dumps({
            "task_id": "hypothesis-task",
            "objective": "minimize val_bpb",
            "dataset": {"name": "synthetic", "path": "missing.bin"},
            "metric": {"name": "val_bpb", "direction": "minimize"},
            "hyperparameter_space": {},
            "budget": {"max_experiments": 1},
            "base_code": {"train_py_url": "file://train.py", "prepare_py_url": "file://prepare.py"},
        }),
        encoding="utf-8",
    )
    research_context = {
        "sources": [
            {
                "source_type": "paper",
                "title": "ALiBi",
                "url": "https://arxiv.org/abs/2108.12409",
            }
        ]
    }
    hypotheses = [{"hypothesis_id": "hyp-001", "title": "Try ALiBi"}]
    captured: dict = {}

    def fake_run_autoresearch_tool(arguments: dict) -> dict:
        captured.update(arguments)
        injected_task = json.loads(Path(arguments["task_config"]).read_text(encoding="utf-8"))
        return {"status": "completed", "task": injected_task}

    monkeypatch.setattr(mcp_service, "run_autoresearch_tool", fake_run_autoresearch_tool)

    response = mcp_service.handle_request(
        _request(
            6,
            "tools/call",
            {
                "name": "run_hypothesis_experiment",
                "arguments": {
                    "task_config": str(task_file),
                    "runtime_root": str(tmp_path),
                    "research_context": research_context,
                    "hypotheses": hypotheses,
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["task"]["research_context"]["sources"][0]["title"] == "ALiBi"
    assert payload["task"]["hypotheses"][0]["hypothesis_id"] == "hyp-001"
    assert captured["task_config"] != str(task_file)
    assert Path(captured["task_config"]).parent == tmp_path / "tasks"


def test_run_hypothesis_experiment_applies_next_task_patch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    task_file = tmp_path / "base-task.json"
    task_file.write_text(
        json.dumps({
            "task_id": "patched-task",
            "objective": "minimize val_bpb",
            "dataset": {"name": "synthetic", "path": "missing.bin"},
            "metric": {"name": "val_bpb", "direction": "minimize"},
            "hyperparameter_space": {
                "lr": {"type": "log_uniform", "min": 1e-5, "max": 1e-2},
            },
            "budget": {"max_experiments": 1},
            "base_code": {"train_py_url": "file://train.py", "prepare_py_url": "file://prepare.py"},
        }),
        encoding="utf-8",
    )
    next_task_patch = {
        "hyperparameter_space": {
            "lr": {"type": "q_log_uniform", "min": 0.0005, "max": 0.002, "q": 0.0001},
        },
        "sampling_constraints": {
            "avoid_params": [{"lr": 0.01}],
        },
        "program_md_overrides": {
            "hints": ["Continue locally around best params from exp-002."],
        },
    }

    def fake_run_autoresearch_tool(arguments: dict) -> dict:
        injected_task = json.loads(Path(arguments["task_config"]).read_text(encoding="utf-8"))
        return {"status": "completed", "task": injected_task}

    monkeypatch.setattr(mcp_service, "run_autoresearch_tool", fake_run_autoresearch_tool)

    response = mcp_service.handle_request(
        _request(
            54,
            "tools/call",
            {
                "name": "run_hypothesis_experiment",
                "arguments": {
                    "task_config": str(task_file),
                    "runtime_root": str(tmp_path),
                    "task_patch": next_task_patch,
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["task"]["hyperparameter_space"] == next_task_patch["hyperparameter_space"]
    assert payload["task"]["sampling_constraints"] == next_task_patch["sampling_constraints"]
    assert payload["task"]["program_md_overrides"]["hints"] == next_task_patch["program_md_overrides"]["hints"]


def test_run_hypothesis_experiment_keeps_search_space_when_recommendation_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    task_file = tmp_path / "base-task.json"
    original_space = {
        "lr": {"type": "log_uniform", "min": 1e-5, "max": 1e-2},
    }
    task_file.write_text(
        json.dumps({
            "task_id": "unchanged-space-task",
            "objective": "minimize val_bpb",
            "dataset": {"name": "synthetic", "path": "missing.bin"},
            "metric": {"name": "val_bpb", "direction": "minimize"},
            "hyperparameter_space": original_space,
            "budget": {"max_experiments": 1},
            "base_code": {"train_py_url": "file://train.py", "prepare_py_url": "file://prepare.py"},
        }),
        encoding="utf-8",
    )

    def fake_run_autoresearch_tool(arguments: dict) -> dict:
        injected_task = json.loads(Path(arguments["task_config"]).read_text(encoding="utf-8"))
        return {"status": "completed", "task": injected_task}

    monkeypatch.setattr(mcp_service, "run_autoresearch_tool", fake_run_autoresearch_tool)

    response = mcp_service.handle_request(
        _request(
            55,
            "tools/call",
            {
                "name": "run_hypothesis_experiment",
                "arguments": {
                    "task_config": str(task_file),
                    "runtime_root": str(tmp_path),
                    "recommended_search_space": {
                        "parameter_hints": {},
                        "avoid_params": [],
                    },
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["task"]["hyperparameter_space"] == original_space
