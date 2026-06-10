#!/usr/bin/env python3
"""Phase 1b: fetch K8s MCP (docker or snapshot) and sync to LangGraph thread.

Requires ``langgraph dev`` on ``LANGGRAPH_API_URL`` (default http://127.0.0.1:2024).

Examples::

  export MCP_CONTAINER=mcp-servers_mcp-k8s_1
  export CLUSTER_ID=k3s-prod
  export NAMESPACE=default
  python scripts/live/mcp_k8s_sync_live.py

  python scripts/live/mcp_k8s_sync_live.py \\
    --snapshot /var/lib/sentinel/k8s_mcp_snapshot.json \\
    --cluster-id k3s-prod --namespace default
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from clients.langgraph_client import get_langgraph_client, verify_langgraph_connection  # noqa: E402
from clients.mcp_k8s import (  # noqa: E402
    attach_cluster_id,
    fetch_k8s_mcp_via_docker,
    load_k8s_mcp_snapshot,
)
from models.scope import resolve_langgraph_thread_id, sync_thread_id  # noqa: E402
from sync import sync_pods_and_events_resilient  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="K8s MCP -> LangGraph sync (live)")
    parser.add_argument("--cluster-id", default=os.environ.get("CLUSTER_ID", "k3s-prod"))
    parser.add_argument("--namespace", default=os.environ.get("NAMESPACE", "default"))
    parser.add_argument(
        "--mcp-container",
        default=os.environ.get("MCP_CONTAINER", ""),
        help="Docker container name for mcp-k8s (default: MCP_CONTAINER env)",
    )
    parser.add_argument(
        "--snapshot",
        default=os.environ.get("K8S_MCP_SNAPSHOT", ""),
        help="Use pre-exported JSON instead of docker exec",
    )
    parser.add_argument("--tenant-id", default=os.environ.get("TENANT_ID") or None)
    parser.add_argument(
        "--thread-id",
        default=os.environ.get("LANGGRAPH_THREAD_ID") or None,
        help="Override LangGraph thread UUID (default: langgraph_thread_id(cluster))",
    )
    parser.add_argument(
        "--incremental",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip unchanged entities (default: true)",
    )
    parser.add_argument("--min-interval-sec", type=float, default=0.0)
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()

    cid = str(args.cluster_id).strip()
    ns = str(args.namespace).strip()
    if not cid or not ns:
        print("cluster-id and namespace required", file=sys.stderr)
        return 1

    if not os.environ.get("LANGGRAPH_API_URL", "").strip():
        os.environ["LANGGRAPH_API_URL"] = "http://127.0.0.1:2024"

    if args.snapshot:
        pods_mcp, events_mcp = load_k8s_mcp_snapshot(args.snapshot)
        source = f"snapshot:{args.snapshot}"
    else:
        container = str(args.mcp_container).strip()
        if not container:
            print(
                "Set MCP_CONTAINER or pass --mcp-container (or use --snapshot)",
                file=sys.stderr,
            )
            return 1
        pods_mcp, events_mcp = fetch_k8s_mcp_via_docker(container, ns)
        source = f"docker:{container}"

    pods_mcp, events_mcp = attach_cluster_id(pods_mcp, events_mcp, cid)
    pod_n = len(pods_mcp.get("results") or [])
    ev_n = len(events_mcp.get("results") or [])

    tid = resolve_langgraph_thread_id(
        thread_id=args.thread_id,
        cluster_id=cid,
        tenant_id=args.tenant_id,
    )
    logical = sync_thread_id(cid, args.tenant_id)

    print(f"source={source}")
    print(f"namespace={ns}")
    print(f"cluster_id={cid}")
    print(f"mcp pods={pod_n} events={ev_n}")
    print(f"thread_id={tid}")
    print(f"logical={logical}")

    client = get_langgraph_client()
    if not args.skip_verify:
        verify_langgraph_connection(client)

    result = sync_pods_and_events_resilient(
        pods_mcp,
        events_mcp,
        ns,
        cluster_id=cid,
        tenant_id=args.tenant_id,
        client=client,
        thread_id=tid,
        incremental=args.incremental,
        min_interval_sec=args.min_interval_sec,
    )
    print(
        "sync ok:",
        f"chunks={result.chunks_sent}",
        f"entities={result.entities_pushed}",
        f"edges={result.edges_pushed}",
        f"skipped={result.skipped_unchanged}",
    )
    print(f"\nQuery with: LANGGRAPH_THREAD_ID={tid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
