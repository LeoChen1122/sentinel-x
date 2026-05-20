"""LangGraph thread_id: logical key vs UUID5 mapping."""

from __future__ import annotations

import sys
import unittest
import uuid
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from models.scope import (  # noqa: E402
    SENTINEL_LANGGRAPH_THREAD_NS,
    langgraph_thread_id,
    resolve_langgraph_thread_id,
    sync_thread_id,
)


class TestScopeThreadId(unittest.TestCase):
    def test_sync_thread_id_logical(self) -> None:
        self.assertEqual(sync_thread_id("dev-cluster"), "default:dev-cluster")
        self.assertEqual(
            sync_thread_id("prod-cluster", "team-alpha"),
            "team-alpha:prod-cluster",
        )

    def test_langgraph_thread_id_is_valid_uuid(self) -> None:
        tid = langgraph_thread_id("dev-cluster")
        parsed = uuid.UUID(tid)
        self.assertEqual(parsed.version, 5)
        self.assertEqual(parsed, uuid.uuid5(SENTINEL_LANGGRAPH_THREAD_NS, "default:dev-cluster"))

    def test_langgraph_thread_id_stable(self) -> None:
        a = langgraph_thread_id("dev-cluster", "team-alpha")
        b = langgraph_thread_id("dev-cluster", "team-alpha")
        self.assertEqual(a, b)
        self.assertNotEqual(a, langgraph_thread_id("prod-cluster", "team-alpha"))

    def test_resolve_passes_through_uuid(self) -> None:
        u = str(uuid.uuid4())
        self.assertEqual(resolve_langgraph_thread_id(thread_id=u), u)

    def test_resolve_maps_arbitrary_label(self) -> None:
        a = resolve_langgraph_thread_id(thread_id="my-thread-1")
        b = resolve_langgraph_thread_id(thread_id="my-thread-1")
        self.assertEqual(a, b)
        uuid.UUID(a)

    def test_resolve_from_cluster(self) -> None:
        self.assertEqual(
            resolve_langgraph_thread_id(cluster_id="dev-cluster"),
            langgraph_thread_id("dev-cluster"),
        )


if __name__ == "__main__":
    unittest.main()
