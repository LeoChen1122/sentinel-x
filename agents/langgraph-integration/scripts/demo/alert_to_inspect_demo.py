#!/usr/bin/env python3
"""W7 demo: patrol or API webhook → inspect → diagnosis → sandbox."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _run_patrol(sync_first: bool, dry_run: str | None) -> int:
    root = Path(os.environ.get("SENTINEL_ROOT", _SRC.parents[2])).resolve()
    script = root / "agents/langgraph-integration/scripts/live/inspect_patrol_live.py"
    py = os.environ.get("VENV_PYTHON") or sys.executable
    cmd = [py, str(script)]
    if sync_first:
        cmd.append("--sync-first")
    if dry_run is not None:
        cmd.extend(["--dry-run", dry_run])
    return subprocess.run(cmd, check=False).returncode


def _run_api_inspect(api_url: str, pod: str, namespace: str, dry_run: bool) -> int:
    body = json.dumps(
        {
            "pod_name": pod,
            "namespace": namespace,
            "dry_run": dry_run,
            "cluster_id": os.environ.get("CLUSTER_ID", "k3s-prod"),
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/v1/inspect",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    token = os.environ.get("SENTINEL_API_TOKEN", "").strip()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"API request failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0 if data.get("ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="W7 alert → inspect demo")
    parser.add_argument(
        "--mode",
        choices=("patrol", "api"),
        default="patrol",
        help="patrol=inspect_patrol_live.py; api=POST /v1/inspect",
    )
    parser.add_argument("--sync-first", action="store_true")
    parser.add_argument("--dry-run", default=None, choices=("true", "false"))
    parser.add_argument("--pod", default=None, help="Required for api mode")
    parser.add_argument("--namespace", default=os.environ.get("NAMESPACE", "kube-system"))
    parser.add_argument("--api-url", default=os.environ.get("SENTINEL_API_URL", "http://127.0.0.1:8080"))
    args = parser.parse_args()

    if os.environ.get("LANGGRAPH_RUN_LIVE", "").strip().lower() not in ("1", "true", "yes"):
        print("Set LANGGRAPH_RUN_LIVE=1 for live demo", file=sys.stderr)
        return 1

    if args.mode == "patrol":
        return _run_patrol(args.sync_first, args.dry_run)

    if not args.pod:
        print("--pod required for api mode", file=sys.stderr)
        return 1
    dry = True if args.dry_run is None else args.dry_run == "true"
    return _run_api_inspect(args.api_url, args.pod, args.namespace, dry)


if __name__ == "__main__":
    raise SystemExit(main())
