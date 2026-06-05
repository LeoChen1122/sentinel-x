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

from adapter.inspections import inspection_mcp_to_batch  # noqa: E402
from adapter.k8s import pods_events_to_batch  # noqa: E402
from query import format_query_result, run_query  # noqa: E402
from testing.multicluster_fixtures import (  # noqa: E402
    CLUSTER_LOCAL,
    inspection_mcp,
    pods_mcp,
    events_mcp,
)
from utils.graph_merge import merge_graph_batches  # noqa: E402


def _mock_payload(cluster_id: str = CLUSTER_LOCAL) -> dict:
    ns = "default"
    pe = pods_events_to_batch(
        pods_mcp(cluster_id, namespace=ns),
        events_mcp(cluster_id, namespace=ns),
        ns,
    )
    insp = inspection_mcp_to_batch(inspection_mcp(cluster_id, namespace=ns))
    return merge_graph_batches(pe, insp).to_dict(wire_only=True)


def _print_ops(payload: dict, cluster_id: str) -> None:
    ns = "default"
    for op, params in (
        ("list_pods", {"cluster_id": cluster_id}),
        ("pod_status", {"cluster_id": cluster_id, "namespace": ns, "name": "shared-pod"}),
        (
            "events_for_pod",
            {"cluster_id": cluster_id, "namespace": ns, "name": "shared-pod"},
        ),
        ("inspections_summary", {"cluster_id": cluster_id}),
    ):
        result = run_query(payload, op, **params)
        print(f"=== {op} ===")
        print(format_query_result(result), end="")


def _live_demo(thread_id: str, cluster_id: str) -> None:
    from clients.langgraph_client import (
        get_langgraph_client,
        query_sentinel,
        stream_sentinel_run,
    )

    ns = "default"
    client = get_langgraph_client()
    batch = pods_events_to_batch(
        pods_mcp(cluster_id, namespace=ns),
        events_mcp(cluster_id, namespace=ns),
        ns,
    )
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
        cluster_id=cluster_id,
        namespace=ns,
        name="shared-pod",
    )
    print("=== events_for_pod (live) ===")
    print(format_query_result(result), end="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sentinel-X query demo (step 6)")
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--cluster-id",
        default=os.environ.get("CLUSTER_ID", CLUSTER_LOCAL),
    )
    parser.add_argument(
        "--thread-id",
        default=os.environ.get("LANGGRAPH_THREAD_ID") or str(uuid.uuid4()),
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
        _live_demo(args.thread_id, args.cluster_id)
        return 0

    _print_ops(_mock_payload(args.cluster_id), args.cluster_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
