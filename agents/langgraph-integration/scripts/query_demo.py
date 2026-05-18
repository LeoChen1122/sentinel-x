#!/usr/bin/env python3
"""Step 6 demo: query graph payload locally or via LangGraph (--live)."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from models.entities import EntityType, RelationType  # noqa: E402
from models.ids import event_id, inspection_id, pod_id  # noqa: E402
from query import format_query_result, run_query  # noqa: E402


def _mock_payload() -> dict:
    ns = "default"
    pname = "demo-pod"
    pid = pod_id(ns, pname)
    eid = event_id(
        namespace=ns,
        object_kind="Pod",
        object_name=pname,
        reason="FailedScheduling",
        last_timestamp="2024-06-01T12:00:00Z",
    )
    iid = inspection_id("2024-06-01T12:00:00Z", "worker-01")
    return {
        "entities": [
            {
                "id": pid,
                "type": EntityType.POD.value,
                "properties": {"namespace": ns, "name": pname, "status": "Running"},
            },
            {
                "id": eid,
                "type": EntityType.EVENT.value,
                "properties": {
                    "type": "Warning",
                    "reason": "FailedScheduling",
                    "message": "0/3 nodes available",
                    "last_timestamp": "2024-06-01T12:00:00Z",
                },
            },
            {
                "id": iid,
                "type": EntityType.INSPECTION.value,
                "properties": {
                    "timestamp": "2024-06-01T12:00:00Z",
                    "node": "worker-01",
                    "status": "ok",
                    "summary": "routine check",
                },
            },
        ],
        "edges": [
            {
                "source_id": pid,
                "target_id": eid,
                "relation": RelationType.HAS_EVENT.value,
            },
            {
                "source_id": iid,
                "target_id": pid,
                "relation": RelationType.INSPECTS_POD.value,
            },
        ],
    }


def _print_ops(payload: dict) -> None:
    for op, params in (
        ("list_pods", {}),
        ("pod_status", {"namespace": "default", "name": "demo-pod"}),
        ("events_for_pod", {"namespace": "default", "name": "demo-pod"}),
        ("inspections_summary", {}),
    ):
        result = run_query(payload, op, **params)
        print(f"=== {op} ===")
        print(format_query_result(result), end="")


def _live_demo(thread_id: str) -> None:
    from adapter import pods_events_to_batch
    from clients.langgraph_client import (
        get_langgraph_client,
        query_sentinel,
        stream_sentinel_run,
    )

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
    batch = pods_events_to_batch(pods_mcp, events_mcp, "default")
    client = get_langgraph_client()
    list(
        stream_sentinel_run(
            batch.to_dict(wire_only=True),
            thread_id=thread_id,
            client=client,
        )
    )

    result = query_sentinel(
        "events_for_pod",
        thread_id=thread_id,
        client=client,
        namespace="default",
        name="demo-pod",
    )
    print("=== events_for_pod (live) ===")
    print(format_query_result(result), end="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sentinel-X query demo (step 6)")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Sync + query via LangGraph (requires LANGGRAPH_API_URL, langgraph dev)",
    )
    parser.add_argument(
        "--thread-id",
        default=os.environ.get("LANGGRAPH_THREAD_ID") or str(uuid.uuid4()),
        help="Thread id for --live (default: new UUID)",
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
        _live_demo(args.thread_id)
        return 0

    _print_ops(_mock_payload())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
