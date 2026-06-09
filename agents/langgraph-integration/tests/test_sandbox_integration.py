"""W6 sandbox runner integration (mocked docker)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent.types import ActionContext, ExecutionResult
from sandbox.config import SandboxConfig
from agent.types import SandboxVerification
from sandbox.runner import run_sandbox_for_execution

_VERIFIED = SandboxVerification(
    pass_=True,
    ready_seconds=30,
    message="sandbox_pass",
    deployment="crash-demo",
    checked_pod="crash-demo-x",
)


class TestSandboxIntegration(unittest.TestCase):
    @mock.patch(
        "sandbox.runner.verify_restart_pod_deployment",
        return_value=_VERIFIED,
    )
    def test_run_sandbox_for_execution_ok(self, _mock_verify) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kc = Path(tmp) / "config"
            kc.write_text("apiVersion: v1\n", encoding="utf-8")
            cfg = SandboxConfig(
                enabled=True,
                namespace="sentinel-sandbox",
                audit_dir=Path(tmp) / "audit",
                image="sentinel-x-sandbox:latest",
                timeout_sec=30,
                max_replicas=5,
                kubeconfig=kc,
                ready_sec=30,
                verify_poll_sec=5,
                verify_timeout_sec=120,
                payload_truncate=4096,
            )
            execution = ExecutionResult(
                dry_run=False,
                sandbox_pending=True,
                actions_taken=[
                    {
                        "action": "restart_pod",
                        "target": "pod:dev:sentinel-sandbox:crash-demo-x",
                        "status": "sandbox_pending",
                        "message": "q",
                    }
                ],
                skipped=[],
                ok=True,
                execution_source="registry_v1",
            )
            ctx = ActionContext(
                cluster_id="dev",
                namespace="sentinel-sandbox",
                pod_name="crash-demo-x",
                pod_id="pod:dev:sentinel-sandbox:crash-demo-x",
                tenant_id=None,
            )

            def fake_run(cmd, **kwargs):
                return CompletedProcess(cmd, 0, stdout="ok", stderr="")

            result = run_sandbox_for_execution(
                execution, ctx, cfg=cfg, run_subprocess=fake_run
            )
            self.assertTrue(result["ok"])
            self.assertEqual(len(result["runs"]), 1)
            self.assertEqual(result["runs"][0]["status"], "ok")
            self.assertTrue(result["verification"]["pass_"])

    def test_production_namespace_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = SandboxConfig(
                enabled=True,
                namespace="sentinel-sandbox",
                audit_dir=Path(tmp) / "audit",
                image="sentinel-x-sandbox:latest",
                timeout_sec=30,
                max_replicas=5,
                kubeconfig=Path(tmp) / "config",
                ready_sec=30,
                verify_poll_sec=5,
                verify_timeout_sec=120,
                payload_truncate=4096,
            )
            execution = ExecutionResult(
                dry_run=False,
                sandbox_pending=True,
                actions_taken=[
                    {
                        "action": "restart_pod",
                        "target": "pod:dev:kube-system:crash-pod",
                        "status": "sandbox_pending",
                        "message": "q",
                    }
                ],
                skipped=[],
                ok=True,
                execution_source="registry_v1",
            )
            ctx = ActionContext(
                cluster_id="dev",
                namespace="kube-system",
                pod_name="crash-pod",
                pod_id="pod:dev:kube-system:crash-pod",
                tenant_id=None,
            )
            result = run_sandbox_for_execution(execution, ctx, cfg=cfg)
            self.assertFalse(result["ok"])
            self.assertTrue(result["blocked"])
            self.assertEqual(result["runs"][0]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
