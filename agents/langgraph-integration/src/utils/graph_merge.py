"""Merge multiple ``GraphBatch`` values for step 8 full-pipeline sync."""

from __future__ import annotations

import logging

from models.entities import GraphBatch, GraphEdge, GraphEntity

logger = logging.getLogger(__name__)


def _edge_key(edge: GraphEdge) -> tuple[str, str, str]:
    return (edge.source_id, edge.target_id, edge.relation.value)


def merge_graph_batches(*batches: GraphBatch) -> GraphBatch:
    """Merge batches: entities by id (later batch wins), deduped edges, orphan filter.

    Edges whose ``source_id`` or ``target_id`` are not in the merged entity set are
    dropped with a warning.
    """
    entity_by_id: dict[str, GraphEntity] = {}
    for batch in batches:
        for ent in batch.entities:
            entity_by_id[ent.id] = ent

    entity_ids = set(entity_by_id.keys())
    seen_edges: set[tuple[str, str, str]] = set()
    merged_edges: list[GraphEdge] = []

    for batch in batches:
        for edge in batch.edges:
            key = _edge_key(edge)
            if key in seen_edges:
                continue
            if edge.source_id not in entity_ids or edge.target_id not in entity_ids:
                logger.warning(
                    "dropping orphan edge %s -> %s (%s): endpoint not in merged entities",
                    edge.source_id,
                    edge.target_id,
                    edge.relation.value,
                )
                continue
            seen_edges.add(key)
            merged_edges.append(edge)

    return GraphBatch(
        entities=list(entity_by_id.values()),
        edges=merged_edges,
    )
