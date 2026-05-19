"""Agent phase A: inspection narrative, gather, cluster isolation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent import build_inspection_report, build_report, gather_subgraph
from models.ids import pod_id
from testing.multicluster_fixtures import (
    CLUSTER_DEV,
    CLUSTER_PROD,
    dual_cluster_full_batch,
    dual_cluster_rich_batch,
    dual_cluster_rich_payload,
)


class TestInspectionReportShape(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = dual_cluster_full_batch().to_dict(wire_only=True)

    def test_report_has_typed_shape(self) -> None:
        report = build_inspection_report(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="shared-pod",
            use_llm=False,
        )
        self.assertIn("markdown", report)
        self.assertIn("sections", report)
        self.assertIn("linked_events", report)
        self.assertIn("linked_pods", report)
        self.assertIn("linked_inspections", report)
        self.assertIn("summary", report)
        self.assertGreater(len(report["sections"]), 0)

    def test_linked_events_use_entity_ids(self) -> None:
        report = build_inspection_report(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="shared-pod",
            use_llm=False,
        )
        for le in report["linked_events"]:
            self.assertTrue(le["entity_id"].startswith(f"event:{CLUSTER_DEV}:"))

    def test_cluster_isolation(self) -> None:
        dev = build_inspection_report(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="shared-pod",
            use_llm=False,
        )
        prod = build_inspection_report(
            self.payload,
            cluster_id=CLUSTER_PROD,
            namespace="default",
            pod_name="shared-pod",
            use_llm=False,
        )
        self.assertNotEqual(dev["pod_entity_id"], prod["pod_entity_id"])
        self.assertIn(CLUSTER_DEV, dev["markdown"])
        self.assertIn(CLUSTER_PROD, prod["markdown"])
        self.assertIn(CLUSTER_DEV, dev["summary"])
        self.assertIn(CLUSTER_PROD, prod["summary"])

    def test_gather_subgraph_filters_cluster(self) -> None:
        g = gather_subgraph(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="shared-pod",
        )
        for ent in g["subgraph"]["entities"]:
            props = ent.get("properties") or {}
            self.assertEqual(props.get("cluster_id"), CLUSTER_DEV)


class TestRichMulticlusterNarrative(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = dual_cluster_rich_payload()

    def test_warning_reflected_in_summary(self) -> None:
        report = build_inspection_report(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="shared-pod",
            use_llm=False,
        )
        self.assertIn("needs attention", report["summary"])
        self.assertGreaterEqual(len(report["linked_events"]), 1)

    def test_crash_pod_status_in_report(self) -> None:
        report = build_inspection_report(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="crash-pod",
            use_llm=False,
        )
        self.assertIn("CrashLoopBackOff", report["markdown"])

    def test_cross_cluster_inspections_empty(self) -> None:
        """Prod pod name on dev cluster scope should not see prod inspections."""
        report = build_inspection_report(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="shared-pod",
            use_llm=False,
        )
        pid = pod_id(CLUSTER_DEV, "default", "shared-pod")
        self.assertEqual(report["pod_entity_id"], pid)
        for li in report["linked_inspections"]:
            self.assertTrue(li["entity_id"].startswith(f"inspection:{CLUSTER_DEV}:"))


class TestGraphNarrateFlow(unittest.TestCase):
    def test_build_report_from_gather_dict(self) -> None:
        payload = dual_cluster_full_batch().to_dict(wire_only=True)
        g = gather_subgraph(
            payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="shared-pod",
        )
        report = build_report(g, use_llm=False)
        self.assertEqual(report["cluster_id"], CLUSTER_DEV)
        self.assertIn("Inspection report", report["markdown"])


if __name__ == "__main__":
    unittest.main()
