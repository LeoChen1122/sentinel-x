"""Adapter: ``k8s_get_events`` MCP payload → graph entities."""

from __future__ import annotations

from adapter.types import McpListResponse
from models.entities import GraphBatch, GraphEntity, entity_from_event_row
from models.scope import resolve_cluster_id


def events_to_entities(
    mcp_json: McpListResponse,
    *,
    cluster_id: str | None = None,
    tenant_id: str | None = None,
) -> list[GraphEntity]:
    """Map ``{query, results}`` from ``k8s_get_events`` to Event entities."""
    cid = resolve_cluster_id(mcp_json, cluster_id=cluster_id)
    return [
        entity_from_event_row(row, cluster_id=cid, tenant_id=tenant_id)
        for row in mcp_json.get("results") or []
    ]


def events_to_langgraph_entities(
    mcp_json: McpListResponse,
    **kwargs: object,
) -> list[GraphEntity]:
    """Guide alias for :func:`events_to_entities`."""
    return events_to_entities(mcp_json, **kwargs)  # type: ignore[arg-type]


def events_mcp_to_batch(
    mcp_json: McpListResponse,
    *,
    cluster_id: str | None = None,
    tenant_id: str | None = None,
) -> GraphBatch:
    """Convenience: events-only ``GraphBatch`` (no Pod→Event edges)."""
    return GraphBatch(
        entities=events_to_entities(
            mcp_json, cluster_id=cluster_id, tenant_id=tenant_id
        )
    )
