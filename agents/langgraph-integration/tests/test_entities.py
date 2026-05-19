"""Step 2: graph entity models, IDs, and MCP row mapping (no LangGraph API)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from models.entities import (
    EntityType,
    GraphBatch,
    RelationKind,
    RelationType,
    edge_inspection_to_pod,
    edge_pod_to_event,
    edge_pod_to_node,
    entity_from_event_row,
    entity_from_inspection,
    entity_from_node,
    entity_from_pod_row,
    relation_kind_from_wire,
    wire_relation,
)
from models.ids import event_id, inspection_id, node_id, pod_id

CL = "local"
CL_SANDBOX = "sandbox"


class TestWireRelationMapping(unittest.TestCase):
    def test_emits_to_has_event(self) -> None:
        self.assertEqual(wire_relation(RelationKind.EMITS), RelationType.HAS_EVENT)
        kind, target = relation_kind_from_wire(RelationType.HAS_EVENT)
        self.assertEqual(kind, RelationKind.EMITS)
        self.assertIsNone(target)

    def test_inspects_pod(self) -> None:
        self.assertEqual(
            wire_relation(RelationKind.INSPECTS, target_type=EntityType.POD),
            RelationType.INSPECTS_POD,
        )
        kind, target = relation_kind_from_wire(RelationType.INSPECTS_POD)
        self.assertEqual(kind, RelationKind.INSPECTS)
        self.assertEqual(target, EntityType.POD)

    def test_inspects_requires_target(self) -> None:
        with self.assertRaises(ValueError):
            wire_relation(RelationKind.INSPECTS)


class TestStableIds(unittest.TestCase):
    def test_pod_id(self) -> None:
        self.assertEqual(
            pod_id(CL, "default", "nginx-1"), f"pod:{CL}/default/nginx-1"
        )

    def test_node_id(self) -> None:
        self.assertEqual(node_id(CL, "worker-01"), f"node:{CL}/worker-01")

    def test_inspection_id(self) -> None:
        self.assertEqual(
            inspection_id(CL, "2024-06-01T00:00:00Z", "worker-01"),
            f"inspection:{CL}:2024-06-01T00_00_00Z:worker-01",
        )

    def test_event_id_structured(self) -> None:
        eid = event_id(
            cluster_id=CL_SANDBOX,
            namespace="sandbox",
            object_kind="Pod",
            object_name="nginx-1",
            reason="Failed",
            last_timestamp="2024-06-15T12:00:00Z",
        )
        self.assertTrue(
            eid.startswith(f"event:{CL_SANDBOX}:sandbox:Pod:nginx-1:Failed:")
        )

    def test_event_id_hash_when_long(self) -> None:
        long_name = "p" * 200
        eid = event_id(
            cluster_id=CL_SANDBOX,
            namespace="sandbox",
            object_kind="Pod",
            object_name=long_name,
            reason="Failed",
            last_timestamp="2024-06-15T12:00:00Z",
        )
        self.assertTrue(eid.startswith(f"event:{CL_SANDBOX}:sandbox:"))
        self.assertNotIn(long_name, eid)
        self.assertEqual(len(eid.split(":")[-1]), 16)


class TestMcpPodMapping(unittest.TestCase):
    def test_pod_entity_uses_tool_namespace(self) -> None:
        mcp_json = {
            "query": "get_pods",
            "results": [{"name": "payment-1", "status": "Running"}],
        }
        ent = entity_from_pod_row(
            mcp_json["results"][0], "sandbox", cluster_id=CL_SANDBOX
        )
        self.assertEqual(ent.type, EntityType.POD)
        self.assertEqual(ent.id, f"pod:{CL_SANDBOX}/sandbox/payment-1")
        self.assertEqual(ent.properties["namespace"], "sandbox")
        self.assertEqual(ent.properties["cluster_id"], CL_SANDBOX)

    def test_pod_optional_labels_timestamp(self) -> None:
        ent = entity_from_pod_row(
            {"name": "p1", "status": "Running"},
            "default",
            cluster_id=CL,
            labels={"app": "web"},
            creation_timestamp="2024-01-01T00:00:00Z",
        )
        self.assertEqual(ent.properties["labels"], {"app": "web"})


class TestMcpEventMapping(unittest.TestCase):
    def test_event_entity_from_normalize_row(self) -> None:
        row = {
            "type": "Warning",
            "reason": "Failed",
            "message": "container crash",
            "object_kind": "Pod",
            "object_name": "payment-1",
            "namespace": "sandbox",
            "count": 2,
            "last_timestamp": "2024-06-15T12:00:00Z",
        }
        ent = entity_from_event_row(row, cluster_id=CL_SANDBOX)
        self.assertEqual(ent.type, EntityType.EVENT)
        self.assertEqual(ent.properties["cluster_id"], CL_SANDBOX)


class TestNodeAndScheduledOn(unittest.TestCase):
    def test_node_entity_and_scheduled_on(self) -> None:
        node = entity_from_node("worker-01", cluster_id=CL, labels={"zone": "a"})
        self.assertEqual(node.id, f"node:{CL}/worker-01")
        pid = pod_id(CL, "default", "p1")
        edge = edge_pod_to_node(pid, node.id)
        self.assertEqual(edge.relation, RelationType.SCHEDULED_ON)


class TestGraphBatchFromPodsEvents(unittest.TestCase):
    def test_from_pods_events(self) -> None:
        pods_mcp = {
            "query": "get_pods",
            "cluster_id": CL_SANDBOX,
            "results": [{"name": "payment-1", "status": "Running"}],
        }
        events_mcp = {
            "query": "get_events",
            "cluster_id": CL_SANDBOX,
            "results": [
                {
                    "type": "Warning",
                    "reason": "Failed",
                    "message": "x",
                    "object_kind": "Pod",
                    "object_name": "payment-1",
                    "namespace": "sandbox",
                    "count": 1,
                    "last_timestamp": "2024-06-15T12:00:00Z",
                }
            ],
        }
        batch = GraphBatch.from_pods_events(pods_mcp, events_mcp, "sandbox")
        self.assertEqual(len(batch.entities), 2)
        self.assertEqual(len(batch.edges), 1)

    def test_from_pods_events_dedupes_entities(self) -> None:
        pods_mcp = {
            "query": "get_pods",
            "cluster_id": CL_SANDBOX,
            "results": [{"name": "p1", "status": "Running"}],
        }
        events_mcp = {
            "query": "get_events",
            "cluster_id": CL_SANDBOX,
            "results": [
                {
                    "reason": "A",
                    "object_kind": "Pod",
                    "object_name": "other",
                    "namespace": "sandbox",
                },
                {
                    "reason": "B",
                    "object_kind": "Pod",
                    "object_name": "other",
                    "namespace": "sandbox",
                },
            ],
        }
        batch = GraphBatch.from_pods_events(
            pods_mcp, events_mcp, "sandbox", link_pod_events=False
        )
        self.assertEqual(len(batch.entities), 3)
        self.assertEqual(len(batch.edges), 0)


class TestGraphBatchAndEdges(unittest.TestCase):
    def test_pod_to_event_edge_from_mock_mcp(self) -> None:
        pods_mcp = {
            "query": "get_pods",
            "cluster_id": CL_SANDBOX,
            "results": [{"name": "payment-1", "status": "Running"}],
        }
        events_mcp = {
            "query": "get_events",
            "cluster_id": CL_SANDBOX,
            "results": [
                {
                    "type": "Warning",
                    "reason": "Failed",
                    "message": "x",
                    "object_kind": "Pod",
                    "object_name": "payment-1",
                    "namespace": "sandbox",
                    "count": 1,
                    "last_timestamp": "2024-06-15T12:00:00Z",
                }
            ],
        }
        batch = GraphBatch.from_pods_events(pods_mcp, events_mcp, "sandbox")
        self.assertEqual(len(batch.entities), 2)
        self.assertEqual(len(batch.edges), 1)

    def test_inspection_edges(self) -> None:
        insp = entity_from_inspection(
            "2024-06-01T00:00:00Z",
            "worker-01",
            "ok",
            "all healthy",
            cluster_id=CL,
        )
        pod = entity_from_pod_row(
            {"name": "p1", "status": "Running"}, "default", cluster_id=CL
        )
        edge = edge_inspection_to_pod(insp.id, pod.id)
        self.assertEqual(edge.relation, RelationType.INSPECTS_POD)

    def test_edge_to_dict_wire_only(self) -> None:
        edge = edge_pod_to_event("pod:a/b", "event:x")
        wire = edge.to_dict(wire_only=True)
        self.assertNotIn("kind", wire)
        self.assertEqual(wire["relation"], "has_event")


if __name__ == "__main__":
    unittest.main()
