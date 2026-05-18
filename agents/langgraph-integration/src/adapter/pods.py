"""Adapter: ``k8s_get_pods`` MCP payload → graph entities."""

from __future__ import annotations

import logging
from typing import Any

from adapter.types import McpListResponse
from models.entities import GraphBatch, GraphEntity, entity_from_pod_row

logger = logging.getLogger(__name__)


def _pod_name_from_row(row: dict[str, Any]) -> str | None:
    name = row.get("name")
    if name is None or not str(name).strip():
        return None
    return str(name).strip()


def pods_to_entities(
    mcp_json: McpListResponse,
    namespace: str,
    *,
    labels: dict[str, str] | None = None,
    creation_timestamp: str | None = None,
) -> list[GraphEntity]:
    """Map ``{query, results}`` from ``k8s_get_pods`` to Pod ``GraphEntity`` list.

    ``namespace`` comes from the tool argument, not from each MCP row.
    Rows without ``name`` or non-dict rows are skipped with a warning (batch continues).
    """
    entities: list[GraphEntity] = []
    for row in mcp_json.get("results") or []:
        if not isinstance(row, dict):
            logger.warning("Skipping pod row that is not a dict: %r", row)
            continue
        if _pod_name_from_row(row) is None:
            logger.warning("Skipping pod row missing name: %r", row)
            continue
        entities.append(
            entity_from_pod_row(
                row,
                namespace,
                labels=labels,
                creation_timestamp=creation_timestamp,
            )
        )
    return entities


def pods_to_langgraph_entities(
    mcp_json: McpListResponse,
    namespace: str,
    **kwargs: Any,
) -> list[GraphEntity]:
    """Guide alias for :func:`pods_to_entities`."""
    return pods_to_entities(mcp_json, namespace, **kwargs)


def pods_mcp_to_batch(
    mcp_json: McpListResponse,
    namespace: str,
) -> GraphBatch:
    """Convenience: pods-only ``GraphBatch`` (no edges)."""
    return GraphBatch(entities=pods_to_entities(mcp_json, namespace))
