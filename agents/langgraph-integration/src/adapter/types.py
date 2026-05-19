"""MCP tool response shapes shared by adapters."""

from __future__ import annotations

from typing import Any, TypedDict


class McpListResponse(TypedDict, total=False):
    """Normalized MCP list tools: ``k8s_get_pods``, ``k8s_get_events``, etc."""

    query: str
    results: list[dict[str, Any]]
    cluster_id: str
