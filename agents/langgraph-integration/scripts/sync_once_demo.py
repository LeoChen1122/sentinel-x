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

from models.scope import sync_thread_id  # noqa: E402
from sync import sync_pods_and_events_resilient  # noqa: E402


def main() -> int:
    from testing.multicluster_fixtures import CLUSTER_LOCAL, events_mcp, pods_mcp

    pods_payload = pods_mcp(CLUSTER_LOCAL)
    events_payload = events_mcp(CLUSTER_LOCAL)
    events_payload = {
        **events_payload,
        "results": [
            {
                "type": "Warning",
                "reason": "FailedScheduling",
                "message": "0/3 nodes",
                "object_kind": "Pod",
                "object_name": "shared-pod",
                "last_timestamp": "2024-06-01T12:00:00Z",
            }
        ],
    }
    result = sync_pods_and_events_resilient(
        pods_payload,
        events_payload,
        "default",
        cluster_id=CLUSTER_LOCAL,
        thread_id=sync_thread_id(CLUSTER_LOCAL),
    )
    print(f"thread_id={sync_thread_id(CLUSTER_LOCAL)}")
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
