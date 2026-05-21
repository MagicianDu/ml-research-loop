from __future__ import annotations

import json
from pathlib import Path

from lib.benchmarks.smol_worldcup import (
    DATASET_API_URL,
    DATASET_ROWS_URL,
    RUNTIME_EVALUATE_URL,
    RUNTIME_RESULTS_URL,
    SPACE_API_URL,
    SPACE_APP_URL,
    SPACE_README_URL,
    SPACE_TREE_URL,
    FetchedResource,
    build_smol_worldcup_live_verification,
    write_smol_worldcup_live_verification,
)


def test_smol_worldcup_live_verification_parses_target_contract() -> None:
    payload = build_smol_worldcup_live_verification(fetcher=_fake_fetcher)

    assert payload["status"] == "verified_with_limitations"
    assert payload["official_scores_claimed"] is False
    assert payload["parsed"]["dataset"]["sha"] == "dataset-sha"
    assert payload["parsed"]["space"]["sha"] == "space-sha"
    assert payload["parsed"]["dataset_rows"]["num_rows_total"] == 125
    assert payload["checks"]["ready_for_local_baseline"] is True
    assert payload["checks"]["external_submission_status"] == "needs_operator_confirmation"
    assert payload["checks"]["runtime_results_count"] == 0
    assert payload["parsed"]["space_app"]["supported_model_count"] == 2
    assert payload["parsed"]["space_app"]["routes_detected"] == ["/evaluate", "/api/results"]
    assert "HF_TOKEN" in payload["parsed"]["space_app"]["env_vars_detected"]
    assert "OPENAI_API_KEY" in payload["parsed"]["space_app"]["env_vars_detected"]
    assert "runtime_results_api_empty" in payload["limitations"]
    assert "space_repo_missing_results.json" in payload["limitations"]
    assert "space_repo_missing_smol_worldcup_s1.json" in payload["limitations"]
    assert "custom_model_submission_not_confirmed" in payload["limitations"]
    assert "leaderboard 成绩" in payload["claim_boundary"]


def test_write_smol_worldcup_live_verification_writes_json_markdown_and_raw(
    tmp_path: Path,
) -> None:
    result = write_smol_worldcup_live_verification(
        tmp_path / "p0",
        fetcher=_fake_fetcher,
    )

    json_path = Path(result["json_path"])
    contract_path = Path(result["contract_path"])
    raw_dir = Path(result["raw_dir"])
    assert result["status"] == "written"
    assert result["verification_status"] == "verified_with_limitations"
    assert result["official_scores_claimed"] is False
    assert result["ready_for_local_baseline"] is True
    assert json_path.exists()
    assert contract_path.exists()
    assert (raw_dir / "dataset_rows.json").exists()
    assert (raw_dir / "space_app.txt").exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = contract_path.read_text(encoding="utf-8")
    assert payload["checks"]["ready_for_local_baseline"] is True
    assert "official_scores_claimed: `false`" in markdown
    assert "ready_for_local_baseline: `true`" in markdown
    assert "runtime_results_api_empty" in markdown


def _fake_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
    del timeout_seconds
    payloads = {
        DATASET_API_URL: {
            "id": "ginigen-ai/smol-worldcup",
            "sha": "dataset-sha",
            "lastModified": "2026-03-10T14:47:44.000Z",
            "private": False,
            "gated": False,
            "tags": ["benchmark"],
        },
        DATASET_ROWS_URL: {
            "features": [
                {"name": name}
                for name in [
                    "id",
                    "shift_axis",
                    "category",
                    "subcategory",
                    "difficulty",
                    "prompt",
                    "answer_key",
                    "explanation",
                    "grading_rule",
                    "auto_grade",
                    "max_score",
                    "anchor",
                    "season",
                    "version",
                    "language",
                    "language_name",
                ]
            ],
            "rows": [
                {
                    "row_idx": 0,
                    "row": {
                        "id": "S1-H1-001",
                        "auto_grade": "json_field_check",
                        "category": "honesty",
                    },
                }
            ],
            "num_rows_total": 125,
            "partial": False,
        },
        SPACE_API_URL: {
            "id": "ginigen-ai/smol-worldcup",
            "sha": "space-sha",
            "lastModified": "2026-03-31T10:10:16.000Z",
            "private": False,
            "sdk": "gradio",
            "cardData": {"license": "apache-2.0"},
            "tags": ["gradio"],
        },
        SPACE_TREE_URL: [
            {"path": ".gitattributes"},
            {"path": "README.md"},
            {"path": "app.py"},
            {"path": "index.html"},
            {"path": "requirements.txt"},
        ],
        SPACE_README_URL: (
            "# Smol AI WorldCup\n\n"
            "Season 1 Results — 18 Models, 12 Makers\n\n"
            "WCS = sqrt(SHIFT * PIR_norm)\n"
            "SHIFT = H * 0.4 + I * 0.6\n"
            "PIR = (I * H * F) / (S * T)\n"
            "GPT-OSS-20B WCS 82.6\n"
        ),
        SPACE_APP_URL: (
            'DATASET_FILE = "smol_worldcup_s1.json"\n'
            'RESULTS_FILE = "results.json"\n'
            "HF_TOKEN = os.getenv('HF_TOKEN')\n"
            "OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')\n"
            "@app.get('/api/results')\n"
            "def api_results():\n"
            "    pass\n"
            "@app.post('/evaluate')\n"
            "def evaluate():\n"
            "    pass\n"
            "SUPPORTED_MODELS = {\n"
            '    "Qwen/Qwen3-0.6B": {},\n'
            '    "HuggingFaceTB/SmolLM2-1.7B-Instruct": {},\n'
            "}\n"
        ),
        RUNTIME_RESULTS_URL: {},
        RUNTIME_EVALUATE_URL: "<html><body>gradio app</body></html>",
    }
    payload = payloads[url]
    text = payload if isinstance(payload, str) else json.dumps(payload)
    content_type = "text/plain" if isinstance(payload, str) else "application/json"
    return FetchedResource(
        url=url,
        status_code=200,
        content_type=content_type,
        text=text,
        fetcher="fake",
    )
