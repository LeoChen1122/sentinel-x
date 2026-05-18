"""Smoke tests for LangGraph SDK client wrapper (step 1)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


class TestGetLanggraphSyncClientFactory(unittest.TestCase):
    def test_passes_url_timeout_and_optional_api_key(self) -> None:
        from clients import langgraph_client as mod

        with mock.patch.dict(
            os.environ,
            {
                "LANGGRAPH_API_URL": "https://example.test/api",
                "LANGGRAPH_REQUEST_TIMEOUT": "45",
                "LANGGRAPH_API_KEY": "secret",
            },
            clear=False,
        ):
            fake = object()
            with mock.patch.object(mod, "get_sync_client", return_value=fake) as m:
                c = mod.get_langgraph_sync_client()
            self.assertIs(c, fake)
            m.assert_called_once()
            kwargs = m.call_args.kwargs
            self.assertEqual(kwargs["url"], "https://example.test/api")
            self.assertEqual(kwargs["timeout"], 45.0)
            self.assertEqual(kwargs["api_key"], "secret")

    def test_raises_without_url(self) -> None:
        from clients import langgraph_client as mod

        with mock.patch.dict(
            os.environ,
            {"LANGGRAPH_API_URL": "", "LANGGRAPH_URL": ""},
            clear=False,
        ):
            with self.assertRaises(ValueError) as ctx:
                mod.get_langgraph_sync_client()
        self.assertIn("LANGGRAPH_API_URL", str(ctx.exception))

    def test_omits_api_key_when_not_set(self) -> None:
        from clients import langgraph_client as mod

        with mock.patch.dict(
            os.environ,
            {
                "LANGGRAPH_URL": "http://localhost:2024",
                "LANGGRAPH_API_URL": "",
                "LANGGRAPH_API_KEY": "",
                "LANGSMITH_API_KEY": "",
                "LANGCHAIN_API_KEY": "",
            },
            clear=False,
        ):
            fake = object()
            with mock.patch.object(mod, "get_sync_client", return_value=fake) as m:
                mod.get_langgraph_sync_client()
            kwargs = m.call_args.kwargs
            self.assertNotIn("api_key", kwargs)


class TestVerifyLanggraphConnectionLive(unittest.TestCase):
    @unittest.skipUnless(
        bool(
            (os.environ.get("LANGGRAPH_API_URL") or os.environ.get("LANGGRAPH_URL") or "")
            .strip()
        ),
        "Set LANGGRAPH_API_URL or LANGGRAPH_URL to run live connectivity test",
    )
    def test_live_search(self) -> None:
        from clients.langgraph_client import (
            get_langgraph_sync_client,
            verify_langgraph_connection,
        )

        client = get_langgraph_sync_client()
        out = verify_langgraph_connection(client)
        self.assertTrue(out.get("ok"))
        self.assertTrue(out.get("assistants_checked"))


class TestVerifyLanggraphConnectionMock(unittest.TestCase):
    def test_calls_assistants_search(self) -> None:
        from clients.langgraph_client import verify_langgraph_connection

        client = mock.MagicMock()
        out = verify_langgraph_connection(client)
        client.assistants.search.assert_called_once_with(limit=1)
        self.assertEqual(out, {"ok": True, "assistants_checked": True})


if __name__ == "__main__":
    unittest.main()
