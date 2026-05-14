from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from tools.k8s_get_events import K8S_GET_EVENTS_TOOL_META, k8s_get_events as run_k8s_get_events
from tools.k8s_get_pods import K8S_GET_PODS_TOOL_META, k8s_get_pods as run_k8s_get_pods

mcp = FastMCP("k8s")


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
    meta=K8S_GET_PODS_TOOL_META,
)
def k8s_get_pods(namespace: str, limit: int | None = None) -> dict[str, Any]:
    """List Pods in a namespace and return normalized ``{query, results}`` for agents."""
    return run_k8s_get_pods(namespace, limit)


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
    meta=K8S_GET_EVENTS_TOOL_META,
)
def k8s_get_events(
    namespace: str,
    pod_name: str | None = None,
    limit: int | None = None,
    since_time: str | None = None,
    api_limit: int | None = None,
    field_selector: str | None = None,
) -> dict[str, Any]:
    """List Events in a namespace (optionally one Pod) and return normalized results."""
    return run_k8s_get_events(
        namespace,
        pod_name,
        limit,
        since_time=since_time,
        api_limit=api_limit,
        field_selector=field_selector,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
