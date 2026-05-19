"""Multicluster MCP mock payloads for phase 4-0 (no live K8s / LangGraph)."""

from __future__ import annotations

from adapter.inspections import inspection_mcp_to_batch
from adapter.k8s import pods_events_to_batch
from adapter.types import McpListResponse
from models.entities import GraphBatch
from models.ids import pod_id
from utils.graph_merge import merge_graph_batches

CLUSTER_DEV = "dev-cluster"
CLUSTER_PROD = "prod-cluster"
CLUSTER_LOCAL = "local"

_DEFAULT_NODE = "worker-01"
_DEFAULT_POD = "shared-pod"


def pods_mcp(
    cluster_id: str,
    *,
    namespace: str = "default",
    pod_name: str = _DEFAULT_POD,
    status: str = "Running",
) -> McpListResponse:
    return {
        "query": "get_pods",
        "cluster_id": cluster_id,
        "results": [{"name": pod_name, "status": status}],
    }


def pods_mcp_multi(
    cluster_id: str,
    *,
    namespace: str = "default",
    pods: list[dict[str, str]],
) -> McpListResponse:
    """Multiple pods in one MCP response."""
    return {
        "query": "get_pods",
        "cluster_id": cluster_id,
        "results": [{"name": p["name"], "status": p.get("status", "Running")} for p in pods],
    }


def events_mcp(
    cluster_id: str,
    *,
    namespace: str = "default",
    pod_name: str = _DEFAULT_POD,
    reason: str = "FailedScheduling",
    event_type: str = "Warning",
) -> McpListResponse:
    return {
        "query": "get_events",
        "cluster_id": cluster_id,
        "results": [
            {
                "type": event_type,
                "reason": reason,
                "message": f"event on {cluster_id} for {pod_name}",
                "namespace": namespace,
                "object_kind": "Pod",
                "object_name": pod_name,
                "last_timestamp": "2024-06-01T12:00:00Z",
            }
        ],
    }


def events_mcp_multi(
    cluster_id: str,
    *,
    namespace: str = "default",
    events: list[dict[str, str]],
) -> McpListResponse:
    rows = []
    for ev in events:
        pname = ev["pod_name"]
        rows.append(
            {
                "type": ev.get("type", "Warning"),
                "reason": ev.get("reason", "FailedScheduling"),
                "message": ev.get("message", f"event on {cluster_id}"),
                "namespace": namespace,
                "object_kind": "Pod",
                "object_name": pname,
                "last_timestamp": ev.get("last_timestamp", "2024-06-01T12:00:00Z"),
            }
        )
    return {"query": "get_events", "cluster_id": cluster_id, "results": rows}


def inspection_mcp(
    cluster_id: str,
    *,
    namespace: str = "default",
    pod_name: str = _DEFAULT_POD,
    node_name: str = _DEFAULT_NODE,
    status: str = "ok",
) -> McpListResponse:
    pid = pod_id(cluster_id, namespace, pod_name)
    return {
        "query": "get_inspections",
        "cluster_id": cluster_id,
        "results": [
            {
                "timestamp": "2024-06-01T12:00:00Z",
                "node": node_name,
                "status": status,
                "summary": f"check {cluster_id} {pod_name}",
                "linked_pods": [pid],
            }
        ],
    }


def pods_events_batch(
    cluster_id: str,
    namespace: str = "default",
    *,
    tenant_id: str | None = None,
    pod_name: str = _DEFAULT_POD,
) -> GraphBatch:
    return pods_events_to_batch(
        pods_mcp(cluster_id, namespace=namespace, pod_name=pod_name),
        events_mcp(cluster_id, namespace=namespace, pod_name=pod_name),
        namespace,
        tenant_id=tenant_id,
    )


def pods_events_batch_with_node(
    cluster_id: str,
    namespace: str = "default",
    *,
    tenant_id: str | None = None,
    pod_name: str = _DEFAULT_POD,
    node_name: str = _DEFAULT_NODE,
    reason: str = "FailedScheduling",
) -> GraphBatch:
    """Pod + Event + Node (``scheduled_on``) for one cluster."""
    return pods_events_to_batch(
        pods_mcp(cluster_id, namespace=namespace, pod_name=pod_name),
        events_mcp(
            cluster_id,
            namespace=namespace,
            pod_name=pod_name,
            reason=reason,
        ),
        namespace,
        cluster_id=cluster_id,
        tenant_id=tenant_id,
        pod_node_map={pod_name: node_name},
    )


def cluster_full_batch(
    cluster_id: str,
    namespace: str = "default",
    *,
    tenant_id: str | None = None,
    pod_name: str = _DEFAULT_POD,
    node_name: str = _DEFAULT_NODE,
) -> GraphBatch:
    """Pod + Event + Node + Inspection for one cluster."""
    pe = pods_events_batch_with_node(
        cluster_id,
        namespace,
        tenant_id=tenant_id,
        pod_name=pod_name,
        node_name=node_name,
    )
    insp = inspection_mcp_to_batch(
        inspection_mcp(cluster_id, namespace=namespace, pod_name=pod_name, node_name=node_name),
        tenant_id=tenant_id,
    )
    return merge_graph_batches(pe, insp)


def cluster_rich_batch(
    cluster_id: str,
    namespace: str = "default",
    *,
    tenant_id: str | None = None,
) -> GraphBatch:
    """Multiple pods/events: shared-pod Running + Warning, crash-pod CrashLoopBackOff."""
    pods = pods_mcp_multi(
        cluster_id,
        namespace=namespace,
        pods=[
            {"name": "shared-pod", "status": "Running"},
            {"name": "crash-pod", "status": "CrashLoopBackOff"},
        ],
    )
    events = events_mcp_multi(
        cluster_id,
        namespace=namespace,
        events=[
            {
                "pod_name": "shared-pod",
                "type": "Warning",
                "reason": "FailedScheduling",
            },
            {
                "pod_name": "crash-pod",
                "type": "Warning",
                "reason": "BackOff",
                "message": f"crash on {cluster_id}",
            },
        ],
    )
    pe = pods_events_to_batch(
        pods,
        events,
        namespace,
        cluster_id=cluster_id,
        tenant_id=tenant_id,
        pod_node_map={"shared-pod": _DEFAULT_NODE},
    )
    insp_shared = inspection_mcp_to_batch(
        inspection_mcp(cluster_id, namespace=namespace, pod_name="shared-pod"),
        tenant_id=tenant_id,
    )
    return merge_graph_batches(pe, insp_shared)


def dual_cluster_merged_batch(
    namespace: str = "default",
    *,
    tenant_id: str | None = None,
) -> GraphBatch:
    """Two clusters Pod/Event; dev inspection only (backward compatible)."""
    dev = pods_events_batch(CLUSTER_DEV, namespace, tenant_id=tenant_id)
    prod = pods_events_batch(CLUSTER_PROD, namespace, tenant_id=tenant_id)
    insp = inspection_mcp_to_batch(
        inspection_mcp(CLUSTER_DEV, namespace=namespace),
        tenant_id=tenant_id,
    )
    return merge_graph_batches(dev, prod, insp)


def dual_cluster_full_batch(
    namespace: str = "default",
    *,
    tenant_id: str | None = None,
) -> GraphBatch:
    """Dev + prod: each with Pod, Event, Node, Inspection (acceptance fixture)."""
    dev = cluster_full_batch(CLUSTER_DEV, namespace, tenant_id=tenant_id)
    prod = cluster_full_batch(CLUSTER_PROD, namespace, tenant_id=tenant_id)
    return merge_graph_batches(dev, prod)


def dual_cluster_rich_batch(
    namespace: str = "default",
    *,
    tenant_id: str | None = None,
) -> GraphBatch:
    """Dev + prod rich multi-pod graphs for Agent narrative tests."""
    dev = cluster_rich_batch(CLUSTER_DEV, namespace, tenant_id=tenant_id)
    prod = cluster_rich_batch(CLUSTER_PROD, namespace, tenant_id=tenant_id)
    return merge_graph_batches(dev, prod)


def dual_cluster_rich_payload(
    namespace: str = "default",
    *,
    tenant_id: str | None = None,
) -> dict:
    return dual_cluster_rich_batch(namespace, tenant_id=tenant_id).to_dict(wire_only=True)
