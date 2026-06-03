"""Fetch K8s MCP tool JSON via docker exec or snapshot file (Phase 1b)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from adapter.types import McpListResponse

_DOCKER_FETCH_SCRIPT = r"""
import json
import os
from tools.k8s_get_pods import k8s_get_pods
from tools.k8s_get_events import k8s_get_events

ns = os.environ.get("SENTINEL_MCP_NAMESPACE", "default").strip() or "default"
print(
    json.dumps(
        {"pods": k8s_get_pods(ns), "events": k8s_get_events(ns)},
        ensure_ascii=False,
    )
)
"""


def load_k8s_mcp_snapshot(path: str | Path) -> tuple[McpListResponse, McpListResponse]:
    """Load ``pods`` / ``events`` from a JSON file written by MCP export."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("snapshot must be a JSON object")
    pods = raw.get("pods")
    events = raw.get("events")
    if not isinstance(pods, dict) or not isinstance(events, dict):
        raise ValueError("snapshot must contain pods and events objects")
    return McpListResponse(**pods), McpListResponse(**events)


def fetch_k8s_mcp_via_docker(
    container: str,
    namespace: str,
    *,
    docker_bin: str = "docker",
) -> tuple[McpListResponse, McpListResponse]:
    """Run ``k8s_get_pods`` / ``k8s_get_events`` inside the MCP container."""
    name = container.strip()
    ns = namespace.strip()
    if not name:
        raise ValueError("container name required")
    if not ns:
        raise ValueError("namespace required")

    proc = subprocess.run(
       [
            docker_bin,
            "exec",
            "-i",
            "-e",
            f"SENTINEL_MCP_NAMESPACE={ns}",
            name,
            "bash",
            "-lc",
            "cd /app/src && python -",
        ],
        input=_DOCKER_FETCH_SCRIPT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"docker exec MCP fetch failed: {err or proc.returncode}")

    stdout = proc.stdout.strip()
    if not stdout:
        raise RuntimeError("docker exec MCP fetch returned empty output")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"MCP fetch output is not JSON: {stdout[:200]}") from e

    pods = data.get("pods")
    events = data.get("events")
    if not isinstance(pods, dict) or not isinstance(events, dict):
        raise RuntimeError("MCP fetch JSON missing pods/events objects")

    pod_count = len(pods.get("results") or [])
    if pod_count == 0:
        raise RuntimeError(
            f"MCP returned 0 pods in namespace {ns!r}; check NAMESPACE and RBAC"
        )

    return McpListResponse(**pods), McpListResponse(**events)


def attach_cluster_id(
    pods_mcp: McpListResponse,
    events_mcp: McpListResponse,
    cluster_id: str,
) -> tuple[McpListResponse, McpListResponse]:
    """Stamp ``cluster_id`` for adapter scope resolution."""
    cid = cluster_id.strip()
    if not cid:
        raise ValueError("cluster_id required")
    pods: dict[str, Any] = dict(pods_mcp)
    events: dict[str, Any] = dict(events_mcp)
    pods["cluster_id"] = cid
    events["cluster_id"] = cid
    return McpListResponse(**pods), McpListResponse(**events)
