from __future__ import annotations

import os
from typing import Any

from clients.prometheus import PrometheusClient
from models.responses import NormalizedQueryResponse
from tools.prometheus_env import verify_ssl_from_env
from utils.normalize import normalize_query_result

PROM_QUERY_TOOL_META: dict[str, Any] = {
    "name": "prom_query",
    "readonly": True,
    "risk": "low",
    "category": "metrics",
}


def prom_query(
    promql: str,
    time: str | float | int | None = None,
) -> dict[str, Any]:
    """Run an instant PromQL query and return a normalized ``dict`` for agents."""
    if not promql or not promql.strip():
        raise ValueError("promql must be a non-empty string")

    base_url = os.getenv("PROMETHEUS_BASE_URL", "http://127.0.0.1:9090").strip()
    token = os.getenv("PROMETHEUS_BEARER_TOKEN")
    token = token.strip() if token else None
    verify = verify_ssl_from_env()

    with PrometheusClient(base_url, token=token, verify=verify) as client:
        payload = client.query(promql.strip(), time=time)

    normalized: NormalizedQueryResponse = normalize_query_result(promql.strip(), payload)
    return dict(normalized)
