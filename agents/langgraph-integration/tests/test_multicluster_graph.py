"""Multicluster acceptance: Node/Inspection IDs, edges, adapter, payload isolation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from adapter.inspections import inspection_mcp_to_batch, inspections_to_batch
from adapter.k8s import pods_events_to_batch
from models.entities import EntityType, RelationType
from models.ids import inspection_id, node_id, pod_id
from models.scope import langgraph_thread_id
from testing.multicluster_fixtures import (
    CLUSTER_DEV,
    CLUSTER_PROD,
    cluster_full_batch,
    dual_cluster_full_batch,
    events_mcp,
    inspection_mcp,
    pods_events_batch_with_node,
    pods_mcp,
)
from utils.graph_merge import merge_graph_batches


class TestNodeAndInspectionIds(unittest.TestCase):
    def setUp(self) -> None:
        self.batch = dual_cluster_full_batch()

    def test_node_ids_differ_across_clusters(self) -> None:
        nodes = [e for e in self.batch.entities if e.type is EntityType.NODE]
        self.assertEqual(len(nodes), 2)
        ids = {n.id for n in nodes}
        self.assertEqual(
            ids,
            {
                node_id(CLUSTER_DEV, "worker-01"),
                node_id(CLUSTER_PROD, "worker-01"),
            },
        )
        for n in nodes:
            self.assertIn(n.properties.get("cluster_id"), (CLUSTER_DEV, CLUSTER_PROD))

    def test_inspection_ids_and_linked_pods(self) -> None:
        inspections = [
            e for e in self.batch.entities if e.type is EntityType.INSPECTION
        ]
        self.assertEqual(len(inspections), 2)
        dev_pid = pod_id(CLUSTER_DEV, "default", "shared-pod")
        prod_pid = pod_id(CLUSTER_PROD, "default", "shared-pod")
        insp_edges = [
            e
            for e in self.batch.edges
            if e.relation is RelationType.INSPECTS_POD
        ]
        self.assertEqual(len(insp_edges), 2)
        targets = {e.target_id for e in insp_edges}
        self.assertEqual(targets, {dev_pid, prod_pid})
        dev_insp_id = inspection_id(CLUSTER_DEV, "2024-06-01T12:00:00Z", "worker-01")
        prod_insp_id = inspection_id(CLUSTER_PROD, "2024-06-01T12:00:00Z", "worker-01")
        self.assertEqual({e.source_id for e in insp_edges}, {dev_insp_id, prod_insp_id})

    def test_merge_no_orphan_inspection_edges(self) -> None:
        dev = cluster_full_batch(CLUSTER_DEV)
        prod = cluster_full_batch(CLUSTER_PROD)
        merged = merge_graph_batches(dev, prod)
        relations = {e.relation for e in merged.edges}
        self.assertIn(RelationType.HAS_EVENT, relations)
        self.assertIn(RelationType.SCHEDULED_ON, relations)
        self.assertIn(RelationType.INSPECTS_POD, relations)
        # per cluster: pod-event, pod-node, inspection-pod = 3 edges * 2
        self.assertEqual(len(merged.edges), 6)

    def test_wrong_cluster_linked_pod_dropped_as_orphan(self) -> None:
        """linked_pods pointing at another cluster's pod id must not create a valid edge."""
        dev_pid = pod_id(CLUSTER_DEV, "default", "shared-pod")
        prod_pid = pod_id(CLUSTER_PROD, "default", "shared-pod")
        rows = [
            {
                "timestamp": "2024-06-01T12:00:00Z",
                "node": "worker-01",
                "status": "ok",
                "summary": "bad link",
                "linked_pods": [prod_pid],
            }
        ]
        dev_only = pods_events_batch_with_node(CLUSTER_DEV)
        insp = inspections_to_batch(rows, cluster_id=CLUSTER_DEV)
        with self.assertLogs("utils.graph_merge", level="WARNING"):
            merged = merge_graph_batches(dev_only, insp)
        insp_edges = [
            e for e in merged.edges if e.relation is RelationType.INSPECTS_POD
        ]
        self.assertEqual(insp_edges, [])
        self.assertIn(dev_pid, {e.id for e in merged.entities})


class TestAdapterMulticluster(unittest.TestCase):
    def test_per_cluster_entity_and_edge_shape(self) -> None:
        ns = "default"
        for cid in (CLUSTER_DEV, CLUSTER_PROD):
            pe = pods_events_to_batch(
                pods_mcp(cid, namespace=ns),
                events_mcp(cid, namespace=ns),
                ns,
                pod_node_map={"shared-pod": "worker-01"},
            )
            insp = inspection_mcp_to_batch(inspection_mcp(cid, namespace=ns))
            batch = merge_graph_batches(pe, insp)
            types = {e.type for e in batch.entities}
            self.assertEqual(
                types,
                {EntityType.POD, EntityType.EVENT, EntityType.NODE, EntityType.INSPECTION},
            )
            relations = {e.relation for e in batch.edges}
            self.assertIn(RelationType.HAS_EVENT, relations)
            self.assertIn(RelationType.SCHEDULED_ON, relations)
            self.assertIn(RelationType.INSPECTS_POD, relations)
            for ent in batch.entities:
                self.assertEqual(ent.properties.get("cluster_id"), cid)


class TestPayloadIsolation(unittest.TestCase):
    def test_per_cluster_payload_no_id_collision(self) -> None:
        dev = cluster_full_batch(CLUSTER_DEV).to_dict(wire_only=True)
        prod = cluster_full_batch(CLUSTER_PROD).to_dict(wire_only=True)
        merged_entities = (dev.get("entities") or []) + (prod.get("entities") or [])
        ids = [e["id"] for e in merged_entities if isinstance(e, dict) and e.get("id")]
        self.assertEqual(len(ids), len(set(ids)))

    def test_merged_full_batch_unique_ids(self) -> None:
        payload = dual_cluster_full_batch().to_dict(wire_only=True)
        ids = [e["id"] for e in payload.get("entities") or []]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 8)


class TestFullPipelineSyncThreads(unittest.TestCase):
    def test_sync_full_pipeline_distinct_threads(self) -> None:
        from sync.pipeline import sync_pods_events_inspections_resilient
        from testing.multicluster_fixtures import inspection_mcp

        captured: list[str | None] = []

        def _stream(*_a, **kwargs):
            captured.append(kwargs.get("thread_id"))
            return iter([])

        for cid in (CLUSTER_DEV, CLUSTER_PROD):
            with mock.patch("sync.pipeline.stream_sentinel_run", side_effect=_stream):
                sync_pods_events_inspections_resilient(
                    pods_mcp(cid),
                    events_mcp(cid),
                    "default",
                    inspection_mcp(cid),
                    incremental=False,
                    min_interval_sec=0,
                )
        self.assertEqual(
            captured,
            [langgraph_thread_id(CLUSTER_DEV), langgraph_thread_id(CLUSTER_PROD)],
        )


if __name__ == "__main__":
    unittest.main()
