from __future__ import annotations

import json
from typing import Any

import httpx

from utils.errors import (
    PrometheusConnectionError,
    PrometheusError,
    PrometheusQueryError,
)


class PrometheusClient:
    """Thin HTTP client for Prometheus expression APIs."""

    def __init__(
        self,
        base_url: str,
        timeout: float | httpx.Timeout = 30.0,
        *,
        token: str | None = None,
        verify: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            headers=headers,
            verify=verify,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PrometheusClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _handle_prometheus_error(self, payload: dict[str, Any]) -> None:
        if payload.get("status") == "error":
            err = payload.get("error") or "unknown error"
            err_type = payload.get("errorType")
            if err_type:
                raise PrometheusQueryError(f"{err_type}: {err}")
            raise PrometheusQueryError(str(err))

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.get(path, params=params)
        except httpx.RequestError as e:
            raise PrometheusConnectionError(str(e) or "request failed") from e

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise PrometheusError(
                f"HTTP {e.response.status_code}: {e.response.text[:500]}"
            ) from e

        try:
            payload = response.json()
        except json.JSONDecodeError as e:
            raise PrometheusError("invalid JSON in Prometheus response") from e

        if not isinstance(payload, dict):
            raise PrometheusError("unexpected Prometheus response shape")

        self._handle_prometheus_error(payload)
        return payload

    def query(
        self,
        promql: str,
        time: str | float | int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"query": promql}
        if time is not None:
            params["time"] = time
        return self._request("/api/v1/query", params)

    def query_range(
        self,
        promql: str,
        start: str | float | int,
        end: str | float | int,
        step: str,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "query": promql,
            "start": start,
            "end": end,
            "step": step,
        }
        return self._request("/api/v1/query_range", params)
