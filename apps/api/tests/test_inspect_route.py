"""W7 API inspect route tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

_API_SRC = Path(__file__).resolve().parents[1] / "src"
_INTEGRATION_SRC = Path(__file__).resolve().parents[3] / "agents" / "langgraph-integration" / "src"
for p in (_INTEGRATION_SRC, _API_SRC):
    s = str(p.resolve())
    if s not in sys.path:
        sys.path.insert(0, s)

import routes.inspect  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _mock_inspect_result() -> dict:
    return {
        "ok": True,
        "cluster_id": "k3s-prod",
        "namespace": "sentinel-sandbox",
        "pod_name": "crash-demo-abc",
        "issues": ["CrashLoop"],
        "dry_run": True,
        "execution": {"dry_run": True},
    }


class TestInspectRoute(TestCase):
    def setUp(self) -> None:
        os.environ.pop("SENTINEL_API_TOKEN", None)

    @patch.object(routes.inspect, "trigger_inspect", return_value=_mock_inspect_result())
    def test_post_inspect_ok(self, _mock) -> None:
        from main import app

        client = TestClient(app)
        resp = client.post(
            "/v1/inspect",
            json={
                "pod_name": "crash-demo-abc",
                "namespace": "sentinel-sandbox",
                "dry_run": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("issues"), ["CrashLoop"])

    @patch.object(routes.inspect, "trigger_inspect", return_value=_mock_inspect_result())
    def test_post_inspect_requires_bearer_when_token_set(self, _mock) -> None:
        os.environ["SENTINEL_API_TOKEN"] = "secret-token"
        from main import app

        client = TestClient(app)
        resp = client.post(
            "/v1/inspect",
            json={"pod_name": "p1", "namespace": "ns", "dry_run": True},
        )
        self.assertEqual(resp.status_code, 401)

        resp2 = client.post(
            "/v1/inspect",
            json={"pod_name": "p1", "namespace": "ns", "dry_run": True},
            headers={"Authorization": "Bearer wrong"},
        )
        self.assertEqual(resp2.status_code, 403)

        resp3 = client.post(
            "/v1/inspect",
            json={"pod_name": "p1", "namespace": "ns", "dry_run": True},
            headers={"Authorization": "Bearer secret-token"},
        )
        self.assertEqual(resp3.status_code, 200)

    def test_health(self) -> None:
        from main import app

        client = TestClient(app)
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})
