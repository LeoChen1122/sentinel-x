"""Step 6: query module and client helpers (no live LangGraph by default)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from models.entities import EntityType, RelationType  # noqa: E402
from models.ids import event_id, inspection_id, pod_id  # noqa: E402


def _fixture_payload() -> dict:
    ns = "sandbox"
    pname = "payment-1"
    pid = pod_id(ns, pname)
    eid = event_id(
        namespace=ns,
        object_kind="Pod",
        object_name=pname,
        reason="Failed",
        last_timestamp="2024-06-15T12:00:00Z",
    )
    iid = inspection_id("2024-06-15T12:00:00Z", "worker-01")
    return {
        "entities": [
            {
                "id": pid,
                "type": EntityType.POD.value,
                "properties": {"namespace": ns, "name": pname, "status": "Running"},
            },
            {
                "id": eid,
                "type": EntityType.EVENT.value,
                "properties": {
                    "type": "Warning",
                    "reason": "Failed",
                    "message": "crash",
                    "last_timestamp": "2024-06-15T12:00:00Z",
                },
            },
            {
                "id": iid,
                "type": EntityType.INSPECTION.value,
                "properties": {
                    "timestamp": "2024-06-15T12:00:00Z",
                    "node": "worker-01",
                    "status": "ok",
                    "summary": "check",
                },
            },
        ],
        "edges": [
            {
                "source_id": pid,
                "target_id": eid,
                "relation": RelationType.HAS_EVENT.value,
            },
            {
                "source_id": iid,
                "target_id": pid,
                "relation": RelationType.INSPECTS_POD.value,
            },
        ],
    }


class TestRunQuery(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = _fixture_payload()

    def test_list_pods(self) -> None:
        from query import run_query

        out = run_query(self.payload, "list_pods")
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["pods"][0]["name"], "payment-1")

    def test_list_pods_namespace_filter(self) -> None:
        from query import run_query

        out = run_query(self.payload, "list_pods", namespace="other")
        self.assertEqual(out["count"], 0)

    def test_pod_status_found(self) -> None:
        from query import run_query

        out = run_query(
            self.payload, "pod_status", namespace="sandbox", name="payment-1"
        )
        self.assertTrue(out["found"])
        self.assertEqual(out["properties"]["status"], "Running")

    def test_pod_status_missing(self) -> None:
        from query import run_query

        out = run_query(
            self.payload, "pod_status", namespace="sandbox", name="missing"
        )
        self.assertFalse(out["found"])

    def test_events_for_pod(self) -> None:
        from query import run_query

        out = run_query(
            self.payload, "events_for_pod", namespace="sandbox", name="payment-1"
        )
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["events"][0]["reason"], "Failed")

    def test_inspections_summary(self) -> None:
        from query import run_query

        out = run_query(self.payload, "inspections_summary")
        self.assertEqual(out["count"], 1)
        self.assertEqual(len(out["inspections"][0]["linked_pods"]), 1)


class TestFormatQueryResult(unittest.TestCase):
    def test_non_empty_output(self) -> None:
        from query import format_query_result, run_query

        result = run_query(_fixture_payload(), "list_pods")
        text = format_query_result(result)
        self.assertIn("payment-1", text)
        self.assertGreater(len(text.strip()), 0)


class TestGraphViewMerge(unittest.TestCase):
    def test_merge_dedupes_edges(self) -> None:
        from query.graph_view import GraphView

        p = _fixture_payload()
        view = GraphView.from_payload(p)
        view.merge_payload(p)
        self.assertEqual(len(view.edges), len(p["edges"]))


class TestQueryClientHelpers(unittest.TestCase):
    def test_stream_passes_thread_id(self) -> None:
        from clients.langgraph_client import stream_sentinel_run

        client = mock.MagicMock()
        client.runs.stream.return_value = iter([])
        list(
            stream_sentinel_run(
                {"query": {"op": "list_pods"}},
                client=client,
                thread_id="thread-abc",
            )
        )
        client.runs.stream.assert_called_once_with(
            "thread-abc",
            "sentinel",
            input={"payload": {"query": {"op": "list_pods"}}},
            stream_mode="values",
        )

    def test_get_payload_from_stream(self) -> None:
        from clients.langgraph_client import get_payload_from_stream

        chunks = [
            SimpleNamespace(data={"payload": {"entities": []}}),
            SimpleNamespace(
                data={
                    "payload": {
                        "entities": [{"id": "pod:x/y"}],
                        "query_result": {"op": "list_pods", "count": 1},
                    }
                }
            ),
        ]
        payload = get_payload_from_stream(chunks)
        self.assertIn("query_result", payload)
        self.assertEqual(payload["query_result"]["op"], "list_pods")

    def test_query_sentinel_from_fake_stream(self) -> None:
        from clients import langgraph_client as mod

        fake_chunks = [
            SimpleNamespace(
                data={
                    "payload": {
                        "query_result": {
                            "op": "events_for_pod",
                            "count": 1,
                            "events": [{"reason": "Failed"}],
                        }
                    }
                }
            )
        ]
        with mock.patch.object(mod, "stream_sentinel_run", return_value=iter(fake_chunks)):
            out = mod.query_sentinel(
                "events_for_pod",
                thread_id="t1",
                namespace="sandbox",
                name="payment-1",
                client=object(),
            )
        self.assertEqual(out["count"], 1)


class TestQuerySentinelLive(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("LANGGRAPH_RUN_LIVE", "").strip().lower() in ("1", "true", "yes"),
        "Set LANGGRAPH_RUN_LIVE=1 and start langgraph dev",
    )
    def test_query_sentinel_live(self) -> None:
        import uuid

        from adapter import pods_events_to_batch
        from clients.langgraph_client import (
            get_langgraph_client,
            query_sentinel,
            stream_sentinel_run,
        )

        thread_id = str(uuid.uuid4())
        client = get_langgraph_client()
        pods_mcp = {
            "query": "get_pods",
            "results": [{"name": "live-pod", "status": "Running"}],
        }
        events_mcp = {"query": "get_events", "results": []}
        batch = pods_events_to_batch(pods_mcp, events_mcp, "default")
        list(
            stream_sentinel_run(
                batch.to_dict(wire_only=True),
                thread_id=thread_id,
                client=client,
            )
        )
        out = query_sentinel(
            "list_pods",
            thread_id=thread_id,
            client=client,
            namespace="default",
        )
        self.assertGreaterEqual(out.get("count", 0), 1)


if __name__ == "__main__":
    unittest.main()
