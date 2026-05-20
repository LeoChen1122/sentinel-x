#!/usr/bin/env python3
"""Step 8 / phase 4-0 demo: multicluster mock pipeline and optional live sync."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from models.scope import resolve_langgraph_thread_id  # noqa: E402
from query import format_query_result, run_query  # noqa: E402
from sync.multicluster import make_mock_cluster_sync, sync_clusters_resilient  # noqa: E402
from testing.multicluster_fixtures import (  # noqa: E402
    CLUSTER_DEV,
    CLUSTER_LOCAL,
    CLUSTER_PROD,
    dual_cluster_merged_batch,
)


def _print_multicluster_mock() -> None:
    sync_one = make_mock_cluster_sync()
    with mock.patch("sync.pipeline.stream_sentinel_run", return_value=iter([])):
        mc = sync_clusters_resilient([CLUSTER_DEV, CLUSTER_PROD], sync_one)
    print(
        f"sync mock: dev entities={mc.by_cluster[CLUSTER_DEV].entities_pushed}, "
        f"prod entities={mc.by_cluster[CLUSTER_PROD].entities_pushed}"
    )
    payload = dual_cluster_merged_batch().to_dict(wire_only=True)
    for cid in (CLUSTER_DEV, CLUSTER_PROD):
        print(f"=== cluster {cid} list_pods ===")
        print(
            format_query_result(
                run_query(payload, "list_pods", cluster_id=cid)
            ),
            end="",
        )
        print(f"=== cluster {cid} events_for_pod ===")
        print(
            format_query_result(
                run_query(
                    payload,
                    "events_for_pod",
                    cluster_id=cid,
                    namespace="default",
                    name="shared-pod",
                )
            ),
            end="",
        )


def _run_inspect_on_thread(
    client: Any,
    thread_id: str,
    cluster_id: str,
    *,
    pod_name: str = "crash-pod",
) -> None:
    from clients.langgraph_client import get_inspect_outputs_from_stream, stream_sentinel_run
    from testing.multicluster_fixtures import dual_cluster_rich_batch

    payload = dual_cluster_rich_batch().to_dict(wire_only=True)
    payload["inspect"] = {
        "cluster_id": cluster_id,
        "namespace": "default",
        "pod_name": pod_name,
        "dry_run": True,
    }
    chunks = list(stream_sentinel_run(payload, client=client, thread_id=thread_id))
    outputs = get_inspect_outputs_from_stream(chunks)
    print("=== inspect (live) ===")
    print(f"issues={outputs.get('diagnosis', {}).get('issues')}")
    print(f"execution_source={outputs.get('execution', {}).get('execution_source')}")
    print(f"narrative_source={outputs.get('narrative', {}).get('narrative_source')}")


def _live_demo(
    cluster_id: str,
    thread_id: str | None,
    tenant_id: str | None,
    *,
    run_inspect: bool = False,
) -> None:
    from clients.langgraph_client import get_langgraph_client, query_sentinel
    from sync import sync_pods_events_inspections_resilient
    from testing.multicluster_fixtures import (
        events_mcp,
        inspection_mcp,
        pods_mcp,
    )

    client = get_langgraph_client()
    ns = "default"
    tid = resolve_langgraph_thread_id(
        thread_id=thread_id,
        cluster_id=cluster_id,
        tenant_id=tenant_id,
    )
    sync_pods_events_inspections_resilient(
        pods_mcp(cluster_id, namespace=ns),
        events_mcp(cluster_id, namespace=ns),
        ns,
        inspection_mcp(cluster_id, namespace=ns),
        client=client,
        cluster_id=cluster_id,
        tenant_id=tenant_id,
        thread_id=tid,
    )
    for op in ("events_for_pod", "inspections_for_pod"):
        out = query_sentinel(
            op,
            thread_id=tid,
            client=client,
            cluster_id=cluster_id,
            namespace=ns,
            name="shared-pod",
        )
        print(f"=== {op} (live) ===")
        print(format_query_result(out), end="")

    if run_inspect:
        _run_inspect_on_thread(client, tid, cluster_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--cluster-id", default=CLUSTER_LOCAL)
    parser.add_argument(
        "--thread-id",
        default=None,
        help="LangGraph thread (default: {tenant}:{cluster_id})",
    )
    parser.add_argument("--tenant-id", default=None)
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="After sync/query, run inspect → diagnose → execute on thread",
    )
    args = parser.parse_args()

    if args.live:
        if os.environ.get("LANGGRAPH_RUN_LIVE", "").strip().lower() not in (
            "1",
            "true",
            "yes",
        ):
            print("Set LANGGRAPH_RUN_LIVE=1", file=sys.stderr)
            return 1
        _live_demo(
            args.cluster_id,
            args.thread_id,
            args.tenant_id,
            run_inspect=args.inspect,
        )
        return 0

    _print_multicluster_mock()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
