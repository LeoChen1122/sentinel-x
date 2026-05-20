#!/usr/bin/env python3
"""Phase F: LangGraph dev E2E for inspect → diagnose → narrate → execute."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from clients.langgraph_client import (  # noqa: E402
    get_inspect_outputs_from_stream,
    get_langgraph_client,
    stream_sentinel_run,
)
from models.scope import resolve_langgraph_thread_id, sync_thread_id  # noqa: E402
from testing.multicluster_fixtures import CLUSTER_DEV, dual_cluster_rich_batch  # noqa: E402


def run_inspect_live(
    *,
    cluster_id: str,
    namespace: str,
    pod_name: str,
    tenant_id: str | None,
    dry_run: bool,
    thread_id: str | None,
) -> int:
    client = get_langgraph_client()
    tid = resolve_langgraph_thread_id(
        thread_id=thread_id,
        cluster_id=cluster_id,
        tenant_id=tenant_id,
    )
    logical_tid = sync_thread_id(cluster_id, tenant_id)

    payload = dual_cluster_rich_batch().to_dict(wire_only=True)
    inspect: dict[str, object] = {
        "cluster_id": cluster_id,
        "namespace": namespace,
        "pod_name": pod_name,
        "dry_run": dry_run,
    }
    if tenant_id:
        inspect["tenant_id"] = tenant_id
    payload["inspect"] = inspect

    print(f"thread_id={tid} (logical={logical_tid})")
    print(f"inspect={json.dumps(inspect, ensure_ascii=False)}")

    try:
        chunks = list(stream_sentinel_run(payload, client=client, thread_id=tid))
    except Exception as exc:
        print(f"\nLangGraph request failed: {exc}", file=sys.stderr)
        print(
            "Run verification first: python scripts/langgraph_live_verify.py",
            file=sys.stderr,
        )
        print(
            "Ensure langgraph dev is running in agents/langgraph-server "
            "and LANGGRAPH_API_URL matches the dev server port.",
            file=sys.stderr,
        )
        return 1
    outputs = get_inspect_outputs_from_stream(chunks)

    diagnosis = outputs.get("diagnosis") or {}
    execution = outputs.get("execution") or {}
    narrative = outputs.get("narrative") or {}

    print("\n--- diagnosis ---")
    print(json.dumps(diagnosis, indent=2, ensure_ascii=False))
    print("\n--- execution ---")
    print(json.dumps(execution, indent=2, ensure_ascii=False))
    print("\n--- narrative (summary) ---")
    print(narrative.get("summary", ""))
    print(f"narrative_source={narrative.get('narrative_source')}")

    if not diagnosis.get("issues"):
        print("WARN: no diagnosis issues", file=sys.stderr)
        return 1
    if not execution.get("actions_taken") and not execution.get("skipped"):
        if execution.get("ok") is False:
            print(f"execution policy error: {execution.get('error')}", file=sys.stderr)
        else:
            print("WARN: no actions_taken", file=sys.stderr)
            return 1
    print("\nOK: inspect LangGraph live demo complete")
    return 0


def main() -> int:
    if os.environ.get("LANGGRAPH_RUN_LIVE", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        print("Set LANGGRAPH_RUN_LIVE=1 and LANGGRAPH_API_URL", file=sys.stderr)
        return 1
    if not os.environ.get("LANGGRAPH_API_URL", "").strip():
        print("Set LANGGRAPH_API_URL (e.g. http://127.0.0.1:2024)", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description="LangGraph inspect E2E demo")
    parser.add_argument("--cluster-id", default=CLUSTER_DEV)
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--pod-name", default="crash-pod")
    parser.add_argument("--tenant-id", default=None)
    parser.add_argument("--thread-id", default=None)
    parser.add_argument(
        "--dry-run",
        default="true",
        choices=("true", "false"),
        help="inspect.dry_run (false still simulated without SENTINEL_EXECUTE_LIVE)",
    )
    args = parser.parse_args()
    dry_run = args.dry_run == "true"
    return run_inspect_live(
        cluster_id=args.cluster_id,
        namespace=args.namespace,
        pod_name=args.pod_name,
        tenant_id=args.tenant_id,
        dry_run=dry_run,
        thread_id=args.thread_id,
    )


if __name__ == "__main__":
    raise SystemExit(main())
