"""Step 8: Sentinel-X connect to local LangGraph (mock + optional live)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


class TestStreamSentinelRunMock(unittest.TestCase):
    def test_stream_calls_runs_with_sentinel_graph(self) -> None:
        from clients.langgraph_client import stream_sentinel_run

        client = mock.MagicMock()
        client.runs.stream.return_value = iter([])

        payload = {"source": "mcp", "results": [{"name": "p", "status": "Running"}]}
        list(stream_sentinel_run(payload, client=client))

        client.runs.stream.assert_called_once_with(
            None,
            "sentinel",
            input={"payload": payload},
            stream_mode="values",
        )

    def test_stream_with_thread_id(self) -> None:
        from clients.langgraph_client import stream_sentinel_run

        client = mock.MagicMock()
        client.runs.stream.return_value = iter([])
        list(stream_sentinel_run({"entities": []}, client=client, thread_id="tid-1"))
        client.runs.stream.assert_called_once_with(
            "tid-1",
            "sentinel",
            input={"payload": {"entities": []}},
            stream_mode="values",
        )

    def test_get_langgraph_client_alias(self) -> None:
        from clients import langgraph_client as mod

        with mock.patch.dict(
            os.environ,
            {"LANGGRAPH_API_URL": "http://127.0.0.1:2024"},
            clear=False,
        ):
            fake = object()
            with mock.patch.object(mod, "get_sync_client", return_value=fake):
                self.assertIs(mod.get_langgraph_client(), fake)


class TestStreamSentinelRunLive(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("LANGGRAPH_RUN_LIVE", "").strip().lower() in ("1", "true", "yes"),
        "Set LANGGRAPH_RUN_LIVE=1 and start langgraph dev to run live stream test",
    )
    def test_live_stream(self) -> None:
        from clients.langgraph_client import get_langgraph_client, stream_sentinel_run

        client = get_langgraph_client()
        chunks = list(
            stream_sentinel_run({"source": "mcp", "results": []}, client=client)
        )
        self.assertGreater(len(chunks), 0)


if __name__ == "__main__":
    unittest.main()
