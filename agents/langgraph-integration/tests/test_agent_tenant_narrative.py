"""Phase C: agent inspect/gather with tenant ACL."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent import build_inspection_report, gather_subgraph
from config.tenant_registry import TenantAccessError
from testing.multicluster_fixtures import (
    CLUSTER_DEV,
    CLUSTER_PROD,
    POD_ALPHA_DEV,
    POD_ALPHA_PROD,
    POD_BETA_DEV,
    POD_BETA_PROD,
    TENANT_ALPHA,
    TENANT_BETA,
    dual_cluster_rich_batch,
    tenant_acl_matrix_payload,
)


class TestAgentTenantNarrative(unittest.TestCase):
    def setUp(self) -> None:
        self.matrix = tenant_acl_matrix_payload()
        self.rich = dual_cluster_rich_batch().to_dict(wire_only=True)

    def test_inspect_alpha_dev_ok(self) -> None:
        report = build_inspection_report(
            self.matrix,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name=POD_ALPHA_DEV,
            tenant_id=TENANT_ALPHA,
            use_llm=False,
        )
        self.assertIn(CLUSTER_DEV, report["markdown"])
        self.assertIn(CLUSTER_DEV, report["summary"])

    def test_inspect_alpha_prod_raises(self) -> None:
        with self.assertRaises(TenantAccessError):
            build_inspection_report(
                self.matrix,
                cluster_id=CLUSTER_PROD,
                namespace="default",
                pod_name=POD_ALPHA_PROD,
                tenant_id=TENANT_ALPHA,
                use_llm=False,
            )

    def test_inspect_beta_prod_ok(self) -> None:
        report = build_inspection_report(
            self.matrix,
            cluster_id=CLUSTER_PROD,
            namespace="default",
            pod_name=POD_BETA_PROD,
            tenant_id=TENANT_BETA,
            use_llm=False,
        )
        self.assertIn(CLUSTER_PROD, report["markdown"])

    def test_inspect_beta_dev_ok(self) -> None:
        report = build_inspection_report(
            self.matrix,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name=POD_BETA_DEV,
            tenant_id=TENANT_BETA,
            use_llm=False,
        )
        self.assertGreater(len(report["sections"]), 0)
        for ent in report.get("linked_events", []):
            eid = ent.get("entity_id", "")
            self.assertTrue(eid.startswith(f"event:{CLUSTER_DEV}:"))

    def test_gather_subgraph_entity_tenants_uniform(self) -> None:
        g = gather_subgraph(
            self.matrix,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name=POD_BETA_DEV,
            tenant_id=TENANT_BETA,
        )
        for ent in g["subgraph"]["entities"]:
            props = ent.get("properties") or {}
            self.assertEqual(props.get("tenant_id"), TENANT_BETA)

    def test_no_tenant_id_inspect_same_as_phase_ab(self) -> None:
        report = build_inspection_report(
            self.rich,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="shared-pod",
            use_llm=False,
        )
        self.assertIn("markdown", report)
        self.assertNotIn("TenantAccessError", report.get("summary", ""))


if __name__ == "__main__":
    unittest.main()
