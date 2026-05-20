"""Phase C: tenant registry ACL and query tenant filtering."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config.tenant_registry import (
    TenantAccessError,
    allowed_clusters,
    assert_tenant_cluster_access,
)
from models.scope import sync_thread_id
from query.operations import run_query
from testing.multicluster_fixtures import (
    CLUSTER_DEV,
    CLUSTER_PROD,
    POD_ALPHA_DEV,
    POD_ALPHA_PROD,
    POD_BETA_DEV,
    POD_BETA_PROD,
    TENANT_ALPHA,
    TENANT_BETA,
    tenant_acl_matrix_payload,
)


class TestTenantRegistry(unittest.TestCase):
    def test_allowed_clusters_alpha_dev_only(self) -> None:
        self.assertEqual(allowed_clusters(TENANT_ALPHA), ["dev-cluster"])

    def test_allowed_clusters_beta_dev_prod(self) -> None:
        self.assertEqual(
            allowed_clusters(TENANT_BETA),
            ["dev-cluster", "prod-cluster"],
        )

    def test_unknown_tenant_raises(self) -> None:
        with self.assertRaises(TenantAccessError):
            allowed_clusters("unknown-tenant")

    def test_assert_denies_prod_for_team_alpha(self) -> None:
        with self.assertRaises(TenantAccessError):
            assert_tenant_cluster_access(TENANT_ALPHA, CLUSTER_PROD)

    def test_registry_aligns_with_sync_scope(self) -> None:
        self.assertEqual(
            sync_thread_id(CLUSTER_DEV, TENANT_ALPHA),
            "team-alpha:dev-cluster",
        )


class TestQueryNoTenantId(unittest.TestCase):
    """Without tenant_id: third-edition behavior (cluster scope only)."""

    def setUp(self) -> None:
        self.payload = tenant_acl_matrix_payload()

    def test_no_tenant_id_same_as_legacy_list_pods(self) -> None:
        dev = run_query(
            self.payload, "list_pods", cluster_id=CLUSTER_DEV
        )
        prod = run_query(
            self.payload, "list_pods", cluster_id=CLUSTER_PROD
        )
        dev_names = {p["name"] for p in dev["pods"]}
        prod_names = {p["name"] for p in prod["pods"]}
        self.assertIn(POD_ALPHA_DEV, dev_names)
        self.assertIn(POD_BETA_DEV, dev_names)
        self.assertIn(POD_BETA_PROD, prod_names)
        self.assertIn(POD_ALPHA_PROD, prod_names)

    def test_no_tenant_id_events_for_pod_unchanged(self) -> None:
        result = run_query(
            self.payload,
            "events_for_pod",
            cluster_id=CLUSTER_DEV,
            namespace="default",
            name=POD_ALPHA_DEV,
        )
        self.assertGreaterEqual(result["count"], 1)


class TestQueryWithTenantId(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = tenant_acl_matrix_payload()

    def test_list_pods_alpha_dev(self) -> None:
        result = run_query(
            self.payload,
            "list_pods",
            cluster_id=CLUSTER_DEV,
            tenant_id=TENANT_ALPHA,
        )
        self.assertGreaterEqual(result["count"], 1)
        for pod in result["pods"]:
            ent = next(
                e
                for e in self.payload["entities"]
                if e.get("id") == pod["id"]
            )
            self.assertEqual(
                ent.get("properties", {}).get("tenant_id"), TENANT_ALPHA
            )

    def test_list_pods_alpha_prod_denied(self) -> None:
        with self.assertRaises(TenantAccessError):
            run_query(
                self.payload,
                "list_pods",
                cluster_id=CLUSTER_PROD,
                tenant_id=TENANT_ALPHA,
            )

    def test_list_pods_beta_prod(self) -> None:
        result = run_query(
            self.payload,
            "list_pods",
            cluster_id=CLUSTER_PROD,
            tenant_id=TENANT_BETA,
        )
        self.assertGreaterEqual(result["count"], 1)
        names = {p["name"] for p in result["pods"]}
        self.assertIn(POD_BETA_PROD, names)
        self.assertNotIn(POD_ALPHA_PROD, names)

    def test_list_pods_beta_dev_sees_only_beta(self) -> None:
        result = run_query(
            self.payload,
            "list_pods",
            cluster_id=CLUSTER_DEV,
            tenant_id=TENANT_BETA,
        )
        names = {p["name"] for p in result["pods"]}
        self.assertIn(POD_BETA_DEV, names)
        self.assertNotIn(POD_ALPHA_DEV, names)

    def test_pod_status_cross_tenant_same_cluster(self) -> None:
        result = run_query(
            self.payload,
            "pod_status",
            cluster_id=CLUSTER_DEV,
            namespace="default",
            name=POD_BETA_DEV,
            tenant_id=TENANT_ALPHA,
        )
        self.assertFalse(result["found"])

    def test_list_clusters_for_tenant(self) -> None:
        result = run_query(
            self.payload,
            "list_clusters_for_tenant",
            tenant_id=TENANT_ALPHA,
        )
        self.assertEqual(result["clusters"], ["dev-cluster"])


if __name__ == "__main__":
    unittest.main()
