"""Phase 4-0: multicluster mock data + model validation (no live K8s)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from models.entities import EntityType  # noqa: E402
from models.ids import pod_id  # noqa: E402
from query import run_query  # noqa: E402
from testing.multicluster_fixtures import (  # noqa: E402
    CLUSTER_DEV,
    CLUSTER_PROD,
    dual_cluster_full_batch,
    dual_cluster_merged_batch,
    pods_events_batch,
)


class TestDualClusterIds(unittest.TestCase):
    def test_same_pod_name_different_cluster_ids(self) -> None:
        dev_pid = pod_id(CLUSTER_DEV, "default", "shared-pod")
        prod_pid = pod_id(CLUSTER_PROD, "default", "shared-pod")
        self.assertNotEqual(dev_pid, prod_pid)
        self.assertTrue(dev_pid.startswith(f"pod:{CLUSTER_DEV}/"))
        self.assertTrue(prod_pid.startswith(f"pod:{CLUSTER_PROD}/"))

    def test_merge_preserves_both_pods(self) -> None:
        batch = dual_cluster_merged_batch()
        pod_ids = {e.id for e in batch.entities if e.type is EntityType.POD}
        self.assertEqual(len(pod_ids), 2)
        self.assertIn(pod_id(CLUSTER_DEV, "default", "shared-pod"), pod_ids)
        self.assertIn(pod_id(CLUSTER_PROD, "default", "shared-pod"), pod_ids)


class TestQueryClusterIsolation(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = dual_cluster_merged_batch().to_dict(wire_only=True)

    def test_events_for_pod_dev_only(self) -> None:
        out = run_query(
            self.payload,
            "events_for_pod",
            cluster_id=CLUSTER_DEV,
            namespace="default",
            name="shared-pod",
        )
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["cluster_id"], CLUSTER_DEV)

    def test_events_for_pod_prod_reason(self) -> None:
        out = run_query(
            self.payload,
            "events_for_pod",
            cluster_id=CLUSTER_PROD,
            namespace="default",
            name="shared-pod",
        )
        self.assertEqual(out["count"], 1)
        events = pods_events_batch(CLUSTER_PROD)
        prod_reason = next(
            e.properties["reason"]
            for e in events.entities
            if e.type is EntityType.EVENT
        )
        self.assertEqual(out["events"][0]["reason"], prod_reason)

    def test_list_pods_filter_cluster(self) -> None:
        out = run_query(self.payload, "list_pods", cluster_id=CLUSTER_DEV)
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["pods"][0]["cluster_id"], CLUSTER_DEV)

    def test_pod_status_requires_cluster(self) -> None:
        from query.operations import QueryError

        with self.assertRaises(QueryError):
            run_query(
                self.payload,
                "pod_status",
                namespace="default",
                name="shared-pod",
            )


class TestQueryFullMulticlusterBatch(unittest.TestCase):
    """Query isolation on dual_cluster_full_batch (Pod/Event/Node/Inspection)."""

    def setUp(self) -> None:
        self.payload = dual_cluster_full_batch().to_dict(wire_only=True)

    def test_list_events_dev_only(self) -> None:
        out = run_query(self.payload, "list_events", cluster_id=CLUSTER_DEV)
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["events"][0]["reason"], "FailedScheduling")

    def test_list_events_prod_only(self) -> None:
        out = run_query(self.payload, "list_events", cluster_id=CLUSTER_PROD)
        self.assertEqual(out["count"], 1)

    def test_inspections_for_pod_per_cluster(self) -> None:
        for cid in (CLUSTER_DEV, CLUSTER_PROD):
            out = run_query(
                self.payload,
                "inspections_for_pod",
                cluster_id=cid,
                namespace="default",
                name="shared-pod",
            )
            self.assertEqual(out["count"], 1, cid)
            self.assertEqual(out["cluster_id"], cid)

    def test_inspections_for_pod_cross_cluster_empty(self) -> None:
        out = run_query(
            self.payload,
            "inspections_for_pod",
            cluster_id=CLUSTER_DEV,
            namespace="default",
            name="shared-pod",
        )
        self.assertEqual(out["count"], 1)
        # prod inspection exists but query scoped to dev pod id only
        out_wrong = run_query(
            self.payload,
            "inspections_for_pod",
            cluster_id=CLUSTER_PROD,
            namespace="default",
            name="nonexistent-pod",
        )
        self.assertEqual(out_wrong["count"], 0)

    def test_inspections_summary_filter(self) -> None:
        dev = run_query(self.payload, "inspections_summary", cluster_id=CLUSTER_DEV)
        prod = run_query(self.payload, "inspections_summary", cluster_id=CLUSTER_PROD)
        self.assertEqual(dev["count"], 1)
        self.assertEqual(prod["count"], 1)

    def test_events_for_pod_linked_events_symmetry(self) -> None:
        dev = run_query(
            self.payload,
            "events_for_pod",
            cluster_id=CLUSTER_DEV,
            namespace="default",
            name="shared-pod",
        )
        prod = run_query(
            self.payload,
            "events_for_pod",
            cluster_id=CLUSTER_PROD,
            namespace="default",
            name="shared-pod",
        )
        self.assertEqual(dev["count"], 1)
        self.assertEqual(prod["count"], 1)
        self.assertIn("event on dev-cluster", dev["events"][0].get("message", ""))
        self.assertIn("event on prod-cluster", prod["events"][0].get("message", ""))

    def test_scheduled_on_edges_present(self) -> None:
        edges = self.payload.get("edges") or []
        scheduled = [
            e
            for e in edges
            if isinstance(e, dict) and e.get("relation") == "scheduled_on"
        ]
        self.assertEqual(len(scheduled), 2)


class TestMcpClusterIdRequired(unittest.TestCase):
    def test_adapter_raises_without_cluster_id(self) -> None:
        from adapter.k8s import pods_events_to_batch

        with self.assertRaises(ValueError):
            pods_events_to_batch(
                {"query": "get_pods", "results": []},
                {"query": "get_events", "results": []},
                "default",
            )


if __name__ == "__main__":
    unittest.main()
