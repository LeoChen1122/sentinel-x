#!/usr/bin/env python3
"""Multicluster acceptance demo: Node/Inspection/Query + mock sync (no live K8s by default)."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from models.scope import sync_thread_id  # noqa: E402
from query import format_query_result, run_query  # noqa: E402
from sync.multicluster import make_mock_cluster_sync, sync_clusters_resilient  # noqa: E402
from testing.multicluster_fixtures import (  # noqa: E402
    CLUSTER_DEV,
    CLUSTER_PROD,
    dual_cluster_full_batch,
)


def _stats_by_cluster(batch) -> dict[str, Counter[str]]:
    out: dict[str, Counter[str]] = {}
    for ent in batch.entities:
        cid = str(ent.properties.get("cluster_id", "unknown"))
        out.setdefault(cid, Counter())[ent.type.value] += 1
    return out


def _run_queries(payload: dict, cluster_id: str) -> None:
    ns, name = "default", "shared-pod"
    for op, params in (
        ("list_pods", {"cluster_id": cluster_id}),
        ("events_for_pod", {"cluster_id": cluster_id, "namespace": ns, "name": name}),
        ("inspections_for_pod", {"cluster_id": cluster_id, "namespace": ns, "name": name}),
    ):
        result = run_query(payload, op, **params)
        print(f"  [{cluster_id}] {op}: count={result.get('count', 'n/a')}")


def main() -> int:
    batch = dual_cluster_full_batch()
    payload = batch.to_dict(wire_only=True)

    print("=== entity counts by cluster ===")
    for cid, counts in sorted(_stats_by_cluster(batch).items()):
        print(f"  {cid}: {dict(counts)}")

    entity_ids = [e.id for e in batch.entities]
    if len(entity_ids) != len(set(entity_ids)):
        print("FAIL: duplicate entity ids in merged batch", file=sys.stderr)
        return 1
    print(f"=== unique entity ids: {len(entity_ids)} ===")

    print("=== query per cluster ===")
    for cid in (CLUSTER_DEV, CLUSTER_PROD):
        _run_queries(payload, cid)

    print("=== mock sync (per-cluster thread_id) ===")
    sync_one = make_mock_cluster_sync(namespace="default")
    threads: list[str | None] = []

    def _capture_stream(*_a, **kwargs):
        threads.append(kwargs.get("thread_id"))
        return iter([])

    with mock.patch("sync.pipeline.stream_sentinel_run", side_effect=_capture_stream):
        mc = sync_clusters_resilient([CLUSTER_DEV, CLUSTER_PROD], sync_one)
    for cid in (CLUSTER_DEV, CLUSTER_PROD):
        r = mc.by_cluster[cid]
        print(
            f"  {cid}: thread={sync_thread_id(cid)} "
            f"entities_pushed={r.entities_pushed} chunks={r.chunks_sent}"
        )
    if threads != [sync_thread_id(CLUSTER_DEV), sync_thread_id(CLUSTER_PROD)]:
        print("FAIL: unexpected thread_ids", threads, file=sys.stderr)
        return 1

    # spot-check one formatted query
    sample = run_query(
        payload,
        "inspections_for_pod",
        cluster_id=CLUSTER_DEV,
        namespace="default",
        name="shared-pod",
    )
    print("=== sample inspections_for_pod (dev) ===")
    print(format_query_result(sample), end="")

    print("\nOK: multicluster validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
