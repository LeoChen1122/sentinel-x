"""Fetch Prometheus MCP tool JSON via docker exec or snapshot file (Phase 1c)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, TypedDict

from adapter.types import McpPromQueryResponse

DEFAULT_CPU_PROMQL = (
    'sum(rate(container_cpu_usage_seconds_total{container!="",pod!=""}[5m])) '
    "by (pod, namespace)"
)
DEFAULT_MEMORY_PROMQL = (
    'sum(container_memory_working_set_bytes{container!="",pod!=""}) '
    "by (pod, namespace)"
)

_DOCKER_FETCH_SCRIPT = f"""
import json
import os
from tools.prom_query import prom_query

cpu_q = os.environ.get("SENTINEL_PROM_CPU_PROMQL", "").strip()
mem_q = os.environ.get("SENTINEL_PROM_MEMORY_PROMQL", "").strip()
if not cpu_q:
    cpu_q = {DEFAULT_CPU_PROMQL!r}
if not mem_q:
    mem_q = {DEFAULT_MEMORY_PROMQL!r}

print(
    json.dumps(
        {{"cpu": prom_query(cpu_q), "memory": prom_query(mem_q)}},
        ensure_ascii=False,
    )
)
"""


class PromMetricsSnapshot(TypedDict):
    cpu: McpPromQueryResponse
    memory: McpPromQueryResponse


def _parse_metrics_payload(raw: dict[str, Any]) -> PromMetricsSnapshot:
    cpu = raw.get("cpu")
    memory = raw.get("memory")
    if not isinstance(cpu, dict) or not isinstance(memory, dict):
        raise ValueError("snapshot must contain cpu and memory objects")
    return PromMetricsSnapshot(cpu=McpPromQueryResponse(**cpu), memory=McpPromQueryResponse(**memory))


def load_prom_mcp_snapshot(path: str | Path) -> PromMetricsSnapshot:
    """Load ``cpu`` / ``memory`` from a JSON file written by MCP export."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("snapshot must be a JSON object")
    return _parse_metrics_payload(raw)


def fetch_prom_mcp_via_docker(
    container: str,
    *,
    docker_bin: str = "docker",
    cpu_promql: str | None = None,
    memory_promql: str | None = None,
) -> PromMetricsSnapshot:
    """Run ``prom_query`` for CPU/memory inside the MCP container."""
    name = container.strip()
    if not name:
        raise ValueError("container name required")

    env: list[str] = []
    if cpu_promql and cpu_promql.strip():
        env.extend(["-e", f"SENTINEL_PROM_CPU_PROMQL={cpu_promql.strip()}"])
    if memory_promql and memory_promql.strip():
        env.extend(["-e", f"SENTINEL_PROM_MEMORY_PROMQL={memory_promql.strip()}"])

    proc = subprocess.run(
        [
            docker_bin,
            "exec",
            "-i",
            *env,
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
        raise RuntimeError(f"docker exec Prom MCP fetch failed: {err or proc.returncode}")

    stdout = proc.stdout.strip()
    if not stdout:
        raise RuntimeError("docker exec Prom MCP fetch returned empty output")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Prom MCP fetch output is not JSON: {stdout[:200]}") from e

    if not isinstance(data, dict):
        raise RuntimeError("Prom MCP fetch JSON must be an object")

    snap = _parse_metrics_payload(data)
    cpu_n = len(snap["cpu"].get("results") or [])
    mem_n = len(snap["memory"].get("results") or [])
    if cpu_n == 0 and mem_n == 0:
        raise RuntimeError(
            "Prom MCP returned 0 cpu and 0 memory series; "
            "check PROMETHEUS_BASE_URL and cAdvisor metrics"
        )
    return snap


def attach_cluster_id(
    snap: PromMetricsSnapshot,
    cluster_id: str,
) -> PromMetricsSnapshot:
    """Stamp ``cluster_id`` on both query responses for adapter scope."""
    cid = cluster_id.strip()
    if not cid:
        raise ValueError("cluster_id required")
    cpu: dict[str, Any] = dict(snap["cpu"])
    memory: dict[str, Any] = dict(snap["memory"])
    cpu["cluster_id"] = cid
    memory["cluster_id"] = cid
    return PromMetricsSnapshot(cpu=McpPromQueryResponse(**cpu), memory=McpPromQueryResponse(**memory))


def promql_from_env() -> tuple[str | None, str | None]:
    """Optional PromQL overrides from ``SENTINEL_PROM_CPU_PROMQL`` / ``MEMORY``."""
    cpu = os.environ.get("SENTINEL_PROM_CPU_PROMQL", "").strip() or None
    mem = os.environ.get("SENTINEL_PROM_MEMORY_PROMQL", "").strip() or None
    return cpu, mem
