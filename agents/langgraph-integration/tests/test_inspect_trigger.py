"""W7 inspect_trigger tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from trigger.inspect_trigger import trigger_inspect


class TestInspectTrigger(unittest.TestCase):
    @mock.patch("trigger.inspect_trigger.get_langgraph_client")
    @mock.patch("trigger.inspect_trigger.stream_sentinel_run")
    @mock.patch("trigger.inspect_trigger.get_inspect_outputs_from_stream")
    def test_trigger_inspect_ok(self, mock_outputs, mock_stream, _mock_client) -> None:
        mock_stream.return_value = iter([{"payload": {}}])
        mock_outputs.return_value = {
            "diagnosis": {"issues": ["CrashLoop"], "ok": True},
            "execution": {
                "dry_run": True,
                "actions_taken": [{"action": "restart_pod", "status": "simulated"}],
                "ok": True,
            },
            "narrative": {"summary": "pod needs attention"},
        }
        result = trigger_inspect(
            cluster_id="k3s-prod",
            namespace="kube-system",
            pod_name="crash-pod",
            dry_run=True,
            thread_id="5ad00ee0-6f4d-5cd6-a021-99469a86e4e1",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["issues"], ["CrashLoop"])
        self.assertIn("restart_pod", str(result["execution"]))

    @mock.patch("trigger.inspect_trigger.get_langgraph_client")
    @mock.patch("trigger.inspect_trigger.stream_sentinel_run")
    def test_trigger_inspect_connection_error(self, mock_stream, _mock_client) -> None:
        mock_stream.side_effect = ConnectionError("refused")
        result = trigger_inspect(
            cluster_id="k3s-prod",
            namespace="kube-system",
            pod_name="p1",
            dry_run=True,
            thread_id="5ad00ee0-6f4d-5cd6-a021-99469a86e4e1",
        )
        self.assertFalse(result["ok"])
        self.assertIn("refused", result.get("error") or "")


if __name__ == "__main__":
    unittest.main()
