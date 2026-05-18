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

from models.entities import EntityType, RelationType  # noqa: E402
from models.ids import inspection_id, pod_id  # noqa: E402


class TestInspectionRowLinks(unittest.TestCase):
    def test_linked_pods_entity_id_from_row(self) -> None:
        from adapter.inspections import inspections_to_batch

        pid = pod_id("default", "p1")
        rows = [
            {
                "timestamp": "2024-06-01T00:00:00Z",
                "node": "worker-01",
                "status": "ok",
                "summary": "ok",
                "linked_pods": [pid],
            }
        ]
        batch = inspections_to_batch(rows)
        self.assertEqual(len(batch.edges), 1)
        self.assertEqual(batch.edges[0].relation, RelationType.INSPECTS_POD)
        self.assertEqual(batch.edges[0].target_id, pid)

    def test_rejects_bare_pod_name_in_linked_pods(self) -> None:
        from adapter.inspections import inspections_to_batch

        rows = [
            {
                "timestamp": "2024-06-01T00:00:00Z",
                "node": "worker-01",
                "status": "ok",
                "summary": "ok",
                "linked_pods": ["demo-pod"],
            }
        ]
        batch = inspections_to_batch(rows)
        self.assertEqual(len(batch.edges), 0)


class TestMergeGraphBatches(unittest.TestCase):
    def test_later_batch_overwrites_entity_properties(self) -> None:
        from adapter.k8s import pods_events_to_batch
        from models.entities import entity_from_pod_row
        from models.entities import GraphBatch
        from utils.graph_merge import merge_graph_batches

        pods_a = {
            "results": [{"name": "p1", "status": "Running"}],
        }
        batch_a = pods_events_to_batch(pods_a, {"results": []}, "default")
        pid = pod_id("default", "p1")
        batch_b = GraphBatch(
            entities=[
                entity_from_pod_row({"name": "p1", "status": "Pending"}, "default")
            ]
        )
        merged = merge_graph_batches(batch_a, batch_b)
        ent = next(e for e in merged.entities if e.id == pid)
        self.assertEqual(ent.properties["status"], "Pending")

    def test_drops_orphan_edges(self) -> None:
        from models.entities import GraphBatch, edge_inspection_to_pod, entity_from_inspection
        from utils.graph_merge import merge_graph_batches

        insp = entity_from_inspection(
            "2024-06-01T00:00:00Z", "worker-01", "ok", "summary"
        )
        orphan = edge_inspection_to_pod(insp.id, "pod:missing/ns")
        batch = GraphBatch(entities=[insp], edges=[orphan])
        merged = merge_graph_batches(batch)
        self.assertEqual(len(merged.edges), 0)

    def test_full_merge_has_three_entity_types(self) -> None:
        from adapter.inspections import inspection_mcp_to_batch
        from adapter.k8s import pods_events_to_batch
        from utils.graph_merge import merge_graph_batches

        pods = {"results": [{"name": "p1", "status": "Running"}]}
        events = {
            "results": [
                {
                    "type": "Warning",
                    "reason": "Failed",
                    "message": "x",
                    "object_kind": "Pod",
                    "object_name": "p1",
                    "last_timestamp": "2024-06-01T00:00:00Z",
                }
            ]
        }
        pe = pods_events_to_batch(pods, events, "default")
        pid = pod_id("default", "p1")
        insp = inspection_mcp_to_batch(
            {
                "results": [
                    {
                        "timestamp": "2024-06-01T00:00:00Z",
                        "node": "worker-01",
                        "status": "ok",
                        "summary": "check",
                        "linked_pods": [pid],
                    }
                ]
            }
        )
        merged = merge_graph_batches(pe, insp)
        types = {e.type for e in merged.entities}
        self.assertIn(EntityType.POD, types)
        self.assertIn(EntityType.EVENT, types)
        self.assertIn(EntityType.INSPECTION, types)


class TestStep8QueryOps(unittest.TestCase):
    def setUp(self) -> None:
        from adapter.inspections import inspections_to_batch
        from adapter.k8s import pods_events_to_batch
        from utils.graph_merge import merge_graph_batches

        pods = {"results": [{"name": "p1", "status": "Running"}]}
        events = {
            "results": [
                {
                    "type": "Warning",
                    "reason": "Failed",
                    "message": "x",
                    "namespace": "sandbox",
                    "object_kind": "Pod",
                    "object_name": "p1",
                    "last_timestamp": "2024-06-01T00:00:00Z",
                }
            ]
        }
        pe = pods_events_to_batch(pods, events, "sandbox")
        pid = pod_id("sandbox", "p1")
        insp = inspections_to_batch(
            [
                {
                    "timestamp": "2024-06-01T12:00:00Z",
                    "node": "worker-01",
                    "status": "ok",
                    "summary": "routine",
                    "linked_pods": [pid],
                }
            ]
        )
        self.payload = merge_graph_batches(pe, insp).to_dict(wire_only=True)

    def test_list_events(self) -> None:
        from query import run_query

        out = run_query(self.payload, "list_events", namespace="sandbox")
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["events"][0]["reason"], "Failed")

    def test_inspections_for_pod(self) -> None:
        from query import run_query

        out = run_query(
            self.payload, "inspections_for_pod", namespace="sandbox", name="p1"
        )
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["inspections"][0]["node"], "worker-01")


class TestSyncInspectionsMock(unittest.TestCase):
    def test_sync_inspections_passes_thread_id(self) -> None:
        from sync.pipeline import sync_inspections_resilient

        mcp = {
            "results": [
                {
                    "timestamp": "2024-06-01T00:00:00Z",
                    "node": "worker-01",
                    "status": "ok",
                    "summary": "x",
                }
            ]
        }
        with mock.patch("sync.pipeline.push_graph_batch_resilient") as push:
            push.return_value = mock.Mock(
                chunks_sent=1,
                entities_pushed=1,
                edges_pushed=0,
                skipped_unchanged=0,
            )
            sync_inspections_resilient(mcp, thread_id="tid-8")
        push.assert_called_once()
        self.assertEqual(push.call_args.kwargs.get("thread_id"), "tid-8")

    def test_sync_full_includes_inspection_entity(self) -> None:
        from sync.pipeline import sync_pods_events_inspections_resilient

        pods = {"results": [{"name": "p1", "status": "Running"}]}
        events = {"results": []}
        insp = {
            "results": [
                {
                    "timestamp": "2024-06-01T00:00:00Z",
                    "node": "worker-01",
                    "status": "ok",
                    "summary": "x",
                    "linked_pods": [pod_id("default", "p1")],
                }
            ]
        }
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
        self.assertEqual(len(captured), 1)
        types = {e.type for e in captured[0].entities}
        self.assertIn(EntityType.INSPECTION, types)


class TestStep8Live(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("LANGGRAPH_RUN_LIVE", "").strip().lower() in ("1", "true", "yes"),
        "Set LANGGRAPH_RUN_LIVE=1 and start langgraph dev",
    )
    def test_full_pipeline_live(self) -> None:
        from clients.langgraph_client import get_langgraph_client, query_sentinel
        from sync import sync_pods_events_inspections_resilient

        thread_id = "step8-live-test"
        client = get_langgraph_client()
        pods = {"results": [{"name": "live-p1", "status": "Running"}]}
        events = {
            "results": [
                {
                    "type": "Warning",
                    "reason": "FailedScheduling",
                    "message": "no nodes",
                    "object_kind": "Pod",
                    "object_name": "live-p1",
                    "last_timestamp": "2024-06-01T00:00:00Z",
                }
            ]
        }
        pid = pod_id("default", "live-p1")
        insp = {
            "results": [
                {
                    "timestamp": "2024-06-01T00:00:00Z",
                    "node": "worker-01",
                    "status": "ok",
                    "summary": "check",
                    "linked_pods": [pid],
                }
            ]
        }
        sync_pods_events_inspections_resilient(
            pods, events, "default", insp, client=client, thread_id=thread_id
        )
        ev = query_sentinel(
            "events_for_pod",
            thread_id=thread_id,
            client=client,
            namespace="default",
            name="live-p1",
        )
        ins = query_sentinel(
            "inspections_for_pod",
            thread_id=thread_id,
            client=client,
            namespace="default",
            name="live-p1",
        )
        self.assertGreaterEqual(ev.get("count", 0), 1)
        self.assertGreaterEqual(ins.get("count", 0), 1)


if __name__ == "__main__":
    unittest.main()
