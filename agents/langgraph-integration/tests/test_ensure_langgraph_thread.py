"""ensure_langgraph_thread: create thread before runs.stream."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


class TestEnsureLanggraphThread(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        from clients.langgraph_client import ensure_langgraph_thread

        client = mock.MagicMock()
        self.assertIsNone(ensure_langgraph_thread(client, None))
        client.threads.get.assert_not_called()
        client.threads.create.assert_not_called()

    def test_existing_thread_skips_create(self) -> None:
        from clients.langgraph_client import ensure_langgraph_thread

        client = mock.MagicMock()
        tid = "03fd5d72-94dc-57d3-a427-da0a784449d4"
        out = ensure_langgraph_thread(client, tid)
        self.assertEqual(out, tid)
        client.threads.get.assert_called_once_with(tid)
        client.threads.create.assert_not_called()

    def test_missing_thread_creates(self) -> None:
        from clients.langgraph_client import ensure_langgraph_thread

        client = mock.MagicMock()
        client.threads.get.side_effect = Exception("NotFoundError: thread")
        tid = "03fd5d72-94dc-57d3-a427-da0a784449d4"
        client.threads.create.return_value = {"thread_id": tid}
        out = ensure_langgraph_thread(client, tid)
        self.assertEqual(out, tid)
        client.threads.create.assert_called_once()
        self.assertEqual(client.threads.create.call_args.kwargs["thread_id"], tid)

    def test_stream_calls_ensure(self) -> None:
        from clients.langgraph_client import stream_sentinel_run

        client = mock.MagicMock()
        client.threads.get.return_value = {"thread_id": "abc"}
        client.runs.stream.return_value = iter([])
        with mock.patch(
            "clients.langgraph_client.ensure_langgraph_thread",
            return_value="abc",
        ) as ensure:
            list(
                stream_sentinel_run(
                    {"entities": []},
                    client=client,
                    thread_id="abc",
                )
            )
        ensure.assert_called_once_with(client, "abc")
        client.runs.stream.assert_called_once()


if __name__ == "__main__":
    unittest.main()
