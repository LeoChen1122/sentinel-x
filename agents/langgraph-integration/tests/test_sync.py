"""Step 5: sync incremental, retry, chunking, rate limit (mock LangGraph)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from models.entities import GraphBatch, entity_from_pod_row
from testing.multicluster_fixtures import CLUSTER_LOCAL
from sync.pipeline import push_graph_batch_resilient
from sync.state import (
    SyncState,
    clear_entity_fingerprint_cache,
    entity_fingerprint,
    _fingerprint_from_parts,
)


def _pod_batch(name: str = "p1", status: str = "Running") -> GraphBatch:
    ent = entity_from_pod_row(
        {"name": name, "status": status},
        "default",
        cluster_id=CLUSTER_LOCAL,
    )
    return GraphBatch(entities=[ent])


class TestIncrementalSync(unittest.TestCase):
    def test_skips_unchanged_on_second_push(self) -> None:
        state = SyncState()
        batch = _pod_batch()
        with mock.patch("sync.pipeline.stream_sentinel_run", return_value=iter([])):
            r1 = push_graph_batch_resilient(
                batch, state=state, incremental=True, min_interval_sec=0
            )
        self.assertEqual(r1.chunks_sent, 1)
        with mock.patch("sync.pipeline.stream_sentinel_run") as m:
            r2 = push_graph_batch_resilient(
                batch, state=state, incremental=True, min_interval_sec=0
            )
            m.assert_not_called()
        self.assertEqual(r2.chunks_sent, 0)
        self.assertEqual(r2.skipped_unchanged, 1)

    def test_property_change_triggers_push(self) -> None:
        state = SyncState()
        with mock.patch("sync.pipeline.stream_sentinel_run", return_value=iter([])):
            push_graph_batch_resilient(
                _pod_batch(status="Running"), state=state, min_interval_sec=0
            )
        with mock.patch("sync.pipeline.stream_sentinel_run", return_value=iter([])) as m:
            r = push_graph_batch_resilient(
                _pod_batch(status="Failed"), state=state, min_interval_sec=0
            )
            m.assert_called()
        self.assertGreaterEqual(r.chunks_sent, 1)

    def test_fingerprint_stable(self) -> None:
        ent = entity_from_pod_row(
            {"name": "a", "status": "Running"}, "ns", cluster_id=CLUSTER_LOCAL
        )
        self.assertEqual(
            entity_fingerprint(ent),
            entity_fingerprint(ent),
        )

    def test_fingerprint_lru_cache(self) -> None:
        clear_entity_fingerprint_cache()
        e1 = entity_from_pod_row(
            {"name": "a", "status": "Running"}, "ns", cluster_id=CLUSTER_LOCAL
        )
        e2 = entity_from_pod_row(
            {"name": "a", "status": "Running"}, "ns", cluster_id=CLUSTER_LOCAL
        )
        self.assertEqual(entity_fingerprint(e1), entity_fingerprint(e2))
        info = _fingerprint_from_parts.cache_info()
        self.assertGreater(info.hits, 0)

    def test_filter_empty_batch(self) -> None:
        state = SyncState()
        out, skipped = state.filter_batch(GraphBatch())
        self.assertEqual(out.entities, [])
        self.assertEqual(out.edges, [])
        self.assertEqual(skipped, 0)

    def test_update_empty_batch_noop(self) -> None:
        state = SyncState()
        state.update_from_batch(GraphBatch())
        self.assertEqual(state.fingerprint_for("any"), None)

    def test_save_atomic_replace(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = SyncState(path=path)
            ent = entity_from_pod_row(
                {"name": "x", "status": "Running"},
                "default",
                cluster_id=CLUSTER_LOCAL,
            )
            state.update_from_batch(GraphBatch(entities=[ent]))
            self.assertTrue(path.is_file())
            self.assertFalse(path.with_name(path.name + ".tmp").exists())


class TestRetry(unittest.TestCase):
    def test_retry_then_success(self) -> None:
        try:
            import httpx
        except ImportError:
            self.skipTest("httpx not installed")

        state = SyncState()
        calls = {"n": 0}

        def flaky(*_a, **_k):
            calls["n"] += 1
            if calls["n"] < 3:
                raise httpx.ConnectError("connection refused")
            return iter([])

        with mock.patch("sync.pipeline.stream_sentinel_run", side_effect=flaky):
            with mock.patch("sync.retry.time.sleep"):
                r = push_graph_batch_resilient(
                    _pod_batch(),
                    state=state,
                    incremental=False,
                    min_interval_sec=0,
                )
        self.assertEqual(calls["n"], 3)
        self.assertEqual(r.chunks_sent, 1)


class TestChunkingAndRateLimit(unittest.TestCase):
    def test_multiple_chunks(self) -> None:
        ents = [
            entity_from_pod_row(
                {"name": f"p{i}", "status": "Running"},
                "default",
                cluster_id=CLUSTER_LOCAL,
            )
            for i in range(5)
        ]
        batch = GraphBatch(entities=ents)
        state = SyncState()
        with mock.patch("sync.pipeline.stream_sentinel_run", return_value=iter([])):
            with mock.patch("sync.pipeline.time.sleep") as sleep:
                r = push_graph_batch_resilient(
                    batch,
                    state=state,
                    incremental=False,
                    max_entities=2,
                    max_edges=500,
                    min_interval_sec=0.1,
                )
        self.assertGreater(r.chunks_sent, 1)
        self.assertGreaterEqual(sleep.call_count, 1)

    def test_empty_batch_no_stream(self) -> None:
        with mock.patch("sync.pipeline.stream_sentinel_run") as m:
            r = push_graph_batch_resilient(
                GraphBatch(),
                state=SyncState(),
                incremental=False,
            )
            m.assert_not_called()
        self.assertEqual(r.chunks_sent, 0)


class TestSyncPodsAndEventsResilient(unittest.TestCase):
    def test_event_trigger_path(self) -> None:
        from sync.pipeline import sync_pods_and_events_resilient

        pods = {
            "query": "get_pods",
            "cluster_id": CLUSTER_LOCAL,
            "results": [{"name": "x", "status": "Running"}],
        }
        events = {"query": "get_events", "cluster_id": CLUSTER_LOCAL, "results": []}
        with mock.patch("sync.pipeline.stream_sentinel_run", return_value=iter([])):
            r = sync_pods_and_events_resilient(
                pods,
                events,
                "default",
                state=SyncState(),
                incremental=False,
                min_interval_sec=0,
            )
        self.assertEqual(r.entities_pushed, 1)


if __name__ == "__main__":
    unittest.main()
