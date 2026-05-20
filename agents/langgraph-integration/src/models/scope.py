"""Cluster / tenant scope helpers for graph entities (phase 4-0)."""

from __future__ import annotations

import uuid
from typing import Any

# Deterministic UUID5 namespace for LangGraph API thread_id (not pod/graph entity IDs).
SENTINEL_LANGGRAPH_THREAD_NS = uuid.UUID("a3b8c9d1-4e5f-6789-abcd-ef0123456789")


def resolve_cluster_id(
    *mcps: dict[str, Any],
    cluster_id: str | None = None,
) -> str:
    """Resolve ``cluster_id`` from explicit arg or MCP payload field."""
    if cluster_id is not None and str(cluster_id).strip():
        return str(cluster_id).strip()
    for mcp in mcps:
        if isinstance(mcp, dict):
            cid = mcp.get("cluster_id")
            if cid is not None and str(cid).strip():
                return str(cid).strip()
    raise ValueError("cluster_id required (argument or MCP payload)")


def stamp_scope(
    properties: dict[str, Any],
    *,
    cluster_id: str,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Attach ``cluster_id`` and optional ``tenant_id`` to entity properties."""
    out = dict(properties)
    out["cluster_id"] = cluster_id
    if tenant_id is not None:
        out["tenant_id"] = tenant_id
    return out


def sync_thread_id(cluster_id: str, tenant_id: str | None = None) -> str:
    """Logical thread key for tenant+cluster (logs, docs, sync state partition)."""
    tenant = (tenant_id or "default").strip() or "default"
    cid = cluster_id.strip()
    if not cid:
        raise ValueError("cluster_id required for sync_thread_id")
    return f"{tenant}:{cid}"


def _thread_id_to_uuid(name: str) -> str:
    return str(uuid.uuid5(SENTINEL_LANGGRAPH_THREAD_NS, name.strip()))


def langgraph_thread_id(cluster_id: str, tenant_id: str | None = None) -> str:
    """LangGraph API ``thread_id`` (standard UUID) for one tenant+cluster checkpoint."""
    return _thread_id_to_uuid(sync_thread_id(cluster_id, tenant_id))


def resolve_langgraph_thread_id(
    *,
    thread_id: str | None = None,
    cluster_id: str | None = None,
    tenant_id: str | None = None,
) -> str:
    """Resolve a LangGraph-safe UUID thread id.

    - If ``thread_id`` is already a UUID string, return it unchanged.
    - If ``thread_id`` is a non-UUID label (e.g. ``my-thread-1``), map via UUID5.
    - Else derive from ``cluster_id`` / ``tenant_id`` via :func:`langgraph_thread_id`.
    """
    if thread_id is not None and str(thread_id).strip():
        raw = str(thread_id).strip()
        try:
            uuid.UUID(raw)
            return raw
        except ValueError:
            return _thread_id_to_uuid(raw)
    if cluster_id is not None and str(cluster_id).strip():
        return langgraph_thread_id(str(cluster_id).strip(), tenant_id)
    raise ValueError(
        "thread_id or cluster_id required for resolve_langgraph_thread_id"
    )
