"""Cluster / tenant scope helpers for graph entities (phase 4-0)."""

from __future__ import annotations

from typing import Any


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
    """LangGraph ``thread_id`` for one tenant+cluster sync/query checkpoint."""
    tenant = (tenant_id or "default").strip() or "default"
    cid = cluster_id.strip()
    if not cid:
        raise ValueError("cluster_id required for sync_thread_id")
    return f"{tenant}:{cid}"
