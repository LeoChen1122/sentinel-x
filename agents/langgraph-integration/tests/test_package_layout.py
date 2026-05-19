"""Step 3: package layout and sync pipeline imports."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


class TestPackageImports(unittest.TestCase):
    def test_subpackages_importable(self) -> None:
        import adapter  # noqa: F401
        import clients  # noqa: F401
        import models  # noqa: F401
        import sync  # noqa: F401
        import utils  # noqa: F401

        self.assertTrue(hasattr(adapter, "pods_to_entities"))
        self.assertTrue(hasattr(models, "GraphBatch"))
        self.assertTrue(hasattr(utils, "chunk_graph_batch"))

    def test_sync_exports(self) -> None:
        from sync import push_graph_batch, sync_pods_and_events
        from sync.pipeline import push_graph_batch as ppb

        self.assertIs(push_graph_batch, ppb)
        self.assertTrue(callable(sync_pods_and_events))


class TestPushGraphBatch(unittest.TestCase):
    def test_push_passes_payload_shape(self) -> None:
        from models.entities import GraphBatch, entity_from_pod_row
        from sync.pipeline import push_graph_batch
        from testing.multicluster_fixtures import CLUSTER_LOCAL

        batch = GraphBatch(
            entities=[
                entity_from_pod_row(
                    {"name": "p1", "status": "Running"},
                    "default",
                    cluster_id=CLUSTER_LOCAL,
                )
            ]
        )
        fake_stream = iter([{"payload": {}}])

        with mock.patch(
            "sync.pipeline.stream_sentinel_run", return_value=fake_stream
        ) as m:
            chunks = list(push_graph_batch(batch, client=mock.Mock(), wire_only=True))

        self.assertEqual(chunks, [{"payload": {}}])
        m.assert_called_once()
        payload = m.call_args[0][0]
        self.assertIn("entities", payload)
        self.assertEqual(len(payload["entities"]), 1)
        self.assertNotIn("kind", payload.get("edges", [{}])[0] if payload.get("edges") else {})


if __name__ == "__main__":
    unittest.main()
