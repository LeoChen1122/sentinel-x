"""Push ``GraphBatch`` to LangGraph with incremental sync, retry, and rate limits.

Use a stable ``thread_id`` per cluster/tenant so Pod, Event, and Inspection data
accumulate on the same LangGraph thread checkpoint (see step 6/8 README).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Iterator

from adapter.inspections import inspection_mcp_to_batch
from adapter.k8s import pods_events_to_batch
from adapter.metrics import pods_with_metrics_to_batch
from adapter.types import McpListResponse, McpPromQueryResponse
from clients.langgraph_client import stream_sentinel_run
from langgraph_sdk.client import SyncLangGraphClient
from models.entities import GraphBatch
from models.scope import resolve_cluster_id, resolve_langgraph_thread_id
from sync.retry import retry_call
from sync.state import SyncState, SyncStateRegistry
from utils.batching import chunk_graph_batch
from utils.graph_merge import merge_graph_batches


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip() or str(default)
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip() or str(default)
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class SyncPushResult:
    chunks_sent: int
    entities_pushed: int
    edges_pushed: int
    skipped_unchanged: int


def _consume_stream(stream: Iterator[Any]) -> list[Any]:
    return list(stream)


def _resolve_sync_scope(
    *mcps: McpListResponse,
    cluster_id: str | None = None,
    tenant_id: str | None = None,
    thread_id: str | None = None,
    state: SyncState | None = None,
    state_registry: SyncStateRegistry | None = None,
) -> tuple[str, str | None, str, SyncState]:
    """Resolve cluster, tenant, LangGraph thread, and partitioned ``SyncState``."""
    cid = resolve_cluster_id(*mcps, cluster_id=cluster_id)
    tid = tenant_id.strip() if tenant_id and str(tenant_id).strip() else None
    thread = resolve_langgraph_thread_id(
        thread_id=thread_id,
        cluster_id=cid,
        tenant_id=tid,
    )
    if state is not None:
        sync_state = state
    else:
        registry = state_registry or SyncStateRegistry.from_env()
        sync_state = registry.get(cid, tid)
    return cid, tid, thread, sync_state


def push_graph_batch(
    batch: GraphBatch,
    *,
    client: SyncLangGraphClient | None = None,
    wire_only: bool = True,
    thread_id: str | None = None,
) -> Iterator[Any]:
    """Stream one sentinel run with entities/edges in ``payload``."""
    payload = batch.to_dict(wire_only=wire_only)
    return stream_sentinel_run(payload, client=client, thread_id=thread_id)


def push_graph_batch_resilient(
    batch: GraphBatch,
    *,
    client: SyncLangGraphClient | None = None,
    state: SyncState | None = None,
    wire_only: bool = True,
    thread_id: str | None = None,
    incremental: bool | None = None,
    max_entities: int | None = None,
    max_edges: int | None = None,
    min_interval_sec: float | None = None,
) -> SyncPushResult:
    """Push with incremental filter, chunking, retry, and inter-chunk rate limit."""
    sync_state = state if state is not None else SyncState.from_env()
    use_incremental = (
        incremental if incremental is not None else _env_bool("LANGGRAPH_SYNC_INCREMENTAL", True)
    )
    skipped = 0
    to_push = batch
    if use_incremental:
        to_push, skipped = sync_state.filter_batch(batch)

    if not to_push.entities and not to_push.edges:
        return SyncPushResult(
            chunks_sent=0,
            entities_pushed=0,
            edges_pushed=0,
            skipped_unchanged=skipped,
        )

    me = max_entities if max_entities is not None else _env_int(
        "LANGGRAPH_SYNC_CHUNK_MAX_ENTITIES", 500
    )
    medge = max_edges if max_edges is not None else _env_int(
        "LANGGRAPH_SYNC_CHUNK_MAX_EDGES", 500
    )
    interval = (
        min_interval_sec
        if min_interval_sec is not None
        else _env_float("LANGGRAPH_SYNC_MIN_INTERVAL_SEC", 0.2)
    )

    chunks = chunk_graph_batch(to_push, max_entities=me, max_edges=medge)
    entities_pushed = 0
    edges_pushed = 0
    chunks_sent = 0

    for i, chunk in enumerate(chunks):
        if not chunk.entities and not chunk.edges:
            continue

        def _push(c: GraphBatch = chunk) -> list[Any]:
            return _consume_stream(
                push_graph_batch(
                    c,
                    client=client,
                    wire_only=wire_only,
                    thread_id=thread_id,
                )
            )

        retry_call(_push)
        chunks_sent += 1
        entities_pushed += len(chunk.entities)
        edges_pushed += len(chunk.edges)
        if i < len(chunks) - 1 and interval > 0:
            time.sleep(interval)

    sync_state.update_from_batch(to_push)

    return SyncPushResult(
        chunks_sent=chunks_sent,
        entities_pushed=entities_pushed,
        edges_pushed=edges_pushed,
        skipped_unchanged=skipped,
    )


def sync_pods_and_events(
    pods_mcp: dict[str, Any],
    events_mcp: dict[str, Any],
    namespace: str,
    *,
    client: SyncLangGraphClient | None = None,
    link_pod_events: bool = True,
    wire_only: bool = True,
    cluster_id: str | None = None,
    tenant_id: str | None = None,
) -> Iterator[Any]:
    """Build batch from MCP JSON and push to LangGraph (single shot, no retry)."""
    cid, tid, thread, _state = _resolve_sync_scope(
        pods_mcp,
        events_mcp,
        cluster_id=cluster_id,
        tenant_id=tenant_id,
    )
    batch = pods_events_to_batch(
        pods_mcp,
        events_mcp,
        namespace,
        cluster_id=cid,
        tenant_id=tid,
        link_pod_events=link_pod_events,
    )
    return push_graph_batch(batch, client=client, wire_only=wire_only, thread_id=thread)


def sync_pods_and_events_resilient(
    pods_mcp: McpListResponse,
    events_mcp: McpListResponse,
    namespace: str,
    *,
    cluster_id: str | None = None,
    tenant_id: str | None = None,
    client: SyncLangGraphClient | None = None,
    state: SyncState | None = None,
    state_registry: SyncStateRegistry | None = None,
    link_pod_events: bool = True,
    wire_only: bool = True,
    thread_id: str | None = None,
    **push_kwargs: Any,
) -> SyncPushResult:
    """Event-triggered sync: MCP JSON → adapter → resilient push."""
    cid, tid, thread, sync_state = _resolve_sync_scope(
        pods_mcp,
        events_mcp,
        cluster_id=cluster_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        state=state,
        state_registry=state_registry,
    )
    batch = pods_events_to_batch(
        pods_mcp,
        events_mcp,
        namespace,
        cluster_id=cid,
        tenant_id=tid,
        link_pod_events=link_pod_events,
    )
    return push_graph_batch_resilient(
        batch,
        client=client,
        state=sync_state,
        wire_only=wire_only,
        thread_id=thread,
        **push_kwargs,
    )


def sync_inspections_resilient(
    inspection_mcp: McpListResponse,
    *,
    cluster_id: str | None = None,
    tenant_id: str | None = None,
    client: SyncLangGraphClient | None = None,
    state: SyncState | None = None,
    state_registry: SyncStateRegistry | None = None,
    link_pods: list[str] | None = None,
    link_nodes: list[str] | None = None,
    wire_only: bool = True,
    thread_id: str | None = None,
    **push_kwargs: Any,
) -> SyncPushResult:
    """Sync inspection MCP JSON → graph entities and ``inspects_*`` edges."""
    cid, tid, thread, sync_state = _resolve_sync_scope(
        inspection_mcp,
        cluster_id=cluster_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        state=state,
        state_registry=state_registry,
    )
    batch = inspection_mcp_to_batch(
        inspection_mcp,
        cluster_id=cid,
        tenant_id=tid,
        link_pods=link_pods,
        link_nodes=link_nodes,
    )
    return push_graph_batch_resilient(
        batch,
        client=client,
        state=sync_state,
        wire_only=wire_only,
        thread_id=thread,
        **push_kwargs,
    )


def sync_pod_metrics_resilient(
    pods_mcp: McpListResponse,
    cpu_mcp: McpPromQueryResponse,
    memory_mcp: McpPromQueryResponse,
    namespace: str,
    *,
    cluster_id: str | None = None,
    tenant_id: str | None = None,
    client: SyncLangGraphClient | None = None,
    state: SyncState | None = None,
    state_registry: SyncStateRegistry | None = None,
    wire_only: bool = True,
    thread_id: str | None = None,
    **push_kwargs: Any,
) -> SyncPushResult:
    """Prometheus metrics enrichment: K8s pods + Prom vectors → resilient push."""
    cid, tid, thread, sync_state = _resolve_sync_scope(
        pods_mcp,
        cpu_mcp,
        memory_mcp,
        cluster_id=cluster_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        state=state,
        state_registry=state_registry,
    )
    batch = pods_with_metrics_to_batch(
        pods_mcp,
        cpu_mcp,
        memory_mcp,
        namespace,
        cluster_id=cid,
        tenant_id=tid,
    )
    return push_graph_batch_resilient(
        batch,
        client=client,
        state=sync_state,
        wire_only=wire_only,
        thread_id=thread,
        **push_kwargs,
    )


def sync_pods_events_inspections_resilient(
    pods_mcp: McpListResponse,
    events_mcp: McpListResponse,
    namespace: str,
    inspection_mcp: McpListResponse,
    *,
    cluster_id: str | None = None,
    tenant_id: str | None = None,
    client: SyncLangGraphClient | None = None,
    state: SyncState | None = None,
    state_registry: SyncStateRegistry | None = None,
    link_pod_events: bool = True,
    link_pods: list[str] | None = None,
    link_nodes: list[str] | None = None,
    wire_only: bool = True,
    thread_id: str | None = None,
    **push_kwargs: Any,
) -> SyncPushResult:
    """Sync Pod + Event + Inspection MCP payloads in one merged resilient push."""
    cid, tid, thread, sync_state = _resolve_sync_scope(
        pods_mcp,
        events_mcp,
        inspection_mcp,
        cluster_id=cluster_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        state=state,
        state_registry=state_registry,
    )
    pe_batch = pods_events_to_batch(
        pods_mcp,
        events_mcp,
        namespace,
        cluster_id=cid,
        tenant_id=tid,
        link_pod_events=link_pod_events,
    )
    insp_batch = inspection_mcp_to_batch(
        inspection_mcp,
        cluster_id=cid,
        tenant_id=tid,
        link_pods=link_pods,
        link_nodes=link_nodes,
    )
    batch = merge_graph_batches(pe_batch, insp_batch)
    return push_graph_batch_resilient(
        batch,
        client=client,
        state=sync_state,
        wire_only=wire_only,
        thread_id=thread,
        **push_kwargs,
    )
