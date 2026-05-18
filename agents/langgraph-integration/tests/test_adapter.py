"""Step 4: adapter MCP → GraphBatch mapping (no LangGraph API)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from adapter.events import events_to_entities
from adapter.inspections import inspections_to_batch
from adapter.k8s import pods_events_to_batch
from adapter.pods import pods_to_entities
from models.entities import EntityType, RelationKind, RelationType


class TestPodsAdapter(unittest.TestCase):
    def test_pods_to_entities(self) -> None:
        mcp = {
            "query": "get_pods",
            "results": [{"name": "payment-1", "status": "Running"}],
        }
        ents = pods_to_entities(mcp, "sandbox")
        self.assertEqual(len(ents), 1)
        self.assertEqual(ents[0].id, "pod:sandbox/payment-1")

    def test_pods_skips_missing_name(self) -> None:
        mcp = {"query": "get_pods", "results": [{"status": "Running"}]}
        self.assertEqual(pods_to_entities(mcp, "default"), [])

    def test_pods_skips_bad_row_keeps_valid(self) -> None:
        mcp = {
            "query": "get_pods",
            "results": [
                {"status": "Running"},
                {"name": "ok-1", "status": "Running"},
                "not-a-dict",
            ],
        }
        ents = pods_to_entities(mcp, "sandbox")
        self.assertEqual(len(ents), 1)
        self.assertEqual(ents[0].id, "pod:sandbox/ok-1")

    def test_pods_empty_results(self) -> None:
        self.assertEqual(pods_to_entities({"results": []}, "ns"), [])


class TestPodsEventsBatch(unittest.TestCase):
    def test_pods_events_to_batch(self) -> None:
        pods_mcp = {
            "query": "get_pods",
            "results": [{"name": "payment-1", "status": "Running"}],
        }
        events_mcp = {
            "query": "get_events",
            "results": [
                {
                    "reason": "Failed",
                    "object_kind": "Pod",
                    "object_name": "payment-1",
                    "namespace": "sandbox",
                }
            ],
        }
        batch = pods_events_to_batch(pods_mcp, events_mcp, "sandbox")
        self.assertEqual(len(batch.entities), 2)
        self.assertEqual(len(batch.edges), 1)
        self.assertEqual(batch.edges[0].relation, RelationType.HAS_EVENT)
        self.assertEqual(batch.edges[0].kind, RelationKind.EMITS)

    def test_pod_node_map(self) -> None:
        pods_mcp = {
            "query": "get_pods",
            "results": [{"name": "payment-1", "status": "Running"}],
        }
        events_mcp = {"query": "get_events", "results": []}
        batch = pods_events_to_batch(
            pods_mcp,
            events_mcp,
            "sandbox",
            link_pod_events=False,
            pod_node_map={"payment-1": "worker-01"},
        )
        node_ids = [e.id for e in batch.entities if e.type is EntityType.NODE]
        self.assertIn("node:worker-01", node_ids)
        sched = [e for e in batch.edges if e.relation is RelationType.SCHEDULED_ON]
        self.assertEqual(len(sched), 1)
        self.assertEqual(sched[0].source_id, "pod:sandbox/payment-1")

    def test_empty_mcp_results(self) -> None:
        batch = pods_events_to_batch(
            {"results": []},
            {"results": []},
            "sandbox",
        )
        self.assertEqual(batch.entities, [])
        self.assertEqual(batch.edges, [])


class TestEventsAdapter(unittest.TestCase):
    def test_events_empty(self) -> None:
        self.assertEqual(events_to_entities({"results": []}), [])


class TestInspectionsAdapter(unittest.TestCase):
    def test_inspections_to_batch_with_pod_link(self) -> None:
        rows = [
            {
                "timestamp": "2024-06-01T00:00:00Z",
                "node": "worker-01",
                "status": "ok",
                "summary": "healthy",
            }
        ]
        batch = inspections_to_batch(rows, link_pods=["pod:default/p1"])
        self.assertEqual(len(batch.entities), 1)
        self.assertEqual(len(batch.edges), 1)
        self.assertEqual(batch.edges[0].relation, RelationType.INSPECTS_POD)

    def test_inspections_linked_pods_in_row(self) -> None:
        batch = inspections_to_batch(
            [
                {
                    "timestamp": "2024-06-01T00:00:00Z",
                    "node": "worker-01",
                    "status": "ok",
                    "summary": "healthy",
                    "linked_pods": ["pod:default/p1"],
                }
            ]
        )
        self.assertEqual(len(batch.edges), 1)


if __name__ == "__main__":
    unittest.main()
