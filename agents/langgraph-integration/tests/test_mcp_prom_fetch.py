"""Phase 1c: MCP Prometheus fetch via docker / snapshot."""

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


def _vector_result(ns: str, pod: str, value: str) -> dict:
    return {
        "metric": {"pod": pod, "namespace": ns},
        "value": [1710000000.0, value],
    }


class TestMcpPromFetch(unittest.TestCase):
    def test_load_snapshot(self) -> None:
        from clients.mcp_prom import load_prom_mcp_snapshot

        snap = {
            "cpu": {
                "query": "cpu",
                "result_type": "vector",
                "results": [_vector_result("default", "a", "0.5")],
            },
            "memory": {
                "query": "mem",
                "result_type": "vector",
                "results": [_vector_result("default", "a", "1024")],
            },
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(snap, f)
            path = f.name
        try:
            loaded = load_prom_mcp_snapshot(path)
            self.assertEqual(loaded["cpu"]["query"], "cpu")
            self.assertEqual(len(loaded["cpu"]["results"]), 1)
            self.assertEqual(loaded["memory"]["results"][0]["metric"]["pod"], "a")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_fetch_via_docker(self) -> None:
        from clients.mcp_prom import fetch_prom_mcp_via_docker

        payload = {
            "cpu": {
                "query": "cpu",
                "result_type": "vector",
                "results": [_vector_result("kube-system", "coredns", "0.01")],
            },
            "memory": {
                "query": "mem",
                "result_type": "vector",
                "results": [_vector_result("kube-system", "coredns", "50000000")],
            },
        }
        proc = mock.Mock(returncode=0, stdout=json.dumps(payload), stderr="")
        with mock.patch("clients.mcp_prom.subprocess.run", return_value=proc) as run:
            snap = fetch_prom_mcp_via_docker("mcp-prometheus")
        self.assertEqual(snap["cpu"]["results"][0]["metric"]["pod"], "coredns")
        run.assert_called_once()
        args = run.call_args[0][0]
        self.assertEqual(args[0], "docker")
        self.assertIn("mcp-prometheus", args)

    def test_attach_cluster_id(self) -> None:
        from clients.mcp_prom import attach_cluster_id

        snap = attach_cluster_id(
            {
                "cpu": {"query": "cpu", "results": []},
                "memory": {"query": "mem", "results": []},
            },
            "k3s-prod",
        )
        self.assertEqual(snap["cpu"]["cluster_id"], "k3s-prod")
        self.assertEqual(snap["memory"]["cluster_id"], "k3s-prod")


class TestAdapterMetrics(unittest.TestCase):
    def test_build_pod_metrics_map(self) -> None:
        from adapter.metrics import build_pod_metrics_map

        cpu = {
            "query": "cpu",
            "results": [
                _vector_result("default", "p1", "0.25"),
                _vector_result("other", "p2", "1.0"),
            ],
        }
        mem = {
            "query": "mem",
            "results": [_vector_result("default", "p1", "2048")],
        }
        m = build_pod_metrics_map(cpu, mem, namespace="default")
        self.assertEqual(m[("default", "p1")]["cpu_cores"], 0.25)
        self.assertEqual(m[("default", "p1")]["memory_bytes"], 2048)
        self.assertNotIn(("other", "p2"), m)

    def test_pods_with_metrics_to_batch(self) -> None:
        from adapter.metrics import pods_with_metrics_to_batch

        pods = {
            "query": "get_pods",
            "results": [{"name": "p1", "status": "Running"}],
            "cluster_id": "local",
        }
        cpu = {
            "query": "cpu",
            "results": [_vector_result("default", "p1", "0.5")],
        }
        mem = {
            "query": "mem",
            "results": [_vector_result("default", "p1", "4096")],
        }
        batch = pods_with_metrics_to_batch(pods, cpu, mem, "default", cluster_id="local")
        self.assertEqual(len(batch.entities), 1)
        props = batch.entities[0].properties
        self.assertEqual(props["cpu_cores"], 0.5)
        self.assertEqual(props["memory_bytes"], 4096)


class TestPromQueryOps(unittest.TestCase):
    def test_top_pods_by_cpu(self) -> None:
        from adapter.metrics import pods_with_metrics_to_batch
        from query import run_query

        pods = {
            "query": "get_pods",
            "results": [
                {"name": "low", "status": "Running"},
                {"name": "high", "status": "Running"},
            ],
            "cluster_id": "local",
        }
        cpu = {
            "query": "cpu",
            "results": [
                _vector_result("default", "low", "0.1"),
                _vector_result("default", "high", "2.5"),
            ],
        }
        mem = {"query": "mem", "results": []}
        batch = pods_with_metrics_to_batch(pods, cpu, mem, "default", cluster_id="local")
        payload = batch.to_dict(wire_only=True)
        out = run_query(payload, "top_pods_by_cpu", cluster_id="local", limit=5)
        self.assertEqual(out["count"], 2)
        self.assertEqual(out["pods"][0]["name"], "high")
        self.assertEqual(out["pods"][0]["cpu_cores"], 2.5)

    def test_pod_metrics(self) -> None:
        from adapter.metrics import pods_with_metrics_to_batch
        from query import run_query

        pods = {
            "query": "get_pods",
            "results": [{"name": "p1", "status": "Running"}],
            "cluster_id": "local",
        }
        cpu = {"query": "cpu", "results": [_vector_result("default", "p1", "0.75")]}
        mem = {"query": "mem", "results": [_vector_result("default", "p1", "8192")]}
        batch = pods_with_metrics_to_batch(pods, cpu, mem, "default", cluster_id="local")
        out = run_query(
            batch.to_dict(wire_only=True),
            "pod_metrics",
            cluster_id="local",
            namespace="default",
            name="p1",
        )
        self.assertTrue(out["found"])
        self.assertEqual(out["cpu_cores"], 0.75)
        self.assertEqual(out["memory_bytes"], 8192)


if __name__ == "__main__":
    unittest.main()
