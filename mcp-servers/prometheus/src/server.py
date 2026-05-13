from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from tools.prom_query import PROM_QUERY_TOOL_META, prom_query as run_prom_query

mcp = FastMCP("prometheus")


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
    meta=PROM_QUERY_TOOL_META,
)
def prom_query(promql: str, time: str | float | int | None = None) -> dict[str, Any]:
    """Run an instant PromQL query against Prometheus and return normalized results."""
    return run_prom_query(promql, time=time)


if __name__ == "__main__":
    mcp.run(transport="stdio")
