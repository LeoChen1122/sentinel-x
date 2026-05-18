#!/usr/bin/env python3
"""Step 5 demo: event-triggered sync with mock MCP JSON → LangGraph.

Requires ``langgraph dev`` and ``LANGGRAPH_API_URL``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sync import sync_pods_and_events_resilient  # noqa: E402


def main() -> int:
    pods_mcp = {
        "query": "get_pods",
        "results": [{"name": "demo-pod", "status": "Running"}],
    }
    events_mcp = {
        "query": "get_events",
        "results": [
            {
                "type": "Warning",
                "reason": "FailedScheduling",
                "message": "0/3 nodes",
                "object_kind": "Pod",
                "object_name": "demo-pod",
                "last_timestamp": "2024-06-01T12:00:00Z",
            }
        ],
    }
    result = sync_pods_and_events_resilient(pods_mcp, events_mcp, "default")
    print(
        "sync ok:",
        f"chunks={result.chunks_sent}",
        f"entities={result.entities_pushed}",
        f"edges={result.edges_pushed}",
        f"skipped={result.skipped_unchanged}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
