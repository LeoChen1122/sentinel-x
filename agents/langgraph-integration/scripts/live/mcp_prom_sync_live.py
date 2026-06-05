#!/usr/bin/env python3
"""Phase 1c: fetch Prometheus MCP + K8s pods and sync metrics into LangGraph.

Requires ``langgraph dev`` on ``LANGGRAPH_API_URL`` (default http://127.0.0.1:2024).
Run K8s sync first (or this script re-fetches pods from K8s MCP).

Examples::

  export MCP_K8S_CONTAINER=mcp-servers_mcp-k8s_1
  export MCP_PROM_CONTAINER=mcp-servers_mcp-prometheus_1
  export CLUSTER_ID=k3s-prod
  export NAMESPACE=kube-system
  python scripts/live/mcp_prom_sync_live.py

  python scripts/live/mcp_prom_sync_live.py \\
    --snapshot /var/lib/sentinel/prom_mcp_snapshot.json \\
    --k8s-snapshot /var/lib/sentinel/k8s_mcp_snapshot.json \\
    --cluster-id k3s-prod --namespace kube-system
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from clients.langgraph_client import get_langgraph_client, verify_langgraph_connection  # noqa: E402
from clients.mcp_k8s import (  # noqa: E402
    attach_cluster_id as attach_k8s_cluster_id,
    fetch_k8s_mcp_via_docker,
    load_k8s_mcp_snapshot,
)
from clients.mcp_prom import (  # noqa: E402
    attach_cluster_id as attach_prom_cluster_id,
    fetch_prom_mcp_via_docker,
    load_prom_mcp_snapshot,
    promql_from_env,
)
from models.scope import resolve_langgraph_thread_id, sync_thread_id  # noqa: E402
from sync import sync_pod_metrics_resilient  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Prometheus MCP -> LangGraph pod metrics sync")
    parser.add_argument("--cluster-id", default=os.environ.get("CLUSTER_ID", "k3s-prod"))
    parser.add_argument("--namespace", default=os.environ.get("NAMESPACE", "default"))
    parser.add_argument(
        "--mcp-k8s-container",
        default=os.environ.get("MCP_K8S_CONTAINER") or os.environ.get("MCP_CONTAINER", ""),
        help="Docker container for mcp-k8s (default: MCP_K8S_CONTAINER or MCP_CONTAINER)",
    )
    parser.add_argument(
        "--mcp-prom-container",
        default=os.environ.get("MCP_PROM_CONTAINER", ""),
        help="Docker container for mcp-prometheus (default: MCP_PROM_CONTAINER env)",
    )
    parser.add_argument(
        "--snapshot",
        default=os.environ.get("PROM_MCP_SNAPSHOT", ""),
        help="Pre-exported Prom JSON instead of docker exec",
    )
    parser.add_argument(
        "--k8s-snapshot",
        default=os.environ.get("K8S_MCP_SNAPSHOT", ""),
        help="Pre-exported K8s pods JSON (required with --snapshot unless --mcp-k8s-container)",
    )
    parser.add_argument("--tenant-id", default=os.environ.get("TENANT_ID") or None)
    parser.add_argument(
        "--thread-id",
        default=os.environ.get("LANGGRAPH_THREAD_ID") or None,
    )
    parser.add_argument(
        "--incremental",
        action=argparse.BooleanOptionalAction,
        default=True,
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
        prom_snap = load_prom_mcp_snapshot(args.snapshot)
        prom_source = f"snapshot:{args.snapshot}"
    else:
        prom_container = str(args.mcp_prom_container).strip()
        if not prom_container:
            print(
                "Set MCP_PROM_CONTAINER or pass --mcp-prom-container (or use --snapshot)",
                file=sys.stderr,
            )
            return 1
        cpu_q, mem_q = promql_from_env()
        prom_snap = fetch_prom_mcp_via_docker(
            prom_container,
            cpu_promql=cpu_q,
            memory_promql=mem_q,
        )
        prom_source = f"docker:{prom_container}"

    if args.k8s_snapshot:
        pods_mcp, _events_mcp = load_k8s_mcp_snapshot(args.k8s_snapshot)
        k8s_source = f"snapshot:{args.k8s_snapshot}"
    else:
        k8s_container = str(args.mcp_k8s_container).strip()
        if not k8s_container:
            print(
                "Set MCP_K8S_CONTAINER/MCP_CONTAINER or pass --mcp-k8s-container "
                "(or use --k8s-snapshot)",
                file=sys.stderr,
            )
            return 1
        pods_mcp, _events_mcp = fetch_k8s_mcp_via_docker(k8s_container, ns)
        k8s_source = f"docker:{k8s_container}"

    pods_mcp, _ = attach_k8s_cluster_id(pods_mcp, _events_mcp, cid)
    prom_snap = attach_prom_cluster_id(prom_snap, cid)

    pod_n = len(pods_mcp.get("results") or [])
    cpu_n = len(prom_snap["cpu"].get("results") or [])
    mem_n = len(prom_snap["memory"].get("results") or [])

    tid = resolve_langgraph_thread_id(
        thread_id=args.thread_id,
        cluster_id=cid,
        tenant_id=args.tenant_id,
    )
    logical = sync_thread_id(cid, args.tenant_id)

    print(f"k8s_source={k8s_source}")
    print(f"prom_source={prom_source}")
    print(f"namespace={ns}")
    print(f"cluster_id={cid}")
    print(f"mcp pods={pod_n} prom_cpu_series={cpu_n} prom_mem_series={mem_n}")
    print(f"thread_id={tid}")
    print(f"logical={logical}")

    client = get_langgraph_client()
    if not args.skip_verify:
        verify_langgraph_connection(client)

    result = sync_pod_metrics_resilient(
        pods_mcp,
        prom_snap["cpu"],
        prom_snap["memory"],
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
    print("  top_pods_by_cpu / pod_metrics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
