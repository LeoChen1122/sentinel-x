#!/usr/bin/env python3
"""Phase F: LangGraph dev E2E for inspect → diagnose → narrate → execute."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
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
    use_llm: bool | None,
    thread_only: bool,
) -> int:
    client = get_langgraph_client()
    tid = resolve_langgraph_thread_id(
        thread_id=thread_id,
        cluster_id=cluster_id,
        tenant_id=tenant_id,
    )
    logical_tid = sync_thread_id(cluster_id, tenant_id)

    inspect: dict[str, object] = {
        "cluster_id": cluster_id,
        "namespace": namespace,
        "pod_name": pod_name,
        "dry_run": dry_run,
    }
    if use_llm is not None:
        inspect["use_llm"] = use_llm
    if tenant_id:
        inspect["tenant_id"] = tenant_id

    if thread_only:
        payload: dict[str, object] = {"inspect": inspect}
    else:
        payload = dual_cluster_rich_batch().to_dict(wire_only=True)
        payload["inspect"] = inspect

    print(f"thread_id={tid} (logical={logical_tid})")
    print(f"payload_mode={'thread_only' if thread_only else 'mock_ingest+inspect'}")
    print(f"inspect={json.dumps(inspect, ensure_ascii=False)}")
    if use_llm:
        timeout = os.environ.get("SENTINEL_LLM_TIMEOUT_SEC", "60")
        print(
            f"NOTE: LLM runs inside langgraph dev (not this shell). "
            f"First call may take up to {timeout}s if DashScope is slow.",
            file=sys.stderr,
        )

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
    llm_err = narrative.get("llm_error")
    if llm_err:
        print(f"llm_error={llm_err}", file=sys.stderr)
    md = narrative.get("markdown")
    if isinstance(md, str) and md.strip():
        print("\n--- narrative (markdown excerpt) ---")
        print(md[:800] + ("..." if len(md) > 800 else ""))

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
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Set inspect.use_llm=true (requires LLM env on langgraph dev server)",
    )
    parser.add_argument(
        "--thread-only",
        action="store_true",
        help="Do not ingest mock graph; use existing thread checkpoint (live sync data)",
    )
    args = parser.parse_args()
    dry_run = args.dry_run == "true"
    use_llm: bool | None = True if args.llm else None
    if args.llm:
        from agent.llm import llm_narrative_config  # noqa: E402

        print("llm_config (client shell):", json.dumps(llm_narrative_config(), ensure_ascii=False))
        print(
            "LLM narrative executes in langgraph dev — set SENTINEL_LLM_ENABLED=1, "
            "DASHSCOPE_API_KEY, OPENAI_BASE_URL in agents/langgraph-server/.env "
            "and restart langgraph dev.",
            file=sys.stderr,
        )
    return run_inspect_live(
        cluster_id=args.cluster_id,
        namespace=args.namespace,
        pod_name=args.pod_name,
        tenant_id=args.tenant_id,
        dry_run=dry_run,
        thread_id=args.thread_id,
        use_llm=use_llm,
        thread_only=args.thread_only,
    )


if __name__ == "__main__":
    raise SystemExit(main())
