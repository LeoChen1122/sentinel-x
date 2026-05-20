"""Phase F: optional live LangGraph inspect E2E (requires langgraph dev)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from testing.multicluster_fixtures import CLUSTER_DEV, dual_cluster_rich_batch  # noqa: E402


class TestInspectOutputsFromStream(unittest.TestCase):
    def test_get_inspect_outputs_from_stream(self) -> None:
        from clients.langgraph_client import get_inspect_outputs_from_stream

        chunks = [
            {"payload": {"entities": []}},
            {
                "payload": {
                    "gather": {"cluster_id": CLUSTER_DEV},
                    "diagnosis": {"issues": ["CrashLoop"]},
                    "execution": {"dry_run": True},
                    "narrative": {"narrative_source": "template"},
                }
            },
        ]
        out = get_inspect_outputs_from_stream(chunks)
        self.assertEqual(out["diagnosis"]["issues"], ["CrashLoop"])
        self.assertTrue(out["execution"]["dry_run"])
        self.assertEqual(out["narrative"]["narrative_source"], "template")
        self.assertEqual(out["gather"]["cluster_id"], CLUSTER_DEV)


class TestLangGraphInspectLive(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("LANGGRAPH_RUN_LIVE", "").strip().lower() in ("1", "true", "yes"),
        "Set LANGGRAPH_RUN_LIVE=1 and start langgraph dev",
    )
    def test_live_inspect_crash_pod(self) -> None:
        from clients.langgraph_client import (
            get_inspect_outputs_from_stream,
            get_langgraph_client,
            stream_sentinel_run,
        )

        payload = dual_cluster_rich_batch().to_dict(wire_only=True)
        payload["inspect"] = {
            "cluster_id": CLUSTER_DEV,
            "namespace": "default",
            "pod_name": "crash-pod",
            "dry_run": True,
        }
        client = get_langgraph_client()
        chunks = list(stream_sentinel_run(payload, client=client))
        outputs = get_inspect_outputs_from_stream(chunks)
        self.assertIn("CrashLoop", (outputs.get("diagnosis") or {}).get("issues", []))
        execution = outputs.get("execution") or {}
        self.assertTrue(execution.get("dry_run"))
        self.assertEqual(execution.get("execution_source"), "registry_v1")


if __name__ == "__main__":
    unittest.main()
