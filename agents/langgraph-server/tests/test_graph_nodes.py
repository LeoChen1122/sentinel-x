"""Smoke tests for langgraph-server graph nodes (W4-4)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SERVER_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SERVER_SRC) not in sys.path:
    sys.path.insert(0, str(_SERVER_SRC))

from graph import ingest, query  # noqa: E402


def _sample_pod_entity(
    *,
    cluster_id: str = "local",
    namespace: str = "default",
    name: str = "app-1",
) -> dict:
    return {
        "id": f"pod:{cluster_id}:{namespace}:{name}",
        "type": "Pod",
        "properties": {
            "cluster_id": cluster_id,
            "namespace": namespace,
            "name": name,
            "status": "Running",
            "cpu_cores": 0.05,
            "memory_bytes": 128_000_000,
        },
    }


class TestGraphNodes(unittest.TestCase):
    def test_ingest_initializes_empty_graph(self) -> None:
        out = ingest({"payload": {}})
        payload = out["payload"]
        self.assertIsInstance(payload.get("entities"), list)
        self.assertIsInstance(payload.get("edges"), list)

    def test_ingest_merges_entities(self) -> None:
        ent = _sample_pod_entity()
        out = ingest({"payload": {"entities": [ent], "edges": []}})
        self.assertEqual(len(out["payload"]["entities"]), 1)

    def test_query_node_list_pods(self) -> None:
        ent = _sample_pod_entity()
        state = ingest({"payload": {"entities": [ent], "edges": []}})
        state["payload"]["query"] = {
            "op": "list_pods",
            "cluster_id": "local",
            "namespace": "default",
        }
        out = query(state)
        qr = out["payload"]["query_result"]
        self.assertIsInstance(qr, dict)
        self.assertEqual(qr.get("op"), "list_pods")
        self.assertEqual(qr.get("count"), 1)
        self.assertEqual(qr["pods"][0]["name"], "app-1")

    def test_query_node_top_pods_by_cpu(self) -> None:
        pods = [
            _sample_pod_entity(name="low", cluster_id="local"),
            _sample_pod_entity(name="high", cluster_id="local"),
        ]
        pods[0]["properties"]["cpu_cores"] = 0.01
        pods[1]["properties"]["cpu_cores"] = 0.99
        state = ingest({"payload": {"entities": pods, "edges": []}})
        state["payload"]["query"] = {
            "op": "top_pods_by_cpu",
            "cluster_id": "local",
            "namespace": "default",
            "limit": 1,
        }
        out = query(state)
        qr = out["payload"]["query_result"]
        self.assertEqual(qr["count"], 1)
        self.assertEqual(qr["pods"][0]["name"], "high")


if __name__ == "__main__":
    unittest.main()
