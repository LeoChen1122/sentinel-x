"""Phase 4-2: multicluster sync partition, thread_id, and scheduler tick."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from models.scope import sync_thread_id
from testing.multicluster_fixtures import CLUSTER_DEV, CLUSTER_LOCAL, CLUSTER_PROD
from sync.multicluster import make_mock_cluster_sync, sync_clusters_resilient
from sync.pipeline import sync_pods_and_events_resilient
from sync.state import SyncState, SyncStateRegistry, partition_state_path


class TestSyncThreadId(unittest.TestCase):
    def test_default_tenant(self) -> None:
        self.assertEqual(sync_thread_id("dev-cluster"), "default:dev-cluster")

    def test_explicit_tenant(self) -> None:
        self.assertEqual(
            sync_thread_id("prod-cluster", "team-alpha"),
            "team-alpha:prod-cluster",
        )


class TestSyncStatePartition(unittest.TestCase):
    def test_partition_paths_differ_by_cluster(self) -> None:
        base = Path("/data/sync-state.json")
        p_dev = partition_state_path(base, CLUSTER_DEV)
        p_prod = partition_state_path(base, CLUSTER_PROD)
        self.assertIsNotNone(p_dev)
        self.assertIsNotNone(p_prod)
        self.assertNotEqual(p_dev, p_prod)
        self.assertIn("dev-cluster", str(p_dev))
        self.assertIn("prod-cluster", str(p_prod))

    def test_registry_isolates_incremental_state(self) -> None:
        registry = SyncStateRegistry()
        state_dev = registry.get(CLUSTER_DEV)
        state_prod = registry.get(CLUSTER_PROD)
        self.assertIsNot(state_dev, state_prod)

        from models.entities import GraphBatch, entity_from_pod_row

        batch_dev = GraphBatch(
            entities=[
                entity_from_pod_row(
                    {"name": "shared-pod", "status": "Running"},
                    "default",
                    cluster_id=CLUSTER_DEV,
                )
            ]
        )
        batch_prod = GraphBatch(
            entities=[
                entity_from_pod_row(
                    {"name": "shared-pod", "status": "Running"},
                    "default",
                    cluster_id=CLUSTER_PROD,
                )
            ]
        )
        state_dev.update_from_batch(batch_dev)
        state_prod.update_from_batch(batch_prod)
        self.assertIsNotNone(state_dev.fingerprint_for(batch_dev.entities[0].id))
        self.assertIsNotNone(state_prod.fingerprint_for(batch_prod.entities[0].id))

    def test_partitioned_file_on_disk(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "sync.json"
            state = SyncState.for_scope(CLUSTER_LOCAL, base_path=base)
            from models.entities import GraphBatch, entity_from_pod_row

            ent = entity_from_pod_row(
                {"name": "p1", "status": "Running"},
                "default",
                cluster_id=CLUSTER_LOCAL,
            )
            state.update_from_batch(GraphBatch(entities=[ent]))
            part_path = partition_state_path(base, CLUSTER_LOCAL)
            self.assertIsNotNone(part_path)
            self.assertTrue(part_path.is_file())


class TestSyncResilientScope(unittest.TestCase):
    def test_passes_default_thread_id(self) -> None:
        from testing.multicluster_fixtures import events_mcp, pods_mcp

        pods = pods_mcp(CLUSTER_DEV)
        events = events_mcp(CLUSTER_DEV)
        expected_thread = sync_thread_id(CLUSTER_DEV)
        with mock.patch("sync.pipeline.stream_sentinel_run", return_value=iter([])) as m:
            sync_pods_and_events_resilient(
                pods,
                events,
                "default",
                incremental=False,
                min_interval_sec=0,
            )
        self.assertEqual(m.call_args.kwargs.get("thread_id"), expected_thread)

    def test_tenant_thread_id(self) -> None:
        from testing.multicluster_fixtures import events_mcp, pods_mcp

        pods = pods_mcp(CLUSTER_DEV)
        events = events_mcp(CLUSTER_DEV)
        with mock.patch("sync.pipeline.stream_sentinel_run", return_value=iter([])) as m:
            sync_pods_and_events_resilient(
                pods,
                events,
                "default",
                tenant_id="team-alpha",
                incremental=False,
                min_interval_sec=0,
            )
        self.assertEqual(
            m.call_args.kwargs.get("thread_id"),
            sync_thread_id(CLUSTER_DEV, "team-alpha"),
        )


class TestMulticlusterSyncTick(unittest.TestCase):
    def test_sync_both_clusters(self) -> None:
        sync_one = make_mock_cluster_sync()
        captured_threads: list[str | None] = []

        def _track_stream(*_a, **kwargs):
            captured_threads.append(kwargs.get("thread_id"))
            return iter([])

        with mock.patch("sync.pipeline.stream_sentinel_run", side_effect=_track_stream):
            result = sync_clusters_resilient(
                [CLUSTER_DEV, CLUSTER_PROD],
                sync_one,
            )
        self.assertEqual(len(result.by_cluster), 2)
        self.assertEqual(result.by_cluster[CLUSTER_DEV].entities_pushed, 2)
        self.assertEqual(result.by_cluster[CLUSTER_PROD].entities_pushed, 2)
        self.assertIn(sync_thread_id(CLUSTER_DEV), captured_threads)
        self.assertIn(sync_thread_id(CLUSTER_PROD), captured_threads)


if __name__ == "__main__":
    unittest.main()
