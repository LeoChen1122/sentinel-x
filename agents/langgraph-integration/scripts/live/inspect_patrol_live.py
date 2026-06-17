#!/usr/bin/env python3
"""W7: patrol graph for unhealthy pods and trigger one inspect run."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from clients.langgraph_client import get_langgraph_client, verify_langgraph_connection  # noqa: E402
from models.scope import resolve_langgraph_thread_id  # noqa: E402
from trigger.config import patrol_config  # noqa: E402
from trigger.inspect_trigger import trigger_inspect  # noqa: E402
from trigger.patrol import (  # noqa: E402
    find_inspect_candidates,
    find_inspect_candidates_multi,
    load_patrol_state,
    mark_pod_inspected,
    select_pod_to_inspect,
)


def _run_sync_first(root: Path) -> int:
    sync_script = root / "agents/langgraph-integration/scripts/live/mcp_k8s_sync_live.py"
    if not sync_script.is_file():
        print(f"sync script missing: {sync_script}", file=sys.stderr)
        return 1
    py = os.environ.get("VENV_PYTHON") or sys.executable
    proc = subprocess.run([py, str(sync_script), "--skip-verify"], check=False)
    return int(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sentinel-X inspect patrol (W7)")
    parser.add_argument("--cluster-id", default=os.environ.get("CLUSTER_ID", "k3s-prod"))
    parser.add_argument("--namespace", default=os.environ.get("NAMESPACE", "kube-system"))
    parser.add_argument("--tenant-id", default=os.environ.get("TENANT_ID") or None)
    parser.add_argument("--thread-id", default=os.environ.get("LANGGRAPH_THREAD_ID") or None)
    parser.add_argument(
        "--dry-run",
        default=None,
        choices=("true", "false"),
        help="inspect dry_run (default: SENTINEL_PATROL_DRY_RUN env)",
    )
    parser.add_argument("--pod", default=None, help="Inspect this pod directly (skip patrol scan)")
    parser.add_argument(
        "--sync-first",
        action="store_true",
        help="Run mcp_k8s_sync_live.py before patrol",
    )
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()

    cfg = patrol_config()
    if not cfg.enabled:
        print(json.dumps({"status": "disabled", "message": "SENTINEL_PATROL_ENABLED=0"}))
        return 0

    root = Path(os.environ.get("SENTINEL_ROOT", _SRC.parents[2])).resolve()
    if args.sync_first:
        rc = _run_sync_first(root)
        if rc != 0:
            print(f"WARN: sync-first exit code={rc}", file=sys.stderr)

    if not os.environ.get("LANGGRAPH_API_URL", "").strip():
        os.environ["LANGGRAPH_API_URL"] = "http://127.0.0.1:2024"

    cid = str(args.cluster_id).strip()
    ns = str(args.namespace).strip()
    tid = resolve_langgraph_thread_id(
        thread_id=args.thread_id,
        cluster_id=cid,
        tenant_id=args.tenant_id,
    )

    client = get_langgraph_client()
    if not args.skip_verify:
        try:
            verify_langgraph_connection(client)
        except Exception as exc:
            print(f"LangGraph verify failed: {exc}", file=sys.stderr)
            return 1

    dry_run = cfg.default_dry_run if args.dry_run is None else args.dry_run == "true"

    if args.pod:
        pod_name = args.pod.strip()
        result = trigger_inspect(
            cluster_id=cid,
            namespace=ns,
            pod_name=pod_name,
            dry_run=dry_run,
            thread_id=tid,
            tenant_id=args.tenant_id,
            client=client,
        )
        _print_result(result, source="manual")
        return 0 if result.get("ok") else 1

    candidates = find_inspect_candidates_multi(
        thread_id=tid,
        cluster_id=cid,
        namespaces=cfg.namespaces,
        client=client,
        tenant_id=args.tenant_id,
    )
    if not candidates:
        print(
            json.dumps(
                {
                    "status": "no_candidates",
                    "count": 0,
                    "namespaces": list(cfg.namespaces),
                }
            )
        )
        return 2

    state = load_patrol_state(cfg.state_path)
    picked = select_pod_to_inspect(candidates, state, cfg=cfg)
    if picked is None:
        print(
            json.dumps(
                {
                    "status": "cooldown",
                    "candidates": len(candidates),
                    "message": "all candidates within cooldown",
                }
            )
        )
        return 2

    result = trigger_inspect(
        cluster_id=picked["cluster_id"],
        namespace=picked["namespace"],
        pod_name=picked["pod_name"],
        dry_run=dry_run,
        thread_id=tid,
        tenant_id=args.tenant_id,
        client=client,
    )
    result["patrol"] = {
        "severity": picked["severity"],
        "reason": picked["reason"],
        "pod_id": picked["pod_id"],
    }
    if result.get("ok"):
        mark_pod_inspected(picked["pod_id"], state, cfg=cfg)
    _print_result(result, source="patrol")
    return 0 if result.get("ok") else 1


def _print_result(result: dict, *, source: str) -> None:
    summary = {
        "status": "ok" if result.get("ok") else "failed",
        "source": source,
        "pod": result.get("pod_name"),
        "namespace": result.get("namespace"),
        "issues": result.get("issues"),
        "dry_run": result.get("dry_run"),
        "sandbox_pending": (result.get("execution") or {}).get("sandbox_pending"),
        "verified": (result.get("skill_verification") or {}).get("verified"),
    }
    print(json.dumps(summary, ensure_ascii=False))
    print(
        f"inspect {summary['status']}: pod={summary['pod']} issues={summary['issues']} "
        f"sandbox_pending={summary['sandbox_pending']} verified={summary['verified']}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
