from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from lib.research_protocol import ResearchSource
from ml_intern import research_tools


def test_normalize_paper_result_preserves_source_type() -> None:
    result = research_tools.normalize_paper_result({
        "title": "ALiBi",
        "url": "https://arxiv.org/abs/2108.12409",
        "summary": "Linear biases for attention.",
    })

    assert result.source_type == "paper"
    assert result.title == "ALiBi"
    assert result.url.endswith("2108.12409")


def test_normalize_dataset_result_preserves_hf_dataset_id() -> None:
    result = research_tools.normalize_dataset_result({
        "id": "roneneldan/TinyStories",
        "description": "Synthetic short stories.",
    })

    assert result.source_type == "hf_dataset"
    assert result.title == "roneneldan/TinyStories"
    assert result.metadata["dataset_id"] == "roneneldan/TinyStories"


def test_search_papers_parses_arxiv_atom_feed() -> None:
    seen_urls: list[str] = []

    def fake_fetch_text(url: str, headers: dict[str, str] | None = None) -> str:
        del headers
        seen_urls.append(url)
        return """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/2108.12409v2</id>
            <title>Train Short, Test Long: Attention with Linear Biases</title>
            <summary>
              We add linear biases to attention scores for length extrapolation.
            </summary>
            <published>2021-08-27T17:59:31Z</published>
            <updated>2022-04-19T12:00:00Z</updated>
            <author><name>Ofir Press</name></author>
            <link href="http://arxiv.org/abs/2108.12409v2" rel="alternate" type="text/html"/>
            <link title="pdf" href="http://arxiv.org/pdf/2108.12409v2" rel="related" type="application/pdf"/>
          </entry>
        </feed>
        """

    results = research_tools.search_papers("linear attention bias", limit=1, fetch_text=fake_fetch_text)

    assert len(results) == 1
    assert results[0].source_type == "paper"
    assert results[0].title == "Train Short, Test Long: Attention with Linear Biases"
    assert results[0].url == "http://arxiv.org/abs/2108.12409v2"
    assert "linear biases" in results[0].summary
    assert results[0].metadata["arxiv_id"] == "2108.12409"
    assert results[0].metadata["pdf_url"] == "http://arxiv.org/pdf/2108.12409v2"
    assert results[0].metadata["authors"] == ["Ofir Press"]

    query_params = parse_qs(urlparse(seen_urls[0]).query)
    assert query_params["search_query"] == ["all:linear attention bias"]
    assert query_params["max_results"] == ["1"]
    assert query_params["sortBy"] == ["relevance"]


def test_read_paper_fetches_arxiv_metadata_by_id() -> None:
    seen_urls: list[str] = []

    def fake_fetch_text(url: str, headers: dict[str, str] | None = None) -> str:
        del headers
        seen_urls.append(url)
        return """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/1706.03762v7</id>
            <title>Attention Is All You Need</title>
            <summary>The Transformer model relies entirely on attention.</summary>
            <published>2017-06-12T17:57:34Z</published>
            <author><name>Ashish Vaswani</name></author>
          </entry>
        </feed>
        """

    result = research_tools.read_paper("https://arxiv.org/abs/1706.03762v7", fetch_text=fake_fetch_text)

    assert result.source_type == "paper"
    assert result.metadata["arxiv_id"] == "1706.03762"
    assert result.title == "Attention Is All You Need"
    assert parse_qs(urlparse(seen_urls[0]).query)["id_list"] == ["1706.03762"]


def test_search_hf_datasets_uses_injected_hub_api_client() -> None:
    class DatasetInfo:
        id = "roneneldan/TinyStories"
        description = "Synthetic short stories for small language models."
        likes = 42
        downloads = 123
        tags = ["text-generation"]

    class FakeApi:
        def list_datasets(self, search: str, limit: int):
            assert search == "tiny stories"
            assert limit == 1
            return [DatasetInfo()]

    results = research_tools.search_hf_datasets("tiny stories", limit=1, api=FakeApi())

    assert len(results) == 1
    assert results[0].source_type == "hf_dataset"
    assert results[0].title == "roneneldan/TinyStories"
    assert results[0].url == "https://huggingface.co/datasets/roneneldan/TinyStories"
    assert results[0].summary == "Synthetic short stories for small language models."
    assert results[0].metadata["downloads"] == 123
    assert results[0].metadata["likes"] == 42
    assert results[0].metadata["tags"] == ["text-generation"]


def test_search_github_code_parses_rest_response() -> None:
    seen_urls: list[str] = []
    seen_headers: list[dict[str, str] | None] = []

    def fake_fetch_json(url: str, headers: dict[str, str] | None = None):
        seen_urls.append(url)
        seen_headers.append(headers)
        return {
            "items": [
                {
                    "name": "train.py",
                    "path": "examples/train.py",
                    "html_url": "https://github.com/org/repo/blob/main/examples/train.py",
                    "score": 1.0,
                    "repository": {
                        "full_name": "org/repo",
                        "html_url": "https://github.com/org/repo",
                    },
                    "text_matches": [{"fragment": "def train(): pass"}],
                }
            ]
        }

    results = research_tools.search_github_code(
        "def train language:python",
        limit=1,
        fetch_json=fake_fetch_json,
        token="test-token",
    )

    assert len(results) == 1
    assert results[0].source_type == "github_code"
    assert results[0].title == "org/repo:examples/train.py"
    assert results[0].url == "https://github.com/org/repo/blob/main/examples/train.py"
    assert results[0].summary == "def train(): pass"
    assert results[0].metadata["repository"] == "org/repo"
    assert results[0].metadata["path"] == "examples/train.py"
    assert results[0].metadata["score"] == 1.0

    query_params = parse_qs(urlparse(seen_urls[0]).query)
    assert query_params["q"] == ["def train language:python"]
    assert query_params["per_page"] == ["1"]
    assert seen_headers[0]["Accept"] == "application/vnd.github.text-match+json"
    assert seen_headers[0]["Authorization"] == "Bearer test-token"


def test_search_github_code_requires_auth_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def fake_fetch_json(url: str, headers: dict[str, str] | None = None):
        raise AssertionError(f"unexpected network call to {url} with {headers}")

    with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
        research_tools.search_github_code(
            "def train language:python",
            fetch_json=fake_fetch_json,
        )


def test_cached_search_reuses_json_cache(tmp_path) -> None:
    calls = 0

    def collect_sources():
        nonlocal calls
        calls += 1
        return [
            ResearchSource(
                source_type="paper",
                title="Cached Attention",
                url="https://arxiv.org/abs/2401.00001",
                summary="Cached result.",
            )
        ]

    first_sources, first_meta = research_tools.cached_search(
        cache_dir=tmp_path / "research-cache",
        namespace="papers",
        query="cached attention",
        limit=1,
        collect=collect_sources,
    )
    second_sources, second_meta = research_tools.cached_search(
        cache_dir=tmp_path / "research-cache",
        namespace="papers",
        query="cached attention",
        limit=1,
        collect=collect_sources,
    )

    assert calls == 1
    assert first_sources[0].title == "Cached Attention"
    assert second_sources[0].title == "Cached Attention"
    assert first_meta["hit"] is False
    assert second_meta["hit"] is True
    assert second_meta["source"] == "cache"
    assert second_meta["cache_file"].endswith(".json")


def test_cached_search_refreshes_corrupt_cache(tmp_path) -> None:
    calls = 0
    cache_dir = tmp_path / "research-cache"

    def collect_sources():
        nonlocal calls
        calls += 1
        return [
            ResearchSource(
                source_type="paper",
                title="Recovered Cache",
                url="https://arxiv.org/abs/2401.00002",
                summary="Recovered from a corrupt cache file.",
            )
        ]

    _, first_meta = research_tools.cached_search(
        cache_dir=cache_dir,
        namespace="papers",
        query="recover cache",
        limit=1,
        collect=collect_sources,
    )
    Path(first_meta["cache_file"]).write_text("{bad json", encoding="utf-8")

    recovered_sources, recovered_meta = research_tools.cached_search(
        cache_dir=cache_dir,
        namespace="papers",
        query="recover cache",
        limit=1,
        collect=collect_sources,
    )

    assert calls == 2
    assert recovered_sources[0].title == "Recovered Cache"
    assert recovered_meta["hit"] is False
    assert recovered_meta["source"] == "live"
    assert "cache_error" in recovered_meta


def test_cached_search_returns_live_sources_when_cache_write_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    def fail_write_text(self, *args, **kwargs):
        del self, args, kwargs
        raise OSError("read-only cache")

    monkeypatch.setattr(Path, "write_text", fail_write_text)

    sources, meta = research_tools.cached_search(
        cache_dir=tmp_path / "research-cache",
        namespace="papers",
        query="live despite cache failure",
        limit=1,
        collect=lambda: [
            ResearchSource(
                source_type="paper",
                title="Live Source",
                url="https://arxiv.org/abs/2401.00003",
                summary="Live result despite cache failure.",
            )
        ],
    )

    assert sources[0].title == "Live Source"
    assert meta["source"] == "live"
    assert meta["hit"] is False
    assert meta["cache_error"] == "read-only cache"
