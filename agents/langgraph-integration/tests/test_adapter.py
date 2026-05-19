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
from models.ids import pod_id
from testing.multicluster_fixtures import CLUSTER_LOCAL

CL = CLUSTER_LOCAL


class TestPodsAdapter(unittest.TestCase):
    def test_pods_to_entities(self) -> None:
        mcp = {
            "query": "get_pods",
            "cluster_id": CL,
            "results": [{"name": "payment-1", "status": "Running"}],
        }
        ents = pods_to_entities(mcp, "sandbox")
        self.assertEqual(len(ents), 1)
        self.assertEqual(ents[0].id, pod_id(CL, "sandbox", "payment-1"))

    def test_pods_skips_missing_name(self) -> None:
        mcp = {"query": "get_pods", "cluster_id": CL, "results": [{"status": "Running"}]}
        self.assertEqual(pods_to_entities(mcp, "default"), [])

    def test_pods_empty_results(self) -> None:
        self.assertEqual(
            pods_to_entities({"query": "get_pods", "cluster_id": CL, "results": []}, "ns"),
            [],
        )


class TestPodsEventsBatch(unittest.TestCase):
    def test_pods_events_to_batch(self) -> None:
        pods_mcp = {
            "query": "get_pods",
            "cluster_id": CL,
            "results": [{"name": "payment-1", "status": "Running"}],
        }
        events_mcp = {
            "query": "get_events",
            "cluster_id": CL,
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

    def test_pod_node_map(self) -> None:
        pods_mcp = {
            "query": "get_pods",
            "cluster_id": CL,
            "results": [{"name": "payment-1", "status": "Running"}],
        }
        events_mcp = {"query": "get_events", "cluster_id": CL, "results": []}
        batch = pods_events_to_batch(
            pods_mcp,
            events_mcp,
            "sandbox",
            link_pod_events=False,
            pod_node_map={"payment-1": "worker-01"},
        )
        self.assertIn(f"node:{CL}/worker-01", [e.id for e in batch.entities])
        self.assertEqual(
            batch.edges[0].source_id, pod_id(CL, "sandbox", "payment-1")
        )

    def test_empty_mcp_results(self) -> None:
        batch = pods_events_to_batch(
            {"query": "get_pods", "cluster_id": CL, "results": []},
            {"query": "get_events", "cluster_id": CL, "results": []},
            "sandbox",
        )
        self.assertEqual(batch.entities, [])


class TestEventsAdapter(unittest.TestCase):
    def test_events_empty(self) -> None:
        self.assertEqual(
            events_to_entities({"query": "get_events", "cluster_id": CL, "results": []}),
            [],
        )


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
        pid = pod_id(CL, "default", "p1")
        batch = inspections_to_batch(rows, cluster_id=CL, link_pods=[pid])
        self.assertEqual(len(batch.edges), 1)

    def test_inspections_linked_pods_in_row(self) -> None:
        pid = pod_id(CL, "default", "p1")
        batch = inspections_to_batch(
            [
                {
                    "timestamp": "2024-06-01T00:00:00Z",
                    "node": "worker-01",
                    "status": "ok",
                    "summary": "healthy",
                    "linked_pods": [pid],
                }
            ],
            cluster_id=CL,
        )
        self.assertEqual(len(batch.edges), 1)


if __name__ == "__main__":
    unittest.main()
