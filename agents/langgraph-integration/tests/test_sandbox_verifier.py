"""W6.1 sandbox verifier: Ready must hold for N seconds."""

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
from sandbox.verifier import verify_restart_pod_deployment


def _cfg(**overrides) -> SandboxConfig:
    base = dict(
        enabled=True,
        namespace="sentinel-sandbox",
        audit_dir=Path("/tmp/audit"),
        image="sentinel-x-sandbox:latest",
        timeout_sec=30,
        max_replicas=5,
        kubeconfig=Path("/tmp/kubeconfig"),
        ready_sec=10,
        verify_poll_sec=1,
        verify_timeout_sec=30,
        payload_truncate=4096,
    )
    base.update(overrides)
    return SandboxConfig(**base)


def _pod_json(name: str, *, ready: bool, crash: bool = False) -> dict:
    waiting = {"reason": "CrashLoopBackOff"} if crash else {}
    state = {"waiting": waiting} if crash else {"running": {}}
    conditions = [{"type": "Ready", "status": "True" if ready else "False"}]
    return {
        "metadata": {"name": name},
        "status": {
            "phase": "Running",
            "conditions": conditions,
            "containerStatuses": [{"state": state}],
        },
    }


class TestSandboxVerifier(unittest.TestCase):
    def test_ready_must_hold_not_instant_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kc = Path(tmp) / "config"
            kc.write_text("apiVersion: v1\n", encoding="utf-8")
            cfg = _cfg(ready_sec=10, kubeconfig=kc, verify_timeout_sec=60)
            t = [0.0]
            polls = [0]

            def mono():
                return t[0]

            def sleep(sec):
                t[0] += sec

            def fake_run(cmd, **kwargs):
                polls[0] += 1
                if polls[0] < 3:
                    body = {"items": [_pod_json("p1", ready=True)]}
                else:
                    body = {"items": [_pod_json("p1", ready=True, crash=True)]}
                return CompletedProcess(cmd, 0, stdout=json.dumps(body), stderr="")

            result = verify_restart_pod_deployment(
                "crash-demo",
                "sentinel-sandbox",
                cfg=cfg,
                run_subprocess=fake_run,
                sleep_fn=sleep,
                monotonic_fn=mono,
            )
            self.assertFalse(result.get("pass_"))
            self.assertEqual(result.get("message"), "sandbox_crash_loop_returned")

    def test_ready_held_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kc = Path(tmp) / "config"
            kc.write_text("apiVersion: v1\n", encoding="utf-8")
            cfg = _cfg(ready_sec=5, kubeconfig=kc, verify_timeout_sec=60)
            t = [0.0]

            def mono():
                return t[0]

            def sleep(sec):
                t[0] += sec

            def fake_run(cmd, **kwargs):
                body = {"items": [_pod_json("p1", ready=True)]}
                return CompletedProcess(cmd, 0, stdout=json.dumps(body), stderr="")

            result = verify_restart_pod_deployment(
                "crash-demo",
                "sentinel-sandbox",
                cfg=cfg,
                run_subprocess=fake_run,
                sleep_fn=sleep,
                monotonic_fn=mono,
            )
            self.assertTrue(result.get("pass_"))
            self.assertGreaterEqual(int(result.get("ready_seconds") or 0), 5)


if __name__ == "__main__":
    unittest.main()
