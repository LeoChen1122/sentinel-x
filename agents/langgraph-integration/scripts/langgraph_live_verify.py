#!/usr/bin/env python3
"""Step-by-step LangGraph dev connectivity and inspect pipeline verification."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from clients.langgraph_client import (  # noqa: E402
    DEFAULT_GRAPH_ID,
    ensure_langgraph_thread,
    find_sentinel_graph,
    get_inspect_outputs_from_stream,
    get_langgraph_client,
    stream_sentinel_run,
    verify_langgraph_connection,
)
from models.scope import langgraph_thread_id, sync_thread_id  # noqa: E402
from testing.multicluster_fixtures import CLUSTER_DEV, dual_cluster_rich_batch  # noqa: E402

_VERIFY_HINT = (
    "Start langgraph dev in agents/langgraph-server and match LANGGRAPH_API_URL "
    "(default http://127.0.0.1:2024)."
)


def _step(name: str, ok: bool, detail: str = "") -> bool:
    mark = "OK" if ok else "FAIL"
    line = f"[{mark}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return ok


def main() -> int:
    print("=== LangGraph dev verification ===\n")

    url = os.environ.get("LANGGRAPH_API_URL", "").strip()
    live = os.environ.get("LANGGRAPH_RUN_LIVE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if not _step("LANGGRAPH_API_URL set", bool(url), url or "(missing)"):
        print(_VERIFY_HINT, file=sys.stderr)
        return 1
    if not _step("LANGGRAPH_RUN_LIVE=1", live):
        print("Set LANGGRAPH_RUN_LIVE=1 for live verification.", file=sys.stderr)
        return 1

    try:
        client = get_langgraph_client()
    except Exception as exc:
        _step("get_langgraph_client", False, str(exc))
        print(_VERIFY_HINT, file=sys.stderr)
        return 1

    try:
        conn = verify_langgraph_connection(client)
        _step("assistants.search (connectivity)", conn.get("ok", False))
    except Exception as exc:
        _step("assistants.search (connectivity)", False, str(exc))
        traceback.print_exc()
        print(_VERIFY_HINT, file=sys.stderr)
        return 1

    graph_row = find_sentinel_graph(client)
    if not _step(
        f"graph '{DEFAULT_GRAPH_ID}' registered",
        graph_row is not None,
        str(graph_row.get("graph_id", graph_row)) if graph_row else "not in search results",
    ):
        print(
            f"Run `langgraph dev` in langgraph-server; langgraph.json must define graphs.{DEFAULT_GRAPH_ID}",
            file=sys.stderr,
        )
        return 1

    tid = langgraph_thread_id(CLUSTER_DEV)
    logical = sync_thread_id(CLUSTER_DEV)
    try:
        ensured = ensure_langgraph_thread(client, tid)
        _step(
            "ensure_langgraph_thread",
            ensured == tid,
            f"uuid={ensured} logical={logical}",
        )
    except Exception as exc:
        _step("ensure_langgraph_thread", False, str(exc))
        traceback.print_exc()
        return 1

    try:
        chunks = list(
            stream_sentinel_run(
                {"entities": [], "edges": []},
                client=client,
                thread_id=tid,
            )
        )
        _step("minimal stream (entities=[])", len(chunks) > 0, f"chunks={len(chunks)}")
    except Exception as exc:
        _step("minimal stream (entities=[])", False, str(exc))
        traceback.print_exc()
        return 1

    payload = dual_cluster_rich_batch().to_dict(wire_only=True)
    payload["inspect"] = {
        "cluster_id": CLUSTER_DEV,
        "namespace": "default",
        "pod_name": "crash-pod",
        "dry_run": True,
    }
    try:
        chunks = list(stream_sentinel_run(payload, client=client, thread_id=tid))
        outputs = get_inspect_outputs_from_stream(chunks)
        issues = (outputs.get("diagnosis") or {}).get("issues") or []
        exec_src = (outputs.get("execution") or {}).get("execution_source")
        narr_src = (outputs.get("narrative") or {}).get("narrative_source")
        inspect_ok = "CrashLoop" in issues and exec_src == "registry_v1"
        _step(
            "inspect pipeline on dev graph",
            inspect_ok,
            f"issues={issues} execution_source={exec_src} narrative_source={narr_src}",
        )
        if not inspect_ok:
            return 1
    except Exception as exc:
        _step("inspect pipeline on dev graph", False, str(exc))
        traceback.print_exc()
        print("\nTip: python scripts/langgraph_live_verify.py", file=sys.stderr)
        return 1

    print("\nAll checks passed. Run: python scripts/inspect_langgraph_live_demo.py --pod-name crash-pod")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
