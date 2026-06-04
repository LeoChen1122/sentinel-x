"""Adapter: Prometheus MCP vector results → Pod property enrichment (Phase 1c)."""

from __future__ import annotations

import logging
from typing import Any

from adapter.pods import _pod_name_from_row
from adapter.types import McpListResponse, McpPromQueryResponse
from models.entities import GraphBatch, GraphEntity, entity_from_pod_row
from models.scope import resolve_cluster_id

logger = logging.getLogger(__name__)

PodMetricKey = tuple[str, str]


def parse_prom_instant_vector(mcp: McpPromQueryResponse) -> dict[PodMetricKey, float]:
    """Extract ``{(namespace, pod): value}`` from an instant ``vector`` query."""
    out: dict[PodMetricKey, float] = {}
    for row in mcp.get("results") or []:
        if not isinstance(row, dict):
            continue
        metric = row.get("metric")
        if not isinstance(metric, dict):
            continue
        pod = str(metric.get("pod") or "").strip()
        ns = str(metric.get("namespace") or "").strip()
        if not pod or not ns:
            continue
        value = row.get("value")
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            continue
        try:
            out[(ns, pod)] = float(value[1])
        except (TypeError, ValueError):
            logger.warning("Skipping non-numeric prom value for %s/%s: %r", ns, pod, value)
    return out


def build_pod_metrics_map(
    cpu_mcp: McpPromQueryResponse,
    memory_mcp: McpPromQueryResponse,
    *,
    namespace: str | None = None,
) -> dict[PodMetricKey, dict[str, float | int]]:
    """Merge CPU (cores) and memory (bytes) vectors keyed by ``(namespace, pod)``."""
    cpu = parse_prom_instant_vector(cpu_mcp)
    memory = parse_prom_instant_vector(memory_mcp)
    ns_filter = namespace.strip() if namespace and str(namespace).strip() else None

    merged: dict[PodMetricKey, dict[str, float | int]] = {}
    for key in set(cpu) | set(memory):
        if ns_filter is not None and key[0] != ns_filter:
            continue
        entry: dict[str, float | int] = {}
        if key in cpu:
            entry["cpu_cores"] = cpu[key]
        if key in memory:
            entry["memory_bytes"] = int(memory[key])
        if entry:
            merged[key] = entry
    return merged


def pods_with_metrics_to_batch(
    pods_mcp: McpListResponse,
    cpu_mcp: McpPromQueryResponse,
    memory_mcp: McpPromQueryResponse,
    namespace: str,
    *,
    cluster_id: str | None = None,
    tenant_id: str | None = None,
) -> GraphBatch:
    """Map K8s pods + Prom metrics to Pod entities with ``cpu_cores`` / ``memory_bytes``."""
    cid = resolve_cluster_id(pods_mcp, cpu_mcp, memory_mcp, cluster_id=cluster_id)
    ns = namespace.strip()
    metrics_map = build_pod_metrics_map(cpu_mcp, memory_mcp, namespace=ns)
    entities: list[GraphEntity] = []

    for row in pods_mcp.get("results") or []:
        if not isinstance(row, dict):
            logger.warning("Skipping pod row that is not a dict: %r", row)
            continue
        name = _pod_name_from_row(row)
        if name is None:
            logger.warning("Skipping pod row missing name: %r", row)
            continue
        pod_metrics = metrics_map.get((ns, name), {})
        entities.append(
            entity_from_pod_row(
                row,
                ns,
                cluster_id=cid,
                tenant_id=tenant_id,
                metrics=pod_metrics or None,
            )
        )

    return GraphBatch(entities=entities)


def metrics_map_from_prom(
    cpu_mcp: McpPromQueryResponse,
    memory_mcp: McpPromQueryResponse,
    *,
    namespace: str | None = None,
) -> dict[PodMetricKey, dict[str, Any]]:
    """Public alias for tests and diagnostics."""
    return build_pod_metrics_map(cpu_mcp, memory_mcp, namespace=namespace)
