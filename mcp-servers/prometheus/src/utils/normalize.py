from __future__ import annotations

from typing import Any

from models.responses import NormalizedQueryResponse


def normalize_query_result(query: str, payload: dict[str, Any]) -> NormalizedQueryResponse:
    """Turn a successful Prometheus query API body into ``{query, result_type, results}``.

    Callers must pass the PromQL string used for the request; it is not echoed
    by Prometheus. ``result_type`` mirrors Prometheus ``data.resultType`` (e.g.
    ``vector`` / ``matrix`` / ``scalar`` / ``string``) for UI and agents. Malformed
    or missing ``data`` yields ``result_type=None`` and ``results: []``.
    """
    if payload.get("status") != "success":
        raise ValueError("expected Prometheus payload with status=success")

    data = payload.get("data")
    if not isinstance(data, dict):
        return NormalizedQueryResponse(query=query, result_type=None, results=[])

    raw_type = data.get("resultType")
    result_type = raw_type if isinstance(raw_type, str) else None
    result = data.get("result")

    if result_type in ("vector", "matrix"):
        results: list[Any] = result if isinstance(result, list) else []
    elif result_type in ("scalar", "string"):
        results = [] if result is None else [result]
    else:
        if isinstance(result, list):
            results = result
        elif result is None:
            results = []
        else:
            results = [result]

    return NormalizedQueryResponse(
        query=query,
        result_type=result_type,
        results=results,
    )
