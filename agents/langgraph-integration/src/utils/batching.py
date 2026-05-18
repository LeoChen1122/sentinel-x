"""GraphBatch chunking helpers for sync (step 5)."""

from __future__ import annotations

from models.entities import GraphBatch, GraphEdge, GraphEntity


def chunk_graph_batch(
    batch: GraphBatch,
    *,
    max_entities: int = 500,
    max_edges: int = 500,
) -> list[GraphBatch]:
    """Split a batch into smaller chunks for rate-limited sync.

    Step 5: sync/pipeline.py will call this before ``stream_sentinel_run``.
    """
    if max_entities < 1 or max_edges < 1:
        raise ValueError("max_entities and max_edges must be positive")

    if len(batch.entities) <= max_entities and len(batch.edges) <= max_edges:
        return [batch]

    chunks: list[GraphBatch] = []
    entity_slices = [
        batch.entities[i : i + max_entities]
        for i in range(0, len(batch.entities), max_entities)
    ]
    edge_slices = [
        batch.edges[i : i + max_edges] for i in range(0, len(batch.edges), max_edges)
    ]
    n = max(len(entity_slices), len(edge_slices))
    for i in range(n):
        ents = entity_slices[i] if i < len(entity_slices) else []
        edges = edge_slices[i] if i < len(edge_slices) else []
        chunks.append(GraphBatch(entities=list(ents), edges=list(edges)))
    return chunks
