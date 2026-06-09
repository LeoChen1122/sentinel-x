"""W6 sandbox executor and audit tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sandbox.config import SandboxConfig
from sandbox.executor import run_sandbox_command


class TestSandboxExecutor(unittest.TestCase):
    def test_audit_on_success(self) -> None:
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
            argv = ["kubectl", "delete", "pod", "p1", "-n", "sentinel-sandbox"]

            def fake_run(cmd, **kwargs):
                return CompletedProcess(cmd, 0, stdout="pod deleted", stderr="")

            record = run_sandbox_command(
                argv,
                cfg=cfg,
                audit_meta={"action": "restart_pod", "namespace": "sentinel-sandbox", "pod": "p1"},
                run_subprocess=fake_run,
            )
            self.assertEqual(record["status"], "ok")
            self.assertEqual(record["exit_code"], 0)
            audit_path = Path(record["audit_path"])
            self.assertTrue(audit_path.is_file())
            self.assertRegex(audit_path.name, r"^audit-\d{4}-\d{2}\.jsonl$")
            line = json.loads(audit_path.read_text(encoding="utf-8").strip())
            self.assertEqual(line["action"], "restart_pod")

    def test_blocked_policy_no_docker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = SandboxConfig(
                enabled=True,
                namespace="sentinel-sandbox",
                audit_dir=Path(tmp) / "audit",
                image="sentinel-x-sandbox:latest",
                timeout_sec=30,
                max_replicas=5,
                kubeconfig=Path(tmp) / "missing",
                ready_sec=30,
                verify_poll_sec=5,
                verify_timeout_sec=120,
                payload_truncate=4096,
            )
            argv = ["kubectl", "delete", "pod", "p1", "-n", "kube-system"]
            record = run_sandbox_command(
                argv,
                cfg=cfg,
                audit_meta={"action": "restart_pod"},
                run_subprocess=lambda *a, **k: CompletedProcess([], 0),
            )
            self.assertTrue(record["blocked"])
            self.assertEqual(record["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
