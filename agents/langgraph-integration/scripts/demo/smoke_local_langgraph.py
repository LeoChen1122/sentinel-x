#!/usr/bin/env python3
"""Step 8: verify Sentinel-X → local LangGraph (health + stream sentinel graph).

Usage (with ``langgraph dev`` running in agents/langgraph-server):

  set LANGGRAPH_API_URL=http://127.0.0.1:2024
  python agents/langgraph-integration/scripts/demo/smoke_local_langgraph.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from clients.langgraph_client import (  # noqa: E402
    get_langgraph_client,
    stream_sentinel_run,
    verify_langgraph_connection,
)


def main() -> int:
    client = get_langgraph_client()
    print("verify:", verify_langgraph_connection(client))
    print("stream sentinel run:")
    for chunk in stream_sentinel_run(
        {"source": "mcp", "results": []},
        client=client,
    ):
        print(f"  {chunk.event}: {chunk.data}")
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
