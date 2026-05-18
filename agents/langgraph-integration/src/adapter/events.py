"""Adapter: ``k8s_get_events`` MCP payload → graph entities."""

from __future__ import annotations

from adapter.types import McpListResponse
from models.entities import GraphBatch, GraphEntity, entity_from_event_row


def events_to_entities(mcp_json: McpListResponse) -> list[GraphEntity]:
    """Map ``{query, results}`` from ``k8s_get_events`` to Event entities."""
    return [entity_from_event_row(row) for row in mcp_json.get("results") or []]


def events_to_langgraph_entities(mcp_json: McpListResponse) -> list[GraphEntity]:
    """Guide alias for :func:`events_to_entities`."""
    return events_to_entities(mcp_json)


def events_mcp_to_batch(mcp_json: McpListResponse) -> GraphBatch:
    """Convenience: events-only ``GraphBatch`` (no Pod→Event edges)."""
    return GraphBatch(entities=events_to_entities(mcp_json))
