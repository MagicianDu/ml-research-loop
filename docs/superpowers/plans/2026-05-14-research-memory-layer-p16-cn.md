# Research Memory Layer P16 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Research Memory Layer so ML Research Loop can reuse past paper reproduction, experiment, patch, failure, rollback, and proof-bundle experience without making Graphiti/cognee default runtime dependencies.

**Architecture:** Implement a dependency-free local memory baseline first, centered on project-owned `ResearchMemoryCard`, `MemoryEvidenceRef`, `MemoryArtifactRef`, `MemorySuggestion`, and `MemoryTrace` schemas in `lib/research_memory.py`. Then add optional Graphiti/cognee adapters behind a stable adapter interface, expose only project-owned memory views through MCP/CLI, and bind retrieval/recording into Skills and release checks. Runtime Artifacts and proof archives remain the factual source; memory suggestions are advisory and never execute patches or experiments directly.

**Tech Stack:** Python stdlib (`dataclasses`, `json`, `pathlib`, `hashlib`, `time`, `typing`), existing MCP service in `lib/mcp_service.py`, existing CLI in `scripts/cli.py`, pytest, ruff, optional imports for Graphiti/cognee adapters, existing release gate in `scripts/release_check.py`.

---

## Product Target

P16 turns the newly documented canonical architecture into runnable product capability:

- Codex/Claude can ask: "Have we seen a similar paper/task/dataset/metric/failure before?"
- ML Research Loop can answer with provenance-backed memory cards and artifact refs.
- Codex/Claude can ask for suggestions, but suggestions remain advisory.
- Useful and failed rounds can be recorded after review/proof generation.
- Fresh checkout remains dependency-free; Graphiti/cognee are optional adapters.

## Constraints

- Graphiti/cognee must not be required for `pip install -e ".[dev]"`, `ml-loop check`, or `scripts/release_check.py --json`.
- Memory records must cite artifacts, proof bundles, logs, review reports, or evidence refs; no standalone natural-language memory can be promoted to reusable proof.
- Memory suggestions cannot call `run_client_patch_experiment`, `apply_client_code_patch`, `run_hypothesis_experiment`, benchmark tools, cleanup tools, or archive tools.
- MCP tools must use existing allowed-root/path-sandbox behavior before reading or writing memory stores outside the project root.
- Private papers, private datasets, and sensitive logs require explicit opt-in metadata before ingestion.
- All benchmark/reproduction memories must preserve claim boundaries such as `official_scores_claimed=false`.
- Release gate must cover dependency-free local memory behavior; Graphiti/cognee checks must be optional and skipped clearly when dependencies are absent.

## Acceptance Criteria

- `lib/research_memory.py` defines the canonical memory schema and local JSONL store.
- Existing fastText P3/P4/P5 proof artifacts can be converted into memory cards without Graphiti/cognee installed.
- Retrieval supports at least paper id, dataset, model family, metric name, patch type, failure category, and free-text query.
- Suggestions return `MemorySuggestion` objects with `provenance`, `confidence`, `known_failures`, `claim_boundary`, and `recommended_mcp_tool` or `recommended_human_action`.
- `audit_memory_trace` explains which memory cards and artifacts support a suggestion.
- MCP exposes `record_research_memory`, `retrieve_research_memory`, `suggest_from_memory`, `promote_memory_card`, and `audit_memory_trace` only after tests cover contracts.
- CLI exposes memory commands for local operation and demo use.
- Skills and planner docs say to retrieve memory before proposing new experiments and record memory after reviewed runs when tools are available.
- Release gate includes a dependency-free local memory smoke test.
- Full verification passes: `ruff`, targeted memory tests, MCP/CLI tests, doc/skill tests, and `scripts/release_check.py --json`.

## Test Strategy

- Unit tests cover schema serialization, validation, local JSONL append/read/search, artifact hash calculation, sensitive input rejection, suggestion construction, and audit trace.
- Unit tests cover optional adapter behavior with missing Graphiti/cognee modules.
- MCP unit tests cover input schemas, allowed-root handling, tool results, and no-execution guarantee.
- CLI unit tests cover `ml-loop memory ...` commands.
- Integration smoke covers extracting fastText proof artifacts into a local memory store and retrieving a suggestion.
- Release gate includes the dependency-free smoke only; optional adapter checks are explicitly separate.

## File Map

- Create `lib/research_memory.py`: canonical dataclasses, validation, local JSONL store, extraction helpers, retrieval, suggestion, audit trace.
- Create `lib/memory_adapters/__init__.py`: adapter protocol and registry.
- Create `lib/memory_adapters/graphiti_adapter.py`: optional Graphiti adapter with graceful missing-dependency handling.
- Create `lib/memory_adapters/cognee_adapter.py`: optional cognee adapter with graceful missing-dependency handling.
- Create `scripts/memory_smoke.py`: dependency-free smoke used by release gate.
- Modify `lib/mcp_service.py`: add memory tool schemas and handlers.
- Modify `scripts/cli.py`: add `ml-loop memory ...` commands.
- Modify `scripts/release_check.py`: add `research-memory-smoke` check.
- Modify `skills/`, `docs/client-planner-template.md`, `docs/skills-setup-cn.md`, `docs/mcp-client-setup.md`: document new workflows.
- Modify `docs/product/research-memory-layer-cn.md`, `docs/productization-todos.md`, `docs/release-checklist.md`, `SECURITY.md`: update product and safety docs.
- Create `tests/unit/test_research_memory.py`: schema, store, extraction, retrieval, suggestion, privacy tests.
- Create `tests/unit/test_memory_adapters.py`: adapter protocol and missing optional dependency tests.
- Modify `tests/unit/test_mcp_service.py`: memory MCP contracts.
- Modify `tests/unit/test_cli.py`: memory CLI commands.
- Modify `tests/unit/test_release_check.py`: release gate includes memory smoke.
- Modify `tests/unit/test_mcp_delivery_docs.py`, `tests/unit/test_planner_docs.py`, `tests/unit/test_skill_packages.py`: docs and skills stay aligned.

---

### Task 1: Canonical Schema And Local Store

**Files:**
- Create: `lib/research_memory.py`
- Create: `tests/unit/test_research_memory.py`

- [ ] **Step 1: Write failing schema/store tests**

Add this to `tests/unit/test_research_memory.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.research_memory import (
    MemoryArtifactRef,
    MemoryEvidenceRef,
    ResearchMemoryCard,
    ResearchMemoryStore,
)


def test_memory_card_round_trips_with_artifact_provenance(tmp_path: Path) -> None:
    artifact = tmp_path / "improvement-report.json"
    artifact.write_text('{"p_at_1": 0.916}', encoding="utf-8")
    card = ResearchMemoryCard(
        card_id="mem-fasttext-wordngrams-2",
        memory_type="patch",
        task_family="text-classification",
        summary="fastText AG News wordNgrams=2 improved local P@1.",
        paper_ids=["arxiv:1607.01759"],
        datasets=["AG News"],
        model_family="fastText",
        metric_name="P@1",
        metric_before=0.914,
        metric_after=0.916,
        patch_type="hyperparameter",
        config={"wordNgrams": 2},
        evidence_refs=[
            MemoryEvidenceRef(
                source_id="fasttext-p5-release",
                quote="Local proof only; not a leaderboard score.",
                strength="runtime_artifact",
            )
        ],
        artifact_refs=[MemoryArtifactRef.from_path("improvement_report", artifact)],
        claim_boundary="local proof only; official_scores_claimed=false",
        official_scores_claimed=False,
        tags=["fasttext", "ag-news", "patch"],
    )

    payload = card.to_dict()
    restored = ResearchMemoryCard.from_dict(payload)

    assert restored.card_id == "mem-fasttext-wordngrams-2"
    assert restored.artifact_refs[0].sha256
    assert restored.official_scores_claimed is False
    assert restored.metric_after == 0.916


def test_store_appends_and_searches_cards(tmp_path: Path) -> None:
    artifact = tmp_path / "proof-manifest.json"
    artifact.write_text(json.dumps({"official_scores_claimed": False}), encoding="utf-8")
    store = ResearchMemoryStore(tmp_path / "memory.jsonl")
    card = ResearchMemoryCard(
        card_id="mem-fasttext-proof",
        memory_type="evidence",
        task_family="text-classification",
        summary="fastText AG News release proof bundle was reviewed with limitations.",
        paper_ids=["arxiv:1607.01759"],
        datasets=["AG News"],
        model_family="fastText",
        metric_name="P@1",
        artifact_refs=[MemoryArtifactRef.from_path("proof_manifest", artifact)],
        claim_boundary="reviewed local release proof bundle only",
        official_scores_claimed=False,
        tags=["proof", "release", "ag-news"],
    )

    store.append(card)
    matches = store.search(query="AG News proof", paper_id="arxiv:1607.01759")

    assert [match.card.card_id for match in matches] == ["mem-fasttext-proof"]
    assert matches[0].score > 0
    assert "paper_id" in matches[0].reasons


def test_memory_card_rejects_private_material_without_opt_in(tmp_path: Path) -> None:
    artifact = tmp_path / "private-log.txt"
    artifact.write_text("private user dataset path", encoding="utf-8")

    with pytest.raises(ValueError, match="private"):
        ResearchMemoryCard(
            card_id="mem-private",
            memory_type="failure",
            task_family="private-task",
            summary="Private run failed.",
            artifact_refs=[MemoryArtifactRef.from_path("log", artifact)],
            privacy_scope="private",
            allow_private_ingestion=False,
        )
```

- [ ] **Step 2: Run schema/store tests to verify they fail**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_memory.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'lib.research_memory'`.

- [ ] **Step 3: Implement schema and local JSONL store**

Create `lib/research_memory.py` with:

```python
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


MemoryType = Literal["evidence", "experiment", "patch", "failure", "procedure"]


def _now() -> float:
    return time.time()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class MemoryEvidenceRef:
    source_id: str
    artifact_path: str | None = None
    quote: str | None = None
    strength: str = "runtime_artifact"
    url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryEvidenceRef":
        return cls(**payload)


@dataclass(frozen=True)
class MemoryArtifactRef:
    name: str
    path: str
    sha256: str
    artifact_type: str = "runtime_artifact"

    @classmethod
    def from_path(cls, name: str, path: str | Path, artifact_type: str = "runtime_artifact") -> "MemoryArtifactRef":
        resolved = Path(path)
        return cls(
            name=name,
            path=str(resolved),
            sha256=_sha256(resolved),
            artifact_type=artifact_type,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryArtifactRef":
        return cls(**payload)


@dataclass(frozen=True)
class ResearchMemoryCard:
    card_id: str
    memory_type: MemoryType
    task_family: str
    summary: str
    paper_ids: list[str] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    model_family: str | None = None
    metric_name: str | None = None
    metric_before: float | None = None
    metric_after: float | None = None
    patch_type: str | None = None
    failure_category: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[MemoryEvidenceRef] = field(default_factory=list)
    artifact_refs: list[MemoryArtifactRef] = field(default_factory=list)
    claim_boundary: str = "local memory only; not public proof"
    official_scores_claimed: bool = False
    privacy_scope: str = "public"
    allow_private_ingestion: bool = False
    promoted: bool = False
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=_now)

    def __post_init__(self) -> None:
        if self.privacy_scope != "public" and not self.allow_private_ingestion:
            raise ValueError("private memory ingestion requires explicit opt-in")
        if self.official_scores_claimed:
            raise ValueError("memory cards must not claim official scores")
        if not self.artifact_refs and self.memory_type != "procedure":
            raise ValueError("non-procedure memory cards require artifact_refs")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_refs"] = [item.to_dict() for item in self.evidence_refs]
        payload["artifact_refs"] = [item.to_dict() for item in self.artifact_refs]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResearchMemoryCard":
        data = dict(payload)
        data["evidence_refs"] = [
            MemoryEvidenceRef.from_dict(item) for item in data.get("evidence_refs", [])
        ]
        data["artifact_refs"] = [
            MemoryArtifactRef.from_dict(item) for item in data.get("artifact_refs", [])
        ]
        return cls(**data)


@dataclass(frozen=True)
class MemorySearchResult:
    card: ResearchMemoryCard
    score: float
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "card": self.card.to_dict(),
            "score": self.score,
            "reasons": list(self.reasons),
        }


class ResearchMemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, card: ResearchMemoryCard) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(card.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")

    def list_cards(self) -> list[ResearchMemoryCard]:
        if not self.path.exists():
            return []
        cards: list[ResearchMemoryCard] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cards.append(ResearchMemoryCard.from_dict(json.loads(line)))
        return cards

    def search(
        self,
        *,
        query: str | None = None,
        paper_id: str | None = None,
        dataset: str | None = None,
        metric_name: str | None = None,
        patch_type: str | None = None,
        failure_category: str | None = None,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        results: list[MemorySearchResult] = []
        query_terms = {term.lower() for term in (query or "").split() if term.strip()}
        for card in self.list_cards():
            score = 0.0
            reasons: list[str] = []
            haystack = " ".join(
                [
                    card.summary,
                    card.task_family,
                    card.model_family or "",
                    " ".join(card.paper_ids),
                    " ".join(card.datasets),
                    " ".join(card.tags),
                ]
            ).lower()
            if query_terms:
                overlap = sum(1 for term in query_terms if term in haystack)
                if overlap:
                    score += overlap
                    reasons.append("query")
            if paper_id and paper_id in card.paper_ids:
                score += 3
                reasons.append("paper_id")
            if dataset and dataset in card.datasets:
                score += 2
                reasons.append("dataset")
            if metric_name and metric_name == card.metric_name:
                score += 1.5
                reasons.append("metric_name")
            if patch_type and patch_type == card.patch_type:
                score += 1
                reasons.append("patch_type")
            if failure_category and failure_category == card.failure_category:
                score += 1
                reasons.append("failure_category")
            if score > 0:
                results.append(MemorySearchResult(card=card, score=score, reasons=reasons))
        return sorted(results, key=lambda item: item.score, reverse=True)[:limit]
```

- [ ] **Step 4: Run schema/store tests to verify they pass**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_memory.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/research_memory.py tests/unit/test_research_memory.py
git commit -m "Add research memory schema and store"
```

---

### Task 2: Extract Memory From Existing Proof Artifacts

**Files:**
- Modify: `lib/research_memory.py`
- Modify: `tests/unit/test_research_memory.py`

- [ ] **Step 1: Write failing fastText extraction test**

Add this to `tests/unit/test_research_memory.py`:

```python
def test_extract_fasttext_release_memory_cards(tmp_path: Path) -> None:
    proof_dir = tmp_path / "release-proof"
    proof_dir.mkdir()
    manifest = proof_dir / "release-proof-manifest.json"
    review = proof_dir / "release-review-checklist.md"
    multi_round = proof_dir / "multi-round-report.json"
    manifest.write_text(
        json.dumps(
            {
                "official_scores_claimed": False,
                "bundle_sha256": "abc123",
                "stage": "p5_fasttext_release_proof_bundle",
            }
        ),
        encoding="utf-8",
    )
    review.write_text("approved_with_limitations", encoding="utf-8")
    multi_round.write_text(
        json.dumps(
            {
                "paper_id": "arxiv:1607.01759",
                "baseline_p_at_1": 0.914,
                "best_metric": 0.916,
                "best_source": "round-001-wordngrams-2",
                "failure_count": 1,
                "rollback_summary": {"rollback_events": 1},
            }
        ),
        encoding="utf-8",
    )

    from lib.research_memory import extract_fasttext_release_memory_cards

    cards = extract_fasttext_release_memory_cards(
        release_manifest=manifest,
        multi_round_report=multi_round,
        review_checklist=review,
    )

    assert [card.memory_type for card in cards] == ["patch", "failure"]
    assert cards[0].paper_ids == ["arxiv:1607.01759"]
    assert cards[0].datasets == ["AG News"]
    assert cards[0].metric_before == 0.914
    assert cards[0].metric_after == 0.916
    assert cards[0].official_scores_claimed is False
    assert cards[1].failure_category == "invalid_or_failed_proposal"
```

- [ ] **Step 2: Run extraction test to verify it fails**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_memory.py::test_extract_fasttext_release_memory_cards -q
```

Expected: FAIL because `extract_fasttext_release_memory_cards` is not defined.

- [ ] **Step 3: Implement fastText extraction helper**

Add to `lib/research_memory.py`:

```python
def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_fasttext_release_memory_cards(
    *,
    release_manifest: str | Path,
    multi_round_report: str | Path,
    review_checklist: str | Path,
) -> list[ResearchMemoryCard]:
    manifest_path = Path(release_manifest)
    multi_round_path = Path(multi_round_report)
    review_path = Path(review_checklist)
    manifest = _read_json(manifest_path)
    multi_round = _read_json(multi_round_path)
    if manifest.get("official_scores_claimed") is not False:
        raise ValueError("fastText memory extraction requires official_scores_claimed=false")
    paper_id = str(multi_round.get("paper_id", "arxiv:1607.01759"))
    baseline = float(multi_round.get("baseline_p_at_1", 0.0))
    best = float(multi_round.get("best_metric", baseline))
    common_artifacts = [
        MemoryArtifactRef.from_path("release_manifest", manifest_path),
        MemoryArtifactRef.from_path("multi_round_report", multi_round_path),
        MemoryArtifactRef.from_path("review_checklist", review_path),
    ]
    patch_card = ResearchMemoryCard(
        card_id=f"mem-fasttext-{paper_id.replace(':', '-')}-best-patch",
        memory_type="patch",
        task_family="text-classification",
        summary="fastText AG News bounded client proposal improved local P@1.",
        paper_ids=[paper_id],
        datasets=["AG News"],
        model_family="fastText",
        metric_name="P@1",
        metric_before=baseline,
        metric_after=best,
        patch_type="hyperparameter",
        config={"best_source": multi_round.get("best_source")},
        evidence_refs=[
            MemoryEvidenceRef(
                source_id="fasttext-release-proof",
                artifact_path=str(manifest_path),
                quote="Local release proof bundle; not a leaderboard score.",
            )
        ],
        artifact_refs=common_artifacts,
        claim_boundary="local fastText proof only; official_scores_claimed=false",
        official_scores_claimed=False,
        tags=["fasttext", "ag-news", "patch", "proof"],
    )
    failure_card = ResearchMemoryCard(
        card_id=f"mem-fasttext-{paper_id.replace(':', '-')}-failed-proposals",
        memory_type="failure",
        task_family="text-classification",
        summary="fastText multi-proposal loop preserved failed or rejected proposals and rollback state.",
        paper_ids=[paper_id],
        datasets=["AG News"],
        model_family="fastText",
        metric_name="P@1",
        failure_category="invalid_or_failed_proposal",
        config={
            "failure_count": multi_round.get("failure_count", 0),
            "rollback_summary": multi_round.get("rollback_summary", {}),
        },
        evidence_refs=[
            MemoryEvidenceRef(
                source_id="fasttext-multi-round-report",
                artifact_path=str(multi_round_path),
                quote="Failed proposal records are audit evidence.",
            )
        ],
        artifact_refs=common_artifacts,
        claim_boundary="failure/rollback audit memory only",
        official_scores_claimed=False,
        tags=["fasttext", "ag-news", "failure", "rollback"],
    )
    return [patch_card, failure_card]
```

- [ ] **Step 4: Run extraction tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_memory.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/research_memory.py tests/unit/test_research_memory.py
git commit -m "Extract memory from fastText proof artifacts"
```

---

### Task 3: Suggestions And Audit Trace

**Files:**
- Modify: `lib/research_memory.py`
- Modify: `tests/unit/test_research_memory.py`

- [ ] **Step 1: Write failing suggestion/audit tests**

Add this to `tests/unit/test_research_memory.py`:

```python
def test_suggest_from_memory_includes_provenance_and_no_execution(tmp_path: Path) -> None:
    artifact = tmp_path / "multi-round-report.json"
    artifact.write_text(json.dumps({"best_metric": 0.916}), encoding="utf-8")
    store = ResearchMemoryStore(tmp_path / "memory.jsonl")
    store.append(
        ResearchMemoryCard(
            card_id="mem-fasttext-wordngrams",
            memory_type="patch",
            task_family="text-classification",
            summary="wordNgrams=2 improved local fastText AG News P@1.",
            paper_ids=["arxiv:1607.01759"],
            datasets=["AG News"],
            model_family="fastText",
            metric_name="P@1",
            metric_before=0.914,
            metric_after=0.916,
            patch_type="hyperparameter",
            artifact_refs=[MemoryArtifactRef.from_path("multi_round_report", artifact)],
            claim_boundary="local proof only",
            tags=["wordNgrams"],
        )
    )

    suggestions = store.suggest(
        query="fastText AG News improve P@1",
        paper_id="arxiv:1607.01759",
        dataset="AG News",
    )

    assert suggestions[0].suggestion_id == "suggest-mem-fasttext-wordngrams"
    assert suggestions[0].recommended_mcp_tool == "run_client_patch_experiment"
    assert suggestions[0].executes_tool is False
    assert suggestions[0].provenance[0]["card_id"] == "mem-fasttext-wordngrams"
    assert suggestions[0].claim_boundary == "local proof only"


def test_audit_memory_trace_explains_supporting_cards(tmp_path: Path) -> None:
    artifact = tmp_path / "review.json"
    artifact.write_text("{}", encoding="utf-8")
    store = ResearchMemoryStore(tmp_path / "memory.jsonl")
    store.append(
        ResearchMemoryCard(
            card_id="mem-debug-timeout",
            memory_type="failure",
            task_family="text-classification",
            summary="Timeout was fixed by reducing candidate count.",
            failure_category="timeout",
            artifact_refs=[MemoryArtifactRef.from_path("review", artifact)],
            claim_boundary="debug memory only",
        )
    )

    trace = store.audit_trace(["mem-debug-timeout"])

    assert trace.trace_id == "trace-1"
    assert trace.cards[0].card_id == "mem-debug-timeout"
    assert trace.artifact_refs[0].name == "review"
    assert trace.claim_boundaries == ["debug memory only"]
```

- [ ] **Step 2: Run suggestion/audit tests to verify they fail**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_memory.py::test_suggest_from_memory_includes_provenance_and_no_execution tests/unit/test_research_memory.py::test_audit_memory_trace_explains_supporting_cards -q
```

Expected: FAIL because `suggest` and `audit_trace` are missing.

- [ ] **Step 3: Implement suggestion and audit trace**

Add to `lib/research_memory.py`:

```python
@dataclass(frozen=True)
class MemorySuggestion:
    suggestion_id: str
    summary: str
    recommended_mcp_tool: str | None
    recommended_human_action: str | None
    confidence: float
    provenance: list[dict[str, Any]]
    known_failures: list[str]
    claim_boundary: str
    executes_tool: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryTrace:
    trace_id: str
    cards: list[ResearchMemoryCard]
    artifact_refs: list[MemoryArtifactRef]
    claim_boundaries: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "cards": [card.to_dict() for card in self.cards],
            "artifact_refs": [artifact.to_dict() for artifact in self.artifact_refs],
            "claim_boundaries": list(self.claim_boundaries),
        }
```

Add methods to `ResearchMemoryStore`:

```python
    def suggest(
        self,
        *,
        query: str,
        paper_id: str | None = None,
        dataset: str | None = None,
        limit: int = 5,
    ) -> list[MemorySuggestion]:
        suggestions: list[MemorySuggestion] = []
        for result in self.search(query=query, paper_id=paper_id, dataset=dataset, limit=limit):
            card = result.card
            recommended_tool = None
            if card.memory_type == "patch":
                recommended_tool = "run_client_patch_experiment"
            elif card.memory_type == "failure":
                recommended_tool = "get_experiment_logs"
            confidence = min(0.95, 0.35 + result.score / 10)
            suggestions.append(
                MemorySuggestion(
                    suggestion_id=f"suggest-{card.card_id}",
                    summary=card.summary,
                    recommended_mcp_tool=recommended_tool,
                    recommended_human_action=None if recommended_tool else "review_memory_card",
                    confidence=confidence,
                    provenance=[{"card_id": card.card_id, "reasons": result.reasons}],
                    known_failures=[card.failure_category] if card.failure_category else [],
                    claim_boundary=card.claim_boundary,
                    executes_tool=False,
                )
            )
        return suggestions

    def audit_trace(self, card_ids: list[str]) -> MemoryTrace:
        cards_by_id = {card.card_id: card for card in self.list_cards()}
        cards = [cards_by_id[card_id] for card_id in card_ids if card_id in cards_by_id]
        artifact_refs: list[MemoryArtifactRef] = []
        claim_boundaries: list[str] = []
        for card in cards:
            artifact_refs.extend(card.artifact_refs)
            claim_boundaries.append(card.claim_boundary)
        return MemoryTrace(
            trace_id=f"trace-{len(cards)}",
            cards=cards,
            artifact_refs=artifact_refs,
            claim_boundaries=claim_boundaries,
        )
```

- [ ] **Step 4: Run all memory tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_memory.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/research_memory.py tests/unit/test_research_memory.py
git commit -m "Add memory suggestions and audit traces"
```

---

### Task 4: Optional Graphiti And cognee Adapter Interfaces

**Files:**
- Create: `lib/memory_adapters/__init__.py`
- Create: `lib/memory_adapters/graphiti_adapter.py`
- Create: `lib/memory_adapters/cognee_adapter.py`
- Create: `tests/unit/test_memory_adapters.py`

- [ ] **Step 1: Write failing adapter tests**

Create `tests/unit/test_memory_adapters.py`:

```python
from __future__ import annotations

from lib.memory_adapters import AdapterStatus, get_memory_adapter_status
from lib.memory_adapters.cognee_adapter import CogneeMemoryAdapter
from lib.memory_adapters.graphiti_adapter import GraphitiMemoryAdapter


def test_missing_optional_adapters_report_skipped_status() -> None:
    statuses = get_memory_adapter_status()

    assert set(statuses) == {"graphiti", "cognee"}
    for status in statuses.values():
        assert isinstance(status, AdapterStatus)
        assert status.name in {"graphiti", "cognee"}
        assert status.enabled is False
        assert status.required is False
        assert status.reason


def test_adapters_return_project_owned_views_when_disabled() -> None:
    graphiti = GraphitiMemoryAdapter()
    cognee = CogneeMemoryAdapter()

    assert graphiti.is_available() is False
    assert cognee.is_available() is False
    assert graphiti.search(query="fastText") == []
    assert cognee.search(query="proof bundle") == []
```

- [ ] **Step 2: Run adapter tests to verify they fail**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_memory_adapters.py -q
```

Expected: FAIL because `lib.memory_adapters` does not exist.

- [ ] **Step 3: Implement adapter protocol and graceful missing-dependency adapters**

Create `lib/memory_adapters/__init__.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from lib.research_memory import ResearchMemoryCard


@dataclass(frozen=True)
class AdapterStatus:
    name: str
    enabled: bool
    required: bool
    reason: str


class MemoryAdapter(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def search(self, *, query: str, limit: int = 10) -> list[ResearchMemoryCard]: ...

    def upsert(self, card: ResearchMemoryCard) -> dict[str, object]: ...


def get_memory_adapter_status() -> dict[str, AdapterStatus]:
    from lib.memory_adapters.cognee_adapter import CogneeMemoryAdapter
    from lib.memory_adapters.graphiti_adapter import GraphitiMemoryAdapter

    adapters = [GraphitiMemoryAdapter(), CogneeMemoryAdapter()]
    return {
        adapter.name: AdapterStatus(
            name=adapter.name,
            enabled=adapter.is_available(),
            required=False,
            reason="available" if adapter.is_available() else "optional dependency not installed",
        )
        for adapter in adapters
    }
```

Create `lib/memory_adapters/graphiti_adapter.py`:

```python
from __future__ import annotations

from lib.research_memory import ResearchMemoryCard


class GraphitiMemoryAdapter:
    name = "graphiti"

    def __init__(self) -> None:
        try:
            import graphiti_core  # type: ignore  # noqa: F401
        except Exception:
            self._available = False
        else:
            self._available = True

    def is_available(self) -> bool:
        return self._available

    def search(self, *, query: str, limit: int = 10) -> list[ResearchMemoryCard]:
        return []

    def upsert(self, card: ResearchMemoryCard) -> dict[str, object]:
        if not self.is_available():
            return {"status": "skipped", "adapter": self.name, "reason": "optional dependency not installed"}
        return {"status": "not_implemented", "adapter": self.name, "card_id": card.card_id}
```

Create `lib/memory_adapters/cognee_adapter.py`:

```python
from __future__ import annotations

from lib.research_memory import ResearchMemoryCard


class CogneeMemoryAdapter:
    name = "cognee"

    def __init__(self) -> None:
        try:
            import cognee  # type: ignore  # noqa: F401
        except Exception:
            self._available = False
        else:
            self._available = True

    def is_available(self) -> bool:
        return self._available

    def search(self, *, query: str, limit: int = 10) -> list[ResearchMemoryCard]:
        return []

    def upsert(self, card: ResearchMemoryCard) -> dict[str, object]:
        if not self.is_available():
            return {"status": "skipped", "adapter": self.name, "reason": "optional dependency not installed"}
        return {"status": "not_implemented", "adapter": self.name, "card_id": card.card_id}
```

- [ ] **Step 4: Run adapter tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_memory_adapters.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/memory_adapters tests/unit/test_memory_adapters.py
git commit -m "Add optional memory adapter interfaces"
```

---

### Task 5: CLI Memory Commands And Smoke Script

**Files:**
- Create: `scripts/memory_smoke.py`
- Modify: `scripts/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Add to `tests/unit/test_cli.py`:

```python
def test_memory_record_and_retrieve_cli(tmp_path, capsys):
    manifest = tmp_path / "release-proof-manifest.json"
    report = tmp_path / "multi-round-report.json"
    review = tmp_path / "release-review-checklist.md"
    store = tmp_path / "memory.jsonl"
    manifest.write_text('{"official_scores_claimed": false}', encoding="utf-8")
    report.write_text(
        '{"paper_id": "arxiv:1607.01759", "baseline_p_at_1": 0.914, "best_metric": 0.916}',
        encoding="utf-8",
    )
    review.write_text("approved_with_limitations", encoding="utf-8")

    exit_code = main(
        [
            "memory",
            "record-fasttext-release",
            "--store",
            str(store),
            "--release-manifest",
            str(manifest),
            "--multi-round-report",
            str(report),
            "--review-checklist",
            str(review),
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "recorded"
    assert payload["card_count"] == 2

    exit_code = main(
        [
            "memory",
            "retrieve",
            "--store",
            str(store),
            "--query",
            "AG News",
            "--paper-id",
            "arxiv:1607.01759",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["matches"][0]["card"]["paper_ids"] == ["arxiv:1607.01759"]
```

- [ ] **Step 2: Run CLI test to verify it fails**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_cli.py::test_memory_record_and_retrieve_cli -q
```

Expected: FAIL because `memory` subcommand is missing.

- [ ] **Step 3: Add memory CLI commands**

In `scripts/cli.py`, import the memory helpers and add subcommands:

```python
from lib.research_memory import (
    ResearchMemoryStore,
    extract_fasttext_release_memory_cards,
)
```

Add parser setup:

```python
memory_parser = subparsers.add_parser("memory")
memory_subparsers = memory_parser.add_subparsers(dest="memory_command", required=True)

record_fasttext = memory_subparsers.add_parser("record-fasttext-release")
record_fasttext.add_argument("--store", required=True)
record_fasttext.add_argument("--release-manifest", required=True)
record_fasttext.add_argument("--multi-round-report", required=True)
record_fasttext.add_argument("--review-checklist", required=True)

retrieve = memory_subparsers.add_parser("retrieve")
retrieve.add_argument("--store", required=True)
retrieve.add_argument("--query", required=True)
retrieve.add_argument("--paper-id")
retrieve.add_argument("--dataset")
retrieve.add_argument("--limit", type=int, default=10)
```

Add command handling:

```python
if args.command == "memory" and args.memory_command == "record-fasttext-release":
    store = ResearchMemoryStore(args.store)
    cards = extract_fasttext_release_memory_cards(
        release_manifest=args.release_manifest,
        multi_round_report=args.multi_round_report,
        review_checklist=args.review_checklist,
    )
    for card in cards:
        store.append(card)
    print(json.dumps({"status": "recorded", "card_count": len(cards)}, ensure_ascii=False))
    return 0

if args.command == "memory" and args.memory_command == "retrieve":
    store = ResearchMemoryStore(args.store)
    matches = store.search(
        query=args.query,
        paper_id=args.paper_id,
        dataset=args.dataset,
        limit=args.limit,
    )
    print(json.dumps({"status": "completed", "matches": [item.to_dict() for item in matches]}, ensure_ascii=False))
    return 0
```

Create `scripts/memory_smoke.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.research_memory import ResearchMemoryStore, extract_fasttext_release_memory_cards


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = output_dir / "release-proof-manifest.json"
    report = output_dir / "multi-round-report.json"
    review = output_dir / "release-review-checklist.md"
    store_path = output_dir / "memory.jsonl"
    manifest.write_text(json.dumps({"official_scores_claimed": False}), encoding="utf-8")
    report.write_text(
        json.dumps(
            {
                "paper_id": "arxiv:1607.01759",
                "baseline_p_at_1": 0.914,
                "best_metric": 0.916,
                "failure_count": 1,
                "rollback_summary": {"rollback_events": 1},
            }
        ),
        encoding="utf-8",
    )
    review.write_text("approved_with_limitations", encoding="utf-8")
    store = ResearchMemoryStore(store_path)
    for card in extract_fasttext_release_memory_cards(
        release_manifest=manifest,
        multi_round_report=report,
        review_checklist=review,
    ):
        store.append(card)
    matches = store.search(query="AG News", paper_id="arxiv:1607.01759")
    payload = {
        "status": "passed" if matches else "failed",
        "store": str(store_path),
        "match_count": len(matches),
        "official_scores_claimed": False,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI and smoke tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_cli.py::test_memory_record_and_retrieve_cli -q
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 scripts/memory_smoke.py --output-dir .demo_runs/memory-smoke
```

Expected: pytest PASS and smoke JSON has `"status": "passed"`.

- [ ] **Step 5: Commit**

```bash
git add scripts/cli.py scripts/memory_smoke.py tests/unit/test_cli.py
git commit -m "Add memory CLI and smoke test"
```

---

### Task 6: MCP Memory Tools

**Files:**
- Modify: `lib/mcp_service.py`
- Modify: `tests/unit/test_mcp_service.py`
- Modify: `tests/integration/test_mcp_server_stdio.py`

- [ ] **Step 1: Write failing MCP unit tests**

Add tests to `tests/unit/test_mcp_service.py` following existing MCP tool-call helper patterns:

```python
def test_memory_tools_are_listed_in_manifest() -> None:
    payload = get_service_manifest()

    for tool in [
        "record_research_memory",
        "retrieve_research_memory",
        "suggest_from_memory",
        "promote_memory_card",
        "audit_memory_trace",
    ]:
        assert tool in payload["tool_contracts"]
    assert "research_memory" in payload["planning_signals"]


def test_retrieve_research_memory_returns_provenance(tmp_path: Path) -> None:
    store = tmp_path / "memory.jsonl"
    artifact = tmp_path / "proof.json"
    artifact.write_text('{"official_scores_claimed": false}', encoding="utf-8")
    ResearchMemoryStore(store).append(
        ResearchMemoryCard(
            card_id="mem-proof",
            memory_type="evidence",
            task_family="text-classification",
            summary="AG News proof memory.",
            paper_ids=["arxiv:1607.01759"],
            datasets=["AG News"],
            artifact_refs=[MemoryArtifactRef.from_path("proof", artifact)],
        )
    )

    payload = retrieve_research_memory(
        {"store": str(store), "query": "AG News", "paper_id": "arxiv:1607.01759"}
    )

    assert payload["status"] == "completed"
    assert payload["matches"][0]["card"]["card_id"] == "mem-proof"
    assert payload["matches"][0]["card"]["artifact_refs"][0]["sha256"]
```

- [ ] **Step 2: Run MCP tests to verify they fail**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_mcp_service.py::test_memory_tools_are_listed_in_manifest tests/unit/test_mcp_service.py::test_retrieve_research_memory_returns_provenance -q
```

Expected: FAIL because memory MCP tools are missing.

- [ ] **Step 3: Implement MCP tool schemas and handlers**

In `lib/mcp_service.py`, add schemas and handlers that wrap `ResearchMemoryStore`. The handlers must:

```python
def retrieve_research_memory(arguments: dict[str, Any]) -> dict[str, Any]:
    store = ResearchMemoryStore(arguments["store"])
    matches = store.search(
        query=arguments.get("query"),
        paper_id=arguments.get("paper_id"),
        dataset=arguments.get("dataset"),
        metric_name=arguments.get("metric_name"),
        patch_type=arguments.get("patch_type"),
        failure_category=arguments.get("failure_category"),
        limit=arguments.get("limit", 10),
    )
    return {
        "status": "completed",
        "matches": [match.to_dict() for match in matches],
        "executes_tool": False,
        "claim_boundary": "memory retrieval only; not proof",
    }
```

Implement equivalent wrappers:

- `record_research_memory`: accept a card dict or fastText release artifact paths, append cards, return card IDs.
- `suggest_from_memory`: call `store.suggest(...)`, return suggestions with `executes_tool=false`.
- `promote_memory_card`: mark a card as `promoted=true` by writing a new promoted copy; do not mutate old lines.
- `audit_memory_trace`: call `store.audit_trace(card_ids)`.

Add tool contracts to `get_service_manifest`:

```python
"research_memory": {
    "status": "preview",
    "default_store": ".demo_runs/research-memory/memory.jsonl",
    "optional_adapters": ["graphiti", "cognee"],
    "executes_tools": False,
}
```

- [ ] **Step 4: Run MCP memory tests and stdio tool-list test**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_mcp_service.py::test_memory_tools_are_listed_in_manifest tests/unit/test_mcp_service.py::test_retrieve_research_memory_returns_provenance tests/integration/test_mcp_server_stdio.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/mcp_service.py tests/unit/test_mcp_service.py tests/integration/test_mcp_server_stdio.py
git commit -m "Expose research memory MCP tools"
```

---

### Task 7: Release Gate And Documentation Binding

**Files:**
- Modify: `scripts/release_check.py`
- Modify: `tests/unit/test_release_check.py`
- Modify: `docs/release-checklist.md`
- Modify: `docs/product/research-memory-layer-cn.md`
- Modify: `docs/mcp-client-setup.md`
- Modify: `docs/client-planner-template.md`
- Modify: `docs/skills-setup-cn.md`
- Modify: `skills/ml-research-loop-planner/SKILL.md`
- Modify: `skills/ml-research-loop-reproduction/SKILL.md`
- Modify: `skills/ml-research-loop-experiment-optimizer/SKILL.md`
- Modify: `tests/unit/test_mcp_delivery_docs.py`
- Modify: `tests/unit/test_planner_docs.py`
- Modify: `tests/unit/test_skill_packages.py`

- [ ] **Step 1: Write failing release/docs tests**

Update tests to assert:

```python
assert "research-memory-smoke" in release_check_doc_or_payload
assert "record_research_memory" in setup_doc
assert "retrieve_research_memory" in planner_doc
assert "suggest_from_memory" in planner_skill
assert "audit_memory_trace" in planner_skill
assert "memory suggestions are advisory" in product_doc
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_release_check.py tests/unit/test_mcp_delivery_docs.py tests/unit/test_planner_docs.py tests/unit/test_skill_packages.py -q
```

Expected: FAIL until release/docs are wired.

- [ ] **Step 3: Add release gate check**

In `scripts/release_check.py`, add a check that runs:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 scripts/memory_smoke.py --output-dir .demo_runs/release-check-memory
```

Label it:

```python
"research-memory-smoke"
```

- [ ] **Step 4: Update docs and skills**

Add memory workflow text:

- `docs/mcp-client-setup.md`: list memory tools and default advisory boundary.
- `docs/client-planner-template.md`: call `retrieve_research_memory` before proposal when available; call `record_research_memory` after reviewed runs.
- `docs/skills-setup-cn.md`: explain memory retrieval/recording in recommended flow.
- Planner/reproduction/optimizer skills: name `retrieve_research_memory`, `suggest_from_memory`, `record_research_memory`, and `audit_memory_trace`.
- `docs/release-checklist.md`: add dependency-free memory smoke and optional adapter checks.

- [ ] **Step 5: Run release/docs tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_release_check.py tests/unit/test_mcp_delivery_docs.py tests/unit/test_planner_docs.py tests/unit/test_skill_packages.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/release_check.py docs/release-checklist.md docs/product/research-memory-layer-cn.md docs/mcp-client-setup.md docs/client-planner-template.md docs/skills-setup-cn.md skills tests/unit
git commit -m "Bind research memory into release docs and skills"
```

---

### Task 8: End-To-End Verification And Final Review

**Files:**
- No new source files unless verification reveals a real bug.

- [ ] **Step 1: Run focused memory test suite**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_research_memory.py \
  tests/unit/test_memory_adapters.py \
  tests/unit/test_mcp_service.py \
  tests/unit/test_cli.py \
  tests/unit/test_release_check.py \
  tests/unit/test_mcp_delivery_docs.py \
  tests/unit/test_planner_docs.py \
  tests/unit/test_skill_packages.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run formatting/lint**

Run:

```bash
.venv/bin/ruff check lib/ scripts/ tests/
git diff --check
```

Expected: `All checks passed!` and no whitespace output.

- [ ] **Step 3: Run full release gate**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/release_check.py --json
```

Expected: JSON has `"status": "passed"` and includes `"research-memory-smoke"`.

- [ ] **Step 4: Manual code review checklist**

Review:

- Memory suggestions never execute tools.
- Non-procedure cards require artifact refs.
- Private ingestion requires explicit opt-in.
- `official_scores_claimed=true` is rejected.
- Graphiti/cognee imports are optional and do not affect fresh checkout.
- MCP tools return project-owned schema only.
- Release docs do not overclaim memory as proof.

- [ ] **Step 5: Commit final verification fixes if needed**

If verification required fixes:

```bash
git add <changed-files>
git commit -m "Harden research memory release gate"
```

If no fixes are needed, do not create an empty commit.

---

## Delivery Milestones

### P16.0 Local Memory Baseline

Includes Tasks 1-3 and the local portion of Task 5.

Acceptance:

- Can record and retrieve local memory cards.
- Can extract fastText proof artifacts into memory cards.
- Can produce suggestions and audit traces with provenance.
- Does not require Graphiti/cognee.

### P16.1 Optional Adapter Spike

Includes Task 4.

Acceptance:

- Missing optional dependencies are reported as skipped, not failure.
- Adapter interface returns project-owned views.
- Future real adapter work has a stable boundary.

### P16.2 MCP + CLI + Skills

Includes Tasks 5-7.

Acceptance:

- MCP and CLI expose memory record/retrieve/suggest/promote/audit.
- Skills and planner docs use memory before proposal and after reviewed runs.
- Suggestions remain advisory.

### P16.3 Release And Safety

Includes Task 8.

Acceptance:

- Full release gate passes.
- Dependency-free memory smoke is in release check.
- Privacy, claim boundary, optional adapter, and no-execution constraints are verified.

## Final Validation Commands

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_memory.py tests/unit/test_memory_adapters.py -q
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_mcp_service.py tests/unit/test_cli.py tests/unit/test_release_check.py -q
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_mcp_delivery_docs.py tests/unit/test_planner_docs.py tests/unit/test_skill_packages.py -q
.venv/bin/ruff check lib/ scripts/ tests/
git diff --check
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON="$(which python3)" python3 scripts/release_check.py --json
```

## Self-Review

- Spec coverage: covers target, path, constraints, acceptance, testing, local baseline, optional adapters, MCP/CLI, Skills, privacy, and release gate.
- Placeholder scan: no unresolved placeholder markers or open-ended implementation gaps. Adapter real backends are intentionally out of scope but represented as skipped optional adapters with stable interfaces.
- Type consistency: schema names match canonical docs: `ResearchMemoryCard`, `MemoryEvidenceRef`, `MemoryArtifactRef`, `MemorySuggestion`, `MemoryTrace`.
