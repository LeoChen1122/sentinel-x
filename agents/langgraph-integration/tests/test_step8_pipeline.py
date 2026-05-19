"""Step 8: Events + Inspections pipeline (merge, sync, query)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from models.entities import EntityType  # noqa: E402
from models.ids import pod_id  # noqa: E402
from testing.multicluster_fixtures import (  # noqa: E402
    CLUSTER_DEV,
    CLUSTER_LOCAL,
    CLUSTER_PROD,
    events_mcp,
    inspection_mcp,
    pods_events_batch,
    pods_mcp,
)


class TestInspectionRowLinks(unittest.TestCase):
    def test_linked_pods_entity_id_from_row(self) -> None:
        from adapter.inspections import inspections_to_batch

        cid = CLUSTER_LOCAL
        pid = pod_id(cid, "default", "p1")
        rows = [
            {
                "timestamp": "2024-06-01T00:00:00Z",
                "node": "worker-01",
                "status": "ok",
                "summary": "ok",
                "linked_pods": [pid],
            }
        ]
        batch = inspections_to_batch(rows, cluster_id=cid)
        self.assertEqual(len(batch.edges), 1)
        self.assertEqual(batch.edges[0].target_id, pid)


class TestMergeGraphBatches(unittest.TestCase):
    def test_full_merge_has_three_entity_types(self) -> None:
        from utils.graph_merge import merge_graph_batches

        batch = merge_graph_batches(
            pods_events_batch(CLUSTER_DEV),
            pods_events_batch(CLUSTER_PROD),
        )
        types = {e.type for e in batch.entities}
        self.assertIn(EntityType.POD, types)
        self.assertEqual(len([e for e in batch.entities if e.type is EntityType.POD]), 2)


class TestStep8QueryOps(unittest.TestCase):
    def setUp(self) -> None:
        from utils.graph_merge import merge_graph_batches

        pe = pods_events_batch(CLUSTER_DEV, "sandbox", pod_name="p1")
        self.payload = merge_graph_batches(pe).to_dict(wire_only=True)
        self.cid = CLUSTER_DEV

    def test_list_events(self) -> None:
        from query import run_query

        out = run_query(
            self.payload, "list_events", cluster_id=self.cid, namespace="sandbox"
        )
        self.assertEqual(out["count"], 1)

    def test_inspections_for_pod(self) -> None:
        from query import run_query

        out = run_query(
            self.payload,
            "inspections_for_pod",
            cluster_id=self.cid,
            namespace="sandbox",
            name="p1",
        )
        self.assertEqual(out["count"], 0)


class TestSyncInspectionsMock(unittest.TestCase):
    def test_sync_full_includes_inspection_entity(self) -> None:
        from sync.pipeline import sync_pods_events_inspections_resilient

        pods = pods_mcp(CLUSTER_LOCAL)
        events = events_mcp(CLUSTER_LOCAL)
        insp = inspection_mcp(CLUSTER_LOCAL)
        captured: list = []

        def _capture(batch, **kwargs):
            captured.append(batch)
            return mock.Mock(
                chunks_sent=1,
                entities_pushed=len(batch.entities),
                edges_pushed=len(batch.edges),
                skipped_unchanged=0,
            )

        with mock.patch("sync.pipeline.push_graph_batch_resilient", side_effect=_capture):
            sync_pods_events_inspections_resilient(
                pods, events, "default", insp, thread_id="tid-full"
            )
        types = {e.type for e in captured[0].entities}
        self.assertIn(EntityType.INSPECTION, types)


if __name__ == "__main__":
    unittest.main()
