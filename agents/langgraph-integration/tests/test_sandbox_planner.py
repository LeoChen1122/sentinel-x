"""W6 sandbox planner tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent.types import ActionContext
from sandbox.config import SandboxConfig
from sandbox.planner import plan_action


def _cfg() -> SandboxConfig:
    return SandboxConfig(
        enabled=True,
        namespace="sentinel-sandbox",
        audit_dir=Path("/tmp/sentinel-audit"),
        image="sentinel-x-sandbox:latest",
        timeout_sec=60,
        max_replicas=5,
        kubeconfig=Path("/tmp/kubeconfig"),
        ready_sec=30,
        verify_poll_sec=5,
        verify_timeout_sec=120,
        payload_truncate=4096,
    )


def _ctx(*, namespace: str = "sentinel-sandbox", pod: str = "crash-demo-abc12") -> ActionContext:
    return ActionContext(
        cluster_id="dev",
        namespace=namespace,
        pod_name=pod,
        pod_id=f"pod:dev:{namespace}:{pod}",
        tenant_id=None,
    )


class TestSandboxPlanner(unittest.TestCase):
    def test_restart_pod_plan(self) -> None:
        plan = plan_action("restart_pod", _ctx(), _cfg())
        self.assertFalse(plan.blocked)
        self.assertEqual(
            plan.argv,
            ["kubectl", "delete", "pod", "crash-demo-abc12", "-n", "sentinel-sandbox"],
        )

    @mock.patch(
        "sandbox.planner.check_scale_up_allowed",
        return_value=(True, "ok", 2),
    )
    def test_scale_up_plan(self, _mock_preflight) -> None:
        plan = plan_action("scale_up", _ctx(pod="crash-demo-rs-xyz"), _cfg())
        self.assertFalse(plan.blocked)
        self.assertIn("scale", plan.argv)
        self.assertIn("deployment", plan.argv)
        self.assertIn("crash-demo", plan.argv)
        self.assertIn("--replicas=2", plan.argv)

    @mock.patch(
        "sandbox.planner.check_scale_up_allowed",
        return_value=(False, "replicas_at_cap (5>=5)", 0),
    )
    def test_scale_up_blocked_at_cap(self, _mock_preflight) -> None:
        plan = plan_action("scale_up", _ctx(pod="crash-demo-rs-xyz"), _cfg())
        self.assertTrue(plan.blocked)
        self.assertIn("replicas_at_cap", plan.reason)

    def test_production_namespace_blocked(self) -> None:
        plan = plan_action("restart_pod", _ctx(namespace="kube-system"), _cfg())
        self.assertTrue(plan.blocked)
        self.assertEqual(plan.argv, [])


if __name__ == "__main__":
    unittest.main()
