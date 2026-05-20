"""Inspect pipeline: gather reuse, on_error=mark, single GraphView parse."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent import (
    InspectPipelineError,
    build_inspection_report,
    build_inspection_with_diagnosis,
    gather_subgraph,
)
from config.tenant_registry import TenantAccessError
from query.graph_view import GraphView
from testing.multicluster_fixtures import (
    CLUSTER_DEV,
    CLUSTER_PROD,
    POD_ALPHA_PROD,
    TENANT_ALPHA,
    dual_cluster_rich_payload,
    tenant_acl_matrix_payload,
)


class TestGatherReuse(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = dual_cluster_rich_payload()

    def test_build_inspection_with_diagnosis_reuses_gather(self) -> None:
        g = gather_subgraph(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="crash-pod",
        )
        with mock.patch(
            "agent.inspect.gather_subgraph",
            side_effect=AssertionError("should not re-gather"),
        ):
            narrative, diagnosis, execution = build_inspection_with_diagnosis(
                self.payload,
                cluster_id=CLUSTER_DEV,
                namespace="default",
                pod_name="crash-pod",
                gather=g,
                use_llm=False,
            )
        self.assertIn("CrashLoop", diagnosis["issues"])
        self.assertTrue(narrative.get("ok", True))
        self.assertTrue(execution.get("ok", True))

    def test_build_inspection_report_reuses_gather(self) -> None:
        g = gather_subgraph(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="shared-pod",
        )
        with mock.patch(
            "agent.inspect.gather_subgraph",
            side_effect=AssertionError("should not re-gather"),
        ):
            report = build_inspection_report(
                self.payload,
                cluster_id=CLUSTER_DEV,
                namespace="default",
                pod_name="shared-pod",
                gather=g,
                use_llm=False,
            )
        self.assertIn("Inspection report", report["markdown"])


class TestSingleGraphViewParse(unittest.TestCase):
    def test_gather_parses_payload_once(self) -> None:
        payload = dual_cluster_rich_payload()
        calls: list[str] = []

        original = GraphView.from_payload

        def counting_from_payload(p: dict) -> GraphView:
            calls.append("from_payload")
            return original(p)

        with mock.patch.object(GraphView, "from_payload", side_effect=counting_from_payload):
            gather_subgraph(
                payload,
                cluster_id=CLUSTER_DEV,
                namespace="default",
                pod_name="crash-pod",
            )
        self.assertEqual(calls, ["from_payload"])


class TestOnErrorMark(unittest.TestCase):
    def test_acl_failure_returns_marked_reports(self) -> None:
        payload = tenant_acl_matrix_payload()
        narrative, diagnosis, execution = build_inspection_with_diagnosis(
            payload,
            cluster_id=CLUSTER_PROD,
            namespace="default",
            pod_name=POD_ALPHA_PROD,
            tenant_id=TENANT_ALPHA,
            on_error="mark",
            use_llm=False,
        )
        self.assertFalse(narrative["ok"])
        self.assertEqual(narrative["error_stage"], "gather")
        self.assertFalse(diagnosis["ok"])
        self.assertFalse(execution["ok"])

    def test_on_error_raise_still_raises(self) -> None:
        payload = tenant_acl_matrix_payload()
        with self.assertRaises(InspectPipelineError):
            build_inspection_with_diagnosis(
                payload,
                cluster_id=CLUSTER_PROD,
                namespace="default",
                pod_name=POD_ALPHA_PROD,
                tenant_id=TENANT_ALPHA,
                on_error="raise",
                use_llm=False,
            )


if __name__ == "__main__":
    unittest.main()
