"""Phase 5: rule diagnosis and dry-run action execution."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent import (
    InspectPipelineError,
    build_inspection_with_diagnosis,
    diagnose_from_gather,
    execute_recommended_actions,
    gather_subgraph,
)
from agent.actions.builtin import _BUILTIN_MESSAGES
from agent.actions.policy import action_context_from_diagnosis, validate_execution_policy
from agent.types import ActionContext, DiagnosisReport
from config.tenant_registry import TenantAccessError
from models.ids import pod_id
from testing.multicluster_fixtures import (
    CLUSTER_DEV,
    CLUSTER_PROD,
    POD_ALPHA_PROD,
    TENANT_ALPHA,
    dual_cluster_rich_batch,
    dual_cluster_rich_payload,
    tenant_acl_matrix_payload,
)


class TestDiagnoseRules(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = dual_cluster_rich_payload()

    def test_crash_pod_diagnosis(self) -> None:
        g = gather_subgraph(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="crash-pod",
        )
        diag = diagnose_from_gather(g)
        self.assertIn("CrashLoop", diag["issues"])
        self.assertIn("restart_pod", diag["recommended_actions"])
        self.assertEqual(diag["severity"], "critical")
        self.assertEqual(diag["diagnosis_source"], "rules_v1")

    def test_shared_pod_warning_severity(self) -> None:
        g = gather_subgraph(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="shared-pod",
        )
        diag = diagnose_from_gather(g)
        self.assertIn(diag["severity"], ("ok", "warning"))
        if diag["severity"] == "warning":
            self.assertTrue(
                "WarningEvents" in diag["issues"]
                or "SchedulingFailure" in diag["issues"]
            )

    def test_diagnosis_pod_id_matches_phase4(self) -> None:
        g = gather_subgraph(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="shared-pod",
        )
        diag = diagnose_from_gather(g)
        expected = pod_id(CLUSTER_DEV, "default", "shared-pod")
        self.assertEqual(diag["pod_id"], expected)
        self.assertEqual(diag["pod_id"], g["pod_entity_id"])

    def test_execute_dry_run_simulated(self) -> None:
        g = gather_subgraph(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="crash-pod",
        )
        diag = diagnose_from_gather(g)
        result = execute_recommended_actions(diag, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result.get("execution_source"), "registry_v1")
        self.assertGreater(len(result["actions_taken"]), 0)
        for rec in result["actions_taken"]:
            self.assertEqual(rec["status"], "simulated")
            self.assertEqual(rec["target"], diag["pod_id"])

    def test_each_builtin_action_produces_record(self) -> None:
        pid = pod_id(CLUSTER_DEV, "default", "crash-pod")
        for action in _BUILTIN_MESSAGES:
            diag = DiagnosisReport(
                cluster_id=CLUSTER_DEV,
                namespace="default",
                pod_name="crash-pod",
                pod_id=pid,
                tenant_id=None,
                issues=["CrashLoop"],
                recommended_actions=[action],
                severity="critical",
                diagnosis_source="rules_v1",
                ok=True,
            )
            result = execute_recommended_actions(diag, dry_run=True)
            self.assertEqual(len(result["actions_taken"]), 1)
            self.assertEqual(result["actions_taken"][0]["action"], action)

    def test_unknown_action_skipped(self) -> None:
        g = gather_subgraph(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="crash-pod",
        )
        diag = diagnose_from_gather(g)
        diag = DiagnosisReport(
            **{**dict(diag), "recommended_actions": ["restart_pod", "nonexistent_action"]}
        )
        result = execute_recommended_actions(diag, dry_run=True)
        self.assertIn("nonexistent_action", result["skipped"])
        self.assertEqual(len(result["actions_taken"]), 1)

    def test_execute_tenant_denied_returns_marked_failure(self) -> None:
        pid = pod_id(CLUSTER_PROD, "default", POD_ALPHA_PROD)
        diag = DiagnosisReport(
            cluster_id=CLUSTER_PROD,
            namespace="default",
            pod_name=POD_ALPHA_PROD,
            pod_id=pid,
            tenant_id=TENANT_ALPHA,
            issues=["CrashLoop"],
            recommended_actions=["restart_pod"],
            severity="critical",
            diagnosis_source="rules_v1",
            ok=True,
        )
        ctx = action_context_from_diagnosis(diag)
        with self.assertRaises(TenantAccessError):
            validate_execution_policy(ctx)
        result = execute_recommended_actions(diag, dry_run=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_stage"], "execute_policy")
        self.assertEqual(result["actions_taken"], [])

    def test_execute_live_without_flag_raises(self) -> None:
        g = gather_subgraph(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="crash-pod",
        )
        diag = diagnose_from_gather(g)
        with self.assertRaises(NotImplementedError):
            execute_recommended_actions(diag, dry_run=False)


class TestDiagnoseOrchestration(unittest.TestCase):
    def test_build_inspection_with_diagnosis(self) -> None:
        payload = dual_cluster_rich_payload()
        narrative, diagnosis, execution = build_inspection_with_diagnosis(
            payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="crash-pod",
            use_llm=False,
        )
        self.assertIn("CrashLoopBackOff", narrative["markdown"])
        self.assertIn("CrashLoop", diagnosis["issues"])
        self.assertTrue(execution["dry_run"])

    def test_tenant_alpha_prod_raises_before_diagnose(self) -> None:
        payload = tenant_acl_matrix_payload()
        with self.assertRaises(InspectPipelineError) as ctx:
            build_inspection_with_diagnosis(
                payload,
                cluster_id=CLUSTER_PROD,
                namespace="default",
                pod_name=POD_ALPHA_PROD,
                tenant_id=TENANT_ALPHA,
                use_llm=False,
            )
        self.assertIsInstance(ctx.exception.cause, TenantAccessError)

    def test_no_tenant_diagnosis_works(self) -> None:
        payload = dual_cluster_rich_batch().to_dict(wire_only=True)
        _, diagnosis, _ = build_inspection_with_diagnosis(
            payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="crash-pod",
            use_llm=False,
        )
        self.assertIsNone(diagnosis.get("tenant_id"))
        self.assertIn("CrashLoop", diagnosis["issues"])


class TestGraphDiagnoseFlow(unittest.TestCase):
    def test_graph_nodes_produce_diagnosis_and_execution(self) -> None:
        server_src = Path(__file__).resolve().parents[2] / "langgraph-server" / "src"
        if str(server_src) not in sys.path:
            sys.path.insert(0, str(server_src))
        from graph import graph  # noqa: E402

        payload = dual_cluster_rich_payload()
        payload["inspect"] = {
            "cluster_id": CLUSTER_DEV,
            "namespace": "default",
            "pod_name": "crash-pod",
        }
        result = graph.invoke({"payload": payload})
        out = result.get("payload") or {}
        self.assertIn("narrative", out)
        self.assertIn("diagnosis", out)
        self.assertIn("execution", out)
        self.assertIn("CrashLoop", out["diagnosis"]["issues"])
        self.assertTrue(out["execution"]["dry_run"])
        self.assertEqual(out["execution"].get("execution_source"), "registry_v1")


if __name__ == "__main__":
    unittest.main()
