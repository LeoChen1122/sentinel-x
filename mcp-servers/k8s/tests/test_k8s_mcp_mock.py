"""Step 7 style integration: tools + server with mocked Kubernetes client (no Cursor, no real cluster)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _fake_pod_payload() -> dict:
    return {
        "items": [
            {
                "metadata": {"name": "payment-1", "namespace": "sandbox"},
                "status": {"phase": "Running"},
            },
            {
                "metadata": {"name": "order-2", "namespace": "sandbox"},
                "status": {"phase": "Pending"},
            },
        ]
    }


def _fake_event_payload() -> dict:
    return {
        "items": [
            {
                "metadata": {"namespace": "sandbox", "creationTimestamp": "2024-01-01T00:00:00Z"},
                "type": "Normal",
                "reason": "Scheduled",
                "message": "ok",
                "involvedObject": {"kind": "Pod", "name": "p1"},
                "count": 1,
                "lastTimestamp": "2024-06-15T12:00:00Z",
            },
            {
                "metadata": {"namespace": "sandbox", "creationTimestamp": "2024-01-01T00:00:00Z"},
                "type": "Warning",
                "reason": "Fail",
                "message": "old",
                "involvedObject": {"kind": "Pod", "name": "p2"},
                "count": 2,
                "lastTimestamp": "2024-01-01T00:00:00Z",
            },
        ]
    }


def _make_client_cm(list_pods=None, list_events=None):
    inner = mock.MagicMock()
    if list_pods is not None:
        inner.list_pods.return_value = list_pods
    if list_events is not None:
        inner.list_events.return_value = list_events
    cm = mock.MagicMock()
    cm.__enter__.return_value = inner
    cm.__exit__.return_value = None
    return cm, inner


class TestK8sGetPodsMock(unittest.TestCase):
    @mock.patch("tools.k8s_get_pods.KubernetesClient")
    def test_tool_returns_normalized(self, mock_cls: mock.MagicMock) -> None:
        from tools import k8s_get_pods as mod

        cm, inner = _make_client_cm(list_pods=_fake_pod_payload())
        mock_cls.return_value = cm

        out = mod.k8s_get_pods("sandbox", limit=1)
        self.assertEqual(out["query"], "get_pods")
        self.assertEqual(len(out["results"]), 1)
        self.assertEqual(out["results"][0]["name"], "payment-1")
        inner.list_pods.assert_called_once_with("sandbox")
        mock_cls.assert_called_once()


class TestK8sGetEventsMock(unittest.TestCase):
    @mock.patch("tools.k8s_get_events.KubernetesClient")
    def test_tool_passes_api_args_and_since_filter(self, mock_cls: mock.MagicMock) -> None:
        from tools import k8s_get_events as mod

        cm, inner = _make_client_cm(list_events=_fake_event_payload())
        mock_cls.return_value = cm

        out = mod.k8s_get_events(
            "sandbox",
            pod_name="p1",
            limit=10,
            since_time="2024-06-01T00:00:00Z",
            api_limit=500,
            field_selector="type=Normal",
        )
        inner.list_events.assert_called_once_with(
            "sandbox",
            "p1",
            field_selector="type=Normal",
            limit=500,
        )
        self.assertEqual(out["query"], "get_events")
        names = [r.get("object_name") for r in out["results"]]
        self.assertIn("p1", names)
        self.assertNotIn("p2", names)


class TestServerWrappersMock(unittest.TestCase):
    @mock.patch("tools.k8s_get_events.KubernetesClient")
    @mock.patch("tools.k8s_get_pods.KubernetesClient")
    def test_server_delegates_to_tools(
        self,
        mock_pods_cls: mock.MagicMock,
        mock_events_cls: mock.MagicMock,
    ) -> None:
        import server

        cm_p, inner_p = _make_client_cm(list_pods=_fake_pod_payload())
        mock_pods_cls.return_value = cm_p
        cm_e, inner_e = _make_client_cm(list_events=_fake_event_payload())
        mock_events_cls.return_value = cm_e

        pods_out = server.k8s_get_pods("sandbox", None)
        self.assertEqual(pods_out["query"], "get_pods")
        self.assertEqual(len(pods_out["results"]), 2)

        events_out = server.k8s_get_events(
            "sandbox",
            None,
            None,
            since_time=None,
            api_limit=None,
            field_selector=None,
        )
        self.assertEqual(events_out["query"], "get_events")
        self.assertEqual(len(events_out["results"]), 2)


if __name__ == "__main__":
    unittest.main()
