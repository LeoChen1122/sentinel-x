"""Combined K8s MCP adapters: pods + events (+ optional Pod→Node)."""

from __future__ import annotations

from adapter.types import McpListResponse
from models.entities import (
    EntityType,
    GraphBatch,
    edge_pod_to_node,
    entity_from_node,
)
from models.ids import pod_id
from models.scope import resolve_cluster_id


def pods_events_to_batch(
    pods_mcp: McpListResponse,
    events_mcp: McpListResponse,
    namespace: str,
    *,
    cluster_id: str | None = None,
    tenant_id: str | None = None,
    link_pod_events: bool = True,
    pod_node_map: dict[str, str] | None = None,
) -> GraphBatch:
    """Map ``k8s_get_pods`` + ``k8s_get_events`` MCP payloads to a ``GraphBatch``.

    ``cluster_id`` may be set on MCP payloads or passed explicitly.
    ``pod_node_map`` maps pod name → node name when nodeName is known outside MCP.
    """
    cid = resolve_cluster_id(pods_mcp, events_mcp, cluster_id=cluster_id)
    batch = GraphBatch.from_pods_events(
        pods_mcp,
        events_mcp,
        namespace,
        cluster_id=cid,
        tenant_id=tenant_id,
        link_pod_events=link_pod_events,
    )
    if not pod_node_map:
        return batch

    ns = namespace.strip()
    entity_ids = {e.id for e in batch.entities}
    pod_ids_in_batch = {e.id for e in batch.entities if e.type is EntityType.POD}

    for pod_name, node_name in pod_node_map.items():
        pid = pod_id(cid, ns, pod_name.strip())
        if pid not in pod_ids_in_batch:
            continue
        node_ent = entity_from_node(node_name, cluster_id=cid, tenant_id=tenant_id)
        if node_ent.id not in entity_ids:
            batch.entities.append(node_ent)
            entity_ids.add(node_ent.id)
        batch.edges.append(edge_pod_to_node(pid, node_ent.id))

    return batch
