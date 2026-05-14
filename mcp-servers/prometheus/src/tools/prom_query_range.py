from __future__ import annotations

import os
from typing import Any

from clients.prometheus import PrometheusClient
from models.responses import NormalizedQueryResponse
from tools.prometheus_env import verify_ssl_from_env
from utils.normalize import normalize_query_result

PROM_QUERY_RANGE_TOOL_META: dict[str, Any] = {
    "name": "prom_query_range",
    "readonly": True,
    "risk": "low",
    "category": "metrics",
}


def _maybe_float(value: str | float | int) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _validate_time_window(start: str | float | int, end: str | float | int) -> None:
    start_n = _maybe_float(start)
    end_n = _maybe_float(end)
    if start_n is None or end_n is None:
        return
    if end_n <= start_n:
        raise ValueError("end must be greater than start")


def _normalize_step(step: str | int) -> str:
    if isinstance(step, int):
        if step <= 0:
            raise ValueError("step must be a positive integer or duration string")
        return f"{step}s"
    if isinstance(step, str):
        s = step.strip()
        if not s:
            raise ValueError("step must be non-empty")
        if s.isdigit():
            n = int(s)
            if n <= 0:
                raise ValueError("step must be positive")
            return f"{n}s"
        return s
    raise TypeError("step must be str or int")


def prom_query_range(
    promql: str,
    start: str | float | int,
    end: str | float | int,
    step: str | int,
) -> dict[str, Any]:
    """Run a PromQL range query and return a normalized ``dict`` for agents."""
    if not promql or not promql.strip():
        raise ValueError("promql must be a non-empty string")

    _validate_time_window(start, end)
    step_str = _normalize_step(step)

    base_url = os.getenv("PROMETHEUS_BASE_URL", "http://127.0.0.1:9090").strip()
    token = os.getenv("PROMETHEUS_BEARER_TOKEN")
    token = token.strip() if token else None
    verify = verify_ssl_from_env()

    with PrometheusClient(base_url, token=token, verify=verify) as client:
        payload = client.query_range(
            promql.strip(),
            start=start,
            end=end,
            step=step_str,
        )

    normalized: NormalizedQueryResponse = normalize_query_result(
        promql.strip(), payload
    )
    return dict(normalized)
