"""Tests for pod/event normalization."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from utils.normalize import normalize_pod_list  # noqa: E402


class TestNormalizePodList(unittest.TestCase):
    def test_crashloop_uses_waiting_reason_not_phase(self) -> None:
        payload = {
            "items": [
                {
                    "metadata": {"name": "crash-demo"},
                    "status": {
                        "phase": "Running",
                        "containerStatuses": [
                            {
                                "state": {
                                    "waiting": {"reason": "CrashLoopBackOff"},
                                }
                            }
                        ],
                    },
                }
            ]
        }
        out = normalize_pod_list("get_pods", payload)
        self.assertEqual(out["results"][0]["status"], "CrashLoopBackOff")


if __name__ == "__main__":
    unittest.main()
