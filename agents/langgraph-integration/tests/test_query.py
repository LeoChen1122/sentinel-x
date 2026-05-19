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

from adapter.inspections import inspection_mcp_to_batch  # noqa: E402
from adapter.k8s import pods_events_to_batch  # noqa: E402
from testing.multicluster_fixtures import (  # noqa: E402
    CLUSTER_LOCAL,
    inspection_mcp,
    pods_mcp,
    events_mcp,
)
from utils.graph_merge import merge_graph_batches  # noqa: E402


def _fixture_payload() -> dict:
    ns = "default"
    cid = CLUSTER_LOCAL
    pe = pods_events_to_batch(
        pods_mcp(cid, namespace=ns, pod_name="payment-1"),
        events_mcp(cid, namespace=ns, pod_name="payment-1"),
        ns,
    )
    insp = inspection_mcp_to_batch(inspection_mcp(cid, namespace=ns, pod_name="payment-1"))
    return merge_graph_batches(pe, insp).to_dict(wire_only=True)


class TestRunQuery(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = _fixture_payload()
        self.cid = CLUSTER_LOCAL
        self.ns = "default"
        self.pname = "payment-1"

    def test_list_pods(self) -> None:
        from query import run_query

        out = run_query(self.payload, "list_pods", cluster_id=self.cid)
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["pods"][0]["name"], self.pname)

    def test_list_pods_namespace_filter(self) -> None:
        from query import run_query

        out = run_query(
            self.payload, "list_pods", cluster_id=self.cid, namespace="other"
        )
        self.assertEqual(out["count"], 0)

    def test_pod_status_found(self) -> None:
        from query import run_query

        out = run_query(
            self.payload,
            "pod_status",
            cluster_id=self.cid,
            namespace=self.ns,
            name=self.pname,
        )
        self.assertTrue(out["found"])

    def test_pod_status_missing(self) -> None:
        from query import run_query

        out = run_query(
            self.payload,
            "pod_status",
            cluster_id=self.cid,
            namespace=self.ns,
            name="missing",
        )
        self.assertFalse(out["found"])

    def test_events_for_pod(self) -> None:
        from query import run_query

        out = run_query(
            self.payload,
            "events_for_pod",
            cluster_id=self.cid,
            namespace=self.ns,
            name=self.pname,
        )
        self.assertEqual(out["count"], 1)

    def test_inspections_summary(self) -> None:
        from query import run_query

        out = run_query(self.payload, "inspections_summary", cluster_id=self.cid)
        self.assertEqual(out["count"], 1)


class TestFormatQueryResult(unittest.TestCase):
    def test_non_empty_output(self) -> None:
        from query import format_query_result, run_query

        result = run_query(_fixture_payload(), "list_pods", cluster_id=CLUSTER_LOCAL)
        text = format_query_result(result)
        self.assertIn("payment-1", text)


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
        client.runs.stream.assert_called_once()

    def test_get_payload_from_stream(self) -> None:
        from clients.langgraph_client import get_payload_from_stream

        chunks = [
            SimpleNamespace(
                data={
                    "payload": {
                        "query_result": {"op": "list_pods", "count": 1},
                    }
                }
            ),
        ]
        payload = get_payload_from_stream(chunks)
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
                cluster_id=CLUSTER_LOCAL,
                namespace="default",
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

        from clients.langgraph_client import (
            get_langgraph_client,
            query_sentinel,
            stream_sentinel_run,
        )

        thread_id = str(uuid.uuid4())
        client = get_langgraph_client()
        cid = CLUSTER_LOCAL
        batch = pods_events_to_batch(
            pods_mcp(cid),
            events_mcp(cid),
            "default",
        )
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
            cluster_id=cid,
            namespace="default",
        )
        self.assertGreaterEqual(out.get("count", 0), 1)


if __name__ == "__main__":
    unittest.main()
