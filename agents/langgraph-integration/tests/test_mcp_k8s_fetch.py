"""Phase 1b: MCP K8s fetch via docker / snapshot."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


class TestMcpK8sFetch(unittest.TestCase):
    def test_load_snapshot(self) -> None:
        from clients.mcp_k8s import load_k8s_mcp_snapshot

        snap = {
            "pods": {"query": "get_pods", "results": [{"name": "a", "status": "Running"}]},
            "events": {"query": "get_events", "results": []},
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(snap, f)
            path = f.name
        try:
            pods, events = load_k8s_mcp_snapshot(path)
            self.assertEqual(pods["query"], "get_pods")
            self.assertEqual(len(pods["results"]), 1)
            self.assertEqual(events["results"], [])
        finally:
            Path(path).unlink(missing_ok=True)

    def test_fetch_via_docker(self) -> None:
        from clients.mcp_k8s import fetch_k8s_mcp_via_docker

        payload = {
            "pods": {
                "query": "get_pods",
                "results": [{"name": "p1", "status": "Running"}],
            },
            "events": {"query": "get_events", "results": []},
        }
        proc = mock.Mock(returncode=0, stdout=json.dumps(payload), stderr="")
        with mock.patch("clients.mcp_k8s.subprocess.run", return_value=proc) as run:
            pods, events = fetch_k8s_mcp_via_docker("mcp-k8s", "default")
        self.assertEqual(pods["results"][0]["name"], "p1")
        self.assertEqual(events["results"], [])
        run.assert_called_once()
        args = run.call_args[0][0]
        self.assertEqual(args[0], "docker")
        self.assertIn("mcp-k8s", args)

    def test_attach_cluster_id(self) -> None:
        from clients.mcp_k8s import attach_cluster_id

        pods, events = attach_cluster_id(
            {"query": "get_pods", "results": []},
            {"query": "get_events", "results": []},
            "k3s-prod",
        )
        self.assertEqual(pods["cluster_id"], "k3s-prod")
        self.assertEqual(events["cluster_id"], "k3s-prod")


if __name__ == "__main__":
    unittest.main()
