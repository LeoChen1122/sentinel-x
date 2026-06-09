"""W6 sandbox kubectl policy tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sandbox.policy import namespace_allowed, validate_kubectl_argv


class TestSandboxPolicy(unittest.TestCase):
    def test_namespace_allowed(self) -> None:
        self.assertTrue(namespace_allowed("sentinel-sandbox", "sentinel-sandbox"))
        self.assertFalse(namespace_allowed("kube-system", "sentinel-sandbox"))

    def test_restart_pod_argv_ok(self) -> None:
        argv = ["kubectl", "delete", "pod", "crash-demo-abc", "-n", "sentinel-sandbox"]
        ok, reason = validate_kubectl_argv(argv, allowed_namespace="sentinel-sandbox")
        self.assertTrue(ok, reason)

    def test_rejects_all_namespaces(self) -> None:
        argv = ["kubectl", "get", "pods", "-A"]
        ok, _ = validate_kubectl_argv(argv, allowed_namespace="sentinel-sandbox")
        self.assertFalse(ok)

    def test_rejects_delete_namespace(self) -> None:
        argv = ["kubectl", "delete", "namespace", "foo", "-n", "sentinel-sandbox"]
        ok, _ = validate_kubectl_argv(argv, allowed_namespace="sentinel-sandbox")
        self.assertFalse(ok)

    def test_rejects_wrong_namespace(self) -> None:
        argv = ["kubectl", "delete", "pod", "x", "-n", "kube-system"]
        ok, _ = validate_kubectl_argv(argv, allowed_namespace="sentinel-sandbox")
        self.assertFalse(ok)

    def test_rejects_exec(self) -> None:
        argv = ["kubectl", "exec", "pod", "x", "-n", "sentinel-sandbox", "--", "sh"]
        ok, _ = validate_kubectl_argv(argv, allowed_namespace="sentinel-sandbox")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
