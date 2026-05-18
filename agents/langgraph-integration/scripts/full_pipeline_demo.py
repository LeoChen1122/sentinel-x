#!/usr/bin/env python3
"""Step 8 demo: Pod + Event + Inspection mock pipeline and optional live sync.

Default (no LangGraph): build batches, merge, run local ``run_query``.
``--live``: requires ``langgraph dev``, ``LANGGRAPH_API_URL``, ``LANGGRAPH_RUN_LIVE=1``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from adapter.inspections import inspection_mcp_to_batch  # noqa: E402
from adapter.k8s import pods_events_to_batch  # noqa: E402
from models.ids import pod_id  # noqa: E402
from query import format_query_result, run_query  # noqa: E402
from utils.graph_merge import merge_graph_batches  # noqa: E402


def _mock_mcp(namespace: str) -> tuple[dict, dict, dict]:
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
                "message": "0/3 nodes available",
                "object_kind": "Pod",
                "object_name": "demo-pod",
                "last_timestamp": "2024-06-01T12:00:00Z",
            }
        ],
    }
    pid = pod_id(namespace, "demo-pod")
    inspection_mcp = {
        "query": "get_inspections",
        "results": [
            {
                "timestamp": "2024-06-01T12:00:00Z",
                "node": "worker-01",
                "status": "ok",
                "summary": "routine check",
                "linked_pods": [pid],
            }
        ],
    }
    return pods_mcp, events_mcp, inspection_mcp


def _build_payload(namespace: str) -> dict:
    pods_mcp, events_mcp, inspection_mcp = _mock_mcp(namespace)
    pe = pods_events_to_batch(pods_mcp, events_mcp, namespace)
    insp = inspection_mcp_to_batch(inspection_mcp)
    return merge_graph_batches(pe, insp).to_dict(wire_only=True)


def _print_queries(payload: dict, namespace: str) -> None:
    for op, params in (
        ("list_pods", {"namespace": namespace}),
        ("list_events", {"namespace": namespace}),
        ("events_for_pod", {"namespace": namespace, "name": "demo-pod"}),
        ("inspections_summary", {}),
        ("inspections_for_pod", {"namespace": namespace, "name": "demo-pod"}),
    ):
        result = run_query(payload, op, **params)
        print(f"=== {op} ===")
        print(format_query_result(result), end="")


def _live_demo(namespace: str, thread_id: str) -> None:
    from clients.langgraph_client import get_langgraph_client, query_sentinel
    from sync import sync_pods_events_inspections_resilient

    pods_mcp, events_mcp, inspection_mcp = _mock_mcp(namespace)
    client = get_langgraph_client()
    result = sync_pods_events_inspections_resilient(
        pods_mcp,
        events_mcp,
        namespace,
        inspection_mcp,
        client=client,
        thread_id=thread_id,
    )
    print(
        "sync:",
        f"chunks={result.chunks_sent}",
        f"entities={result.entities_pushed}",
        f"edges={result.edges_pushed}",
    )
    for op, params in (
        ("events_for_pod", {"namespace": namespace, "name": "demo-pod"}),
        ("inspections_for_pod", {"namespace": namespace, "name": "demo-pod"}),
    ):
        out = query_sentinel(op, thread_id=thread_id, client=client, **params)
        print(f"=== {op} (live) ===")
        print(format_query_result(out), end="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 8 full pipeline demo")
    parser.add_argument("--live", action="store_true", help="Sync + query via LangGraph")
    parser.add_argument("--namespace", default="default")
    parser.add_argument(
        "--thread-id",
        default=os.environ.get("LANGGRAPH_THREAD_ID", "step8-demo"),
    )
    args = parser.parse_args()

    if args.live:
        if os.environ.get("LANGGRAPH_RUN_LIVE", "").strip().lower() not in (
            "1",
            "true",
            "yes",
        ):
            print("Set LANGGRAPH_RUN_LIVE=1 for --live", file=sys.stderr)
            return 1
        _live_demo(args.namespace, args.thread_id)
        return 0

    _print_queries(_build_payload(args.namespace), args.namespace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
