"""Shared low-level helpers used across lib/failure_driven_proposal.py and its
extracted sibling modules (lib/proposal_effectiveness/, lib/method_search/,
lib/optimizer_gate/). Pure stdlib, no cross-imports from those modules.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _path_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = _string_value(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _load_object(value: dict[str, Any] | str | Path) -> tuple[dict[str, Any], Path | None]:
    if isinstance(value, dict):
        return value, None
    path = Path(value)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload, path


def _json_clone(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _is_plain_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _ensure_writable(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; pass overwrite=True to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_jsonl(items: list[dict[str, Any]], output: Path) -> None:
    with output.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
