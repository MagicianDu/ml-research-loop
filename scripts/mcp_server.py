#!/usr/bin/env python3
"""stdio MCP server entrypoint for ml-research-loop."""

from __future__ import annotations

import json
import sys
from typing import Any

from lib.mcp_service import handle_request


def main() -> int:
    """Read line-delimited JSON-RPC requests from stdin and write responses."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        response = _handle_line(line)
        if response is None:
            continue
        print(json.dumps(response, ensure_ascii=False), flush=True)

    return 0


def _handle_line(line: str) -> dict[str, Any] | None:
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": f"Parse error: {exc}"},
        }

    if not isinstance(request, dict):
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Invalid request"},
        }

    return handle_request(request)


if __name__ == "__main__":
    raise SystemExit(main())
