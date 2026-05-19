"""Multicluster sync helpers (phase 4-2): tick each cluster with isolated state/thread."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sync.pipeline import SyncPushResult
from sync.scheduler import PeriodicSyncStats, run_periodic_sync
from sync.state import SyncStateRegistry


@dataclass
class MulticlusterSyncResult:
    """Per-cluster results from :func:`sync_clusters_resilient`."""

    by_cluster: dict[str, SyncPushResult]

    @property
    def total_entities_pushed(self) -> int:
        return sum(r.entities_pushed for r in self.by_cluster.values())

    @property
    def failures(self) -> list[str]:
        return [cid for cid, r in self.by_cluster.items() if r.chunks_sent == 0 and r.entities_pushed == 0]


def sync_clusters_resilient(
    cluster_ids: list[str],
    sync_one: Callable[[str], SyncPushResult],
    *,
    continue_on_error: bool = True,
) -> MulticlusterSyncResult:
    """Run ``sync_one(cluster_id)`` for each cluster; errors optional per cluster."""
    results: dict[str, SyncPushResult] = {}
    for cid in cluster_ids:
        try:
            results[cid] = sync_one(cid)
        except Exception:
            if not continue_on_error:
                raise
            results[cid] = SyncPushResult(
                chunks_sent=0,
                entities_pushed=0,
                edges_pushed=0,
                skipped_unchanged=0,
            )
    return MulticlusterSyncResult(by_cluster=results)


def make_mock_cluster_sync(
    namespace: str = "default",
    *,
    tenant_id: str | None = None,
    state_registry: SyncStateRegistry | None = None,
):
    """Factory: sync one cluster from :mod:`testing.multicluster_fixtures` (no LangGraph required in caller)."""
    from sync.pipeline import sync_pods_and_events_resilient
    from testing.multicluster_fixtures import events_mcp, pods_mcp

    registry = state_registry or SyncStateRegistry()

    def _sync(cluster_id: str) -> SyncPushResult:
        return sync_pods_and_events_resilient(
            pods_mcp(cluster_id, namespace=namespace),
            events_mcp(cluster_id, namespace=namespace),
            namespace,
            cluster_id=cluster_id,
            tenant_id=tenant_id,
            state_registry=registry,
            incremental=False,
            min_interval_sec=0,
        )

    return _sync


def run_periodic_multicluster_sync(
    cluster_ids: list[str],
    sync_one: Callable[[str], SyncPushResult],
    interval_sec: float,
    **scheduler_kwargs,
) -> PeriodicSyncStats:
    """Periodic loop: one tick syncs every cluster in ``cluster_ids``."""

    def _tick() -> SyncPushResult:
        mc = sync_clusters_resilient(cluster_ids, sync_one, continue_on_error=True)
        total_entities = mc.total_entities_pushed
        total_chunks = sum(r.chunks_sent for r in mc.by_cluster.values())
        return SyncPushResult(
            chunks_sent=total_chunks,
            entities_pushed=total_entities,
            edges_pushed=sum(r.edges_pushed for r in mc.by_cluster.values()),
            skipped_unchanged=sum(r.skipped_unchanged for r in mc.by_cluster.values()),
        )

    return run_periodic_sync(_tick, interval_sec, **scheduler_kwargs)
