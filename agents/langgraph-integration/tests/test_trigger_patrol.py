"""W7 patrol selection tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from trigger.config import PatrolConfig
from trigger.patrol import (
    PodCandidate,
    find_inspect_candidates,
    find_inspect_candidates_multi,
    load_patrol_state,
    save_patrol_state,
    select_pod_to_inspect,
)

_CFG = PatrolConfig(
    enabled=True,
    cooldown_sec=3600,
    state_path=Path("/tmp/x"),
    default_dry_run=True,
    namespaces=("kube-system", "sentinel-sandbox"),
)


class TestPatrol(unittest.TestCase):
    def test_classify_and_select_crashloop_first(self) -> None:
        candidates = [
            PodCandidate(
                cluster_id="c",
                namespace="ns",
                pod_name="warn-pod",
                pod_id="pod:c:ns:warn-pod",
                severity="WarningEvents",
                reason="Warning",
            ),
            PodCandidate(
                cluster_id="c",
                namespace="ns",
                pod_name="crash-pod",
                pod_id="pod:c:ns:crash-pod",
                severity="CrashLoop",
                reason="CrashLoopBackOff",
            ),
        ]
        cfg = _CFG
        picked = select_pod_to_inspect(candidates, {}, cfg=cfg, now=1000.0)
        self.assertIsNotNone(picked)
        assert picked is not None
        self.assertEqual(picked["pod_name"], "crash-pod")

    def test_cooldown_skips_recent(self) -> None:
        candidates = [
            PodCandidate(
                cluster_id="c",
                namespace="ns",
                pod_name="crash-pod",
                pod_id="pod:c:ns:crash-pod",
                severity="CrashLoop",
                reason="CrashLoopBackOff",
            ),
        ]
        cfg = _CFG
        state = {"pod:c:ns:crash-pod": 500.0}
        picked = select_pod_to_inspect(candidates, state, cfg=cfg, now=1000.0)
        self.assertIsNone(picked)

    def test_state_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            save_patrol_state({"pod:1": 123.0}, path)
            loaded = load_patrol_state(path)
            self.assertEqual(loaded["pod:1"], 123.0)

    @mock.patch("trigger.patrol.query_sentinel")
    def test_find_candidates_from_list_pods(self, mock_query) -> None:
        def fake_query(op, **kwargs):
            if op == "list_pods":
                return {
                    "pods": [
                        {
                            "id": "pod:c:ns:ok",
                            "name": "ok",
                            "namespace": "ns",
                            "cluster_id": "c",
                            "status": "Running",
                        },
                        {
                            "id": "pod:c:ns:bad",
                            "name": "bad",
                            "namespace": "ns",
                            "cluster_id": "c",
                            "status": "CrashLoopBackOff",
                        },
                    ],
                }
            if kwargs.get("name") == "bad":
                return {"events": [{"properties": {"reason": "BackOff"}}]}
            return {"events": []}

        mock_query.side_effect = fake_query
        found = find_inspect_candidates(
            thread_id="5ad00ee0-6f4d-5cd6-a021-99469a86e4e1",
            cluster_id="c",
            namespace="ns",
        )
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["pod_name"], "bad")
        self.assertEqual(found[0]["severity"], "CrashLoop")

    @mock.patch("trigger.patrol.query_sentinel")
    def test_find_candidates_multi_namespace(self, mock_query) -> None:
        def fake_query(op, **kwargs):
            if op == "list_pods":
                ns = kwargs.get("namespace")
                if ns == "kube-system":
                    return {"pods": []}
                if ns == "sentinel-sandbox":
                    return {
                        "pods": [
                            {
                                "id": "pod:c:sentinel-sandbox:crash-demo",
                                "name": "crash-demo",
                                "namespace": "sentinel-sandbox",
                                "cluster_id": "c",
                                "status": "CrashLoopBackOff",
                            },
                        ],
                    }
            return {"events": [{"properties": {"reason": "BackOff"}}]}

        mock_query.side_effect = fake_query
        found = find_inspect_candidates_multi(
            thread_id="tid",
            cluster_id="c",
            namespaces=("kube-system", "sentinel-sandbox"),
        )
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["pod_name"], "crash-demo")

    @mock.patch("trigger.patrol.query_sentinel")
    def test_find_candidates_running_phase_with_backoff_events(self, mock_query) -> None:
        def fake_query(op, **kwargs):
            if op == "list_pods":
                return {
                    "pods": [
                        {
                            "id": "pod:c:ns:bad",
                            "name": "bad",
                            "namespace": "ns",
                            "cluster_id": "c",
                            "status": "Running",
                        },
                    ],
                }
            return {"events": [{"properties": {"reason": "CrashLoopBackOff", "type": "Warning"}}]}

        mock_query.side_effect = fake_query
        found = find_inspect_candidates(
            thread_id="tid",
            cluster_id="c",
            namespace="ns",
        )
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["severity"], "CrashLoop")

    @mock.patch("trigger.patrol.query_sentinel")
    def test_running_healthy_skips_stale_backoff_events(self, mock_query) -> None:
        def fake_query(op, **kwargs):
            if op == "list_pods":
                return {
                    "pods": [
                        {
                            "id": "pod:c:ns:ok",
                            "name": "ok",
                            "namespace": "ns",
                            "cluster_id": "c",
                            "status": "Running",
                        },
                        {
                            "id": "pod:c:ns:done",
                            "name": "done",
                            "namespace": "ns",
                            "cluster_id": "c",
                            "status": "Succeeded",
                        },
                    ],
                }
            return {"events": [{"properties": {"reason": "BackOff", "type": "Warning"}}]}

        mock_query.side_effect = fake_query
        found = find_inspect_candidates(
            thread_id="tid",
            cluster_id="c",
            namespace="ns",
        )
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
