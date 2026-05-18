"""Adapter: inspection records → graph entities (future inspection MCP).

Wire IDs for ``linked_pods`` / ``linked_nodes`` (row fields or ``link_*`` args)
must be **entity ids** only, e.g. ``pod:default/demo-pod``, ``node:worker-01``.
Do not pass bare pod names or ``namespace/name`` strings.
"""

from __future__ import annotations

import logging
from typing import Any

from adapter.types import McpListResponse
from models.entities import (
    GraphBatch,
    GraphEntity,
    edge_inspection_to_node,
    edge_inspection_to_pod,
    entity_from_inspection,
)

logger = logging.getLogger(__name__)

_POD_ID_PREFIX = "pod:"
_NODE_ID_PREFIX = "node:"


def _entity_ids_from_field(
    value: object, *, expected_prefix: str, field_name: str
) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        logger.warning(
            "inspection row %s must be a list of entity ids, got %r",
            field_name,
            type(value).__name__,
        )
        return []
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            continue
        eid = item.strip()
        if not eid.startswith(expected_prefix):
            logger.warning(
                "inspection %s entry %r must start with %r (entity id)",
                field_name,
                eid,
                expected_prefix,
            )
            continue
        out.append(eid)
    return out


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def inspections_to_entities(rows: list[dict[str, Any]]) -> list[GraphEntity]:
    """Map inspection rows to ``GraphEntity`` list.

    Expected keys per row: ``timestamp``, ``node``, ``status``, ``summary``.
    """
    entities: list[GraphEntity] = []
    for row in rows:
        entities.append(
            entity_from_inspection(
                str(row["timestamp"]),
                str(row["node"]),
                str(row.get("status", "unknown")),
                str(row.get("summary", "")),
            )
        )
    return entities


def inspections_to_batch(
    rows: list[dict[str, Any]],
    *,
    link_pods: list[str] | None = None,
    link_nodes: list[str] | None = None,
) -> GraphBatch:
    """Build inspection entities and optional ``inspects_*`` edges."""
    batch = GraphBatch(entities=inspections_to_entities(rows))
    global_pods = _entity_ids_from_field(
        link_pods, expected_prefix=_POD_ID_PREFIX, field_name="link_pods"
    )
    global_nodes = _entity_ids_from_field(
        link_nodes, expected_prefix=_NODE_ID_PREFIX, field_name="link_nodes"
    )

    for insp, row in zip(batch.entities, rows):
        row_pods = _entity_ids_from_field(
            row.get("linked_pods"),
            expected_prefix=_POD_ID_PREFIX,
            field_name="linked_pods",
        )
        row_nodes = _entity_ids_from_field(
            row.get("linked_nodes"),
            expected_prefix=_NODE_ID_PREFIX,
            field_name="linked_nodes",
        )
        pods = _dedupe_preserve(row_pods + global_pods)
        nodes = _dedupe_preserve(row_nodes + global_nodes)
        for pid in pods:
            batch.edges.append(edge_inspection_to_pod(insp.id, pid))
        for nid in nodes:
            batch.edges.append(edge_inspection_to_node(insp.id, nid))
    return batch


def inspection_mcp_to_batch(
    mcp_json: McpListResponse,
    *,
    link_pods: list[str] | None = None,
    link_nodes: list[str] | None = None,
) -> GraphBatch:
    """Map ``{query, results}`` inspection MCP shape to ``GraphBatch``."""
    rows = mcp_json.get("results") or []
    return inspections_to_batch(rows, link_pods=link_pods, link_nodes=link_nodes)
