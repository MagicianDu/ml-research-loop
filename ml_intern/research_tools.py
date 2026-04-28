"""ml-intern research tool adapters for fusion workflows."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from lib.research_protocol import ResearchSource

ARXIV_API_URL = "http://export.arxiv.org/api/query"
GITHUB_CODE_SEARCH_URL = "https://api.github.com/search/code"
GITHUB_API_VERSION = os.environ.get("GITHUB_API_VERSION", "2026-03-10")
DEFAULT_USER_AGENT = "ml-research-loop/0.1"
DEFAULT_TIMEOUT_SECONDS = 20
MAX_RESULT_LIMIT = 20

TextFetcher = Callable[[str, Mapping[str, str] | None], str]
JsonFetcher = Callable[[str, Mapping[str, str] | None], Any]


def normalize_paper_result(data: dict) -> ResearchSource:
    """Normalize a paper search/read result into a research source."""
    return ResearchSource(
        source_type="paper",
        title=data.get("title", ""),
        url=data.get("url", ""),
        summary=data.get("summary", data.get("abstract", "")),
        metadata={
            key: value
            for key, value in data.items()
            if key not in {"title", "url", "summary", "abstract"}
        },
    )


def normalize_dataset_result(data: dict) -> ResearchSource:
    """Normalize a Hugging Face dataset result into a research source."""
    dataset_id = data.get("id", data.get("dataset_id", ""))
    return ResearchSource(
        source_type="hf_dataset",
        title=dataset_id,
        url=f"https://huggingface.co/datasets/{dataset_id}" if dataset_id else "",
        summary=data.get("description", ""),
        metadata={
            key: value
            for key, value in {
                "dataset_id": dataset_id,
                "downloads": data.get("downloads"),
                "likes": data.get("likes"),
                "tags": data.get("tags"),
            }.items()
            if value is not None
        },
    )


def search_papers(
    query: str,
    limit: int = 5,
    fetch_text: TextFetcher | None = None,
) -> list[ResearchSource]:
    """Search papers and return normalized sources.

    Uses arXiv's public Atom API. `fetch_text` is injectable so tests and MCP
    callers can keep behavior deterministic when needed.
    """
    query = query.strip()
    if not query:
        return []

    fetch = fetch_text or _http_get_text
    bounded_limit = _clamp_limit(limit)
    query_params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": bounded_limit,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API_URL}?{urlencode(query_params)}"
    return _parse_arxiv_feed(fetch(url, _default_headers()))[:bounded_limit]


def read_paper(
    identifier: str,
    fetch_text: TextFetcher | None = None,
) -> ResearchSource:
    """Read one paper's metadata by arXiv ID or arXiv URL."""
    arxiv_id = _extract_arxiv_id(identifier)
    if not arxiv_id:
        raise ValueError(f"Unsupported paper identifier: {identifier}")

    fetch = fetch_text or _http_get_text
    url = f"{ARXIV_API_URL}?{urlencode({'id_list': arxiv_id})}"
    results = _parse_arxiv_feed(fetch(url, _default_headers()))
    if not results:
        raise ValueError(f"No paper metadata found for arXiv ID: {arxiv_id}")
    return results[0]


def search_hf_datasets(query: str, limit: int = 5, api: Any = None) -> list[ResearchSource]:
    """Search Hugging Face datasets and return normalized sources."""
    query = query.strip()
    if not query:
        return []

    bounded_limit = _clamp_limit(limit)
    hub_api = api or _create_hf_api()
    dataset_infos = hub_api.list_datasets(search=query, limit=bounded_limit)
    return [
        normalize_dataset_result(_dataset_info_to_dict(dataset_info))
        for dataset_info in dataset_infos
    ][:bounded_limit]


def search_github_code(
    query: str,
    limit: int = 5,
    fetch_json: JsonFetcher | None = None,
    token: str | None = None,
) -> list[ResearchSource]:
    """Search GitHub code and return normalized sources."""
    query = query.strip()
    if not query:
        return []

    fetch = fetch_json or _http_get_json
    bounded_limit = _clamp_limit(limit)
    url = f"{GITHUB_CODE_SEARCH_URL}?{urlencode({'q': query, 'per_page': bounded_limit})}"
    api_token = token or os.environ.get("GITHUB_TOKEN")
    if not api_token:
        raise RuntimeError("GITHUB_TOKEN is required for GitHub code search.")

    payload = fetch(url, _github_headers(api_token))
    return [
        normalize_github_code_result(item)
        for item in payload.get("items", [])
    ][:bounded_limit]


def normalize_github_code_result(data: dict[str, Any]) -> ResearchSource:
    """Normalize a GitHub code search item into a research source."""
    repository = data.get("repository", {}) or {}
    repo_name = repository.get("full_name", "")
    path = data.get("path", data.get("name", ""))
    text_matches = data.get("text_matches", []) or []
    fragment = text_matches[0].get("fragment", "") if text_matches else ""
    return ResearchSource(
        source_type="github_code",
        title=f"{repo_name}:{path}" if repo_name and path else data.get("name", ""),
        url=data.get("html_url", ""),
        summary=fragment,
        metadata={
            key: value
            for key, value in {
                "repository": repo_name,
                "repository_url": repository.get("html_url"),
                "path": path,
                "score": data.get("score"),
            }.items()
            if value not in {None, ""}
        },
    )


def _http_get_text(
    url: str,
    headers: Mapping[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    request = Request(url, headers=dict(headers or {}))
    with urlopen(request, timeout=timeout) as response:
        encoding = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(encoding)


def _http_get_json(url: str, headers: Mapping[str, str] | None = None) -> Any:
    return json.loads(_http_get_text(url, headers))


def _default_headers() -> dict[str, str]:
    return {"User-Agent": DEFAULT_USER_AGENT}


def _github_headers(token: str | None = None) -> dict[str, str]:
    api_token = token or os.environ.get("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github.text-match+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": DEFAULT_USER_AGENT,
    }
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    return headers


def _clamp_limit(limit: int) -> int:
    return max(1, min(int(limit), MAX_RESULT_LIMIT))


def _parse_arxiv_feed(feed_xml: str) -> list[ResearchSource]:
    root = ElementTree.fromstring(feed_xml)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    sources: list[ResearchSource] = []
    for entry in root.findall("atom:entry", namespace):
        url = _entry_text(entry, "id", namespace)
        summary = _normalize_space(_entry_text(entry, "summary", namespace))
        title = _normalize_space(_entry_text(entry, "title", namespace))
        arxiv_id = _extract_arxiv_id(url)
        sources.append(
            normalize_paper_result({
                "title": title,
                "url": url,
                "summary": summary,
                "arxiv_id": arxiv_id,
                "authors": [
                    _normalize_space(author.findtext("atom:name", default="", namespaces=namespace))
                    for author in entry.findall("atom:author", namespace)
                    if author.findtext("atom:name", default="", namespaces=namespace)
                ],
                "published": _entry_text(entry, "published", namespace),
                "updated": _entry_text(entry, "updated", namespace),
                "pdf_url": _entry_pdf_url(entry, namespace),
            })
        )
    return sources


def _entry_text(
    entry: ElementTree.Element,
    tag: str,
    namespace: dict[str, str],
) -> str:
    return entry.findtext(f"atom:{tag}", default="", namespaces=namespace)


def _entry_pdf_url(entry: ElementTree.Element, namespace: dict[str, str]) -> str:
    for link in entry.findall("atom:link", namespace):
        if link.attrib.get("title") == "pdf":
            return link.attrib.get("href", "")
    return ""


def _extract_arxiv_id(identifier: str) -> str:
    match = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?", identifier)
    return match.group(1) if match else identifier.strip()


def _normalize_space(value: str) -> str:
    return " ".join(value.split())


def _create_hf_api() -> Any:
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is required for live Hugging Face dataset search."
        ) from exc
    return HfApi()


def _dataset_info_to_dict(dataset_info: Any) -> dict[str, Any]:
    if isinstance(dataset_info, dict):
        return dataset_info
    return {
        "id": _attr(dataset_info, "id") or _attr(dataset_info, "dataset_id"),
        "description": _attr(dataset_info, "description") or "",
        "downloads": _attr(dataset_info, "downloads"),
        "likes": _attr(dataset_info, "likes"),
        "tags": _attr(dataset_info, "tags"),
    }


def _attr(value: Any, name: str) -> Any:
    return getattr(value, name, None)
