from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

from urllib3.exceptions import RequestError as Urllib3RequestError

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.config import ConfigException

from utils.errors import (
    KubernetesApiError,
    KubernetesConnectionError,
    KubernetesError,
)

T = TypeVar("T")

_RETRY_STATUSES = frozenset({429, 502, 503, 504})
_RETRY_DELAYS_SEC = (0.2, 0.4)


def _coerce_http_status(status: object) -> int | None:
    if status is None:
        return None
    if isinstance(status, int) and status > 0:
        return status
    if isinstance(status, str) and status.isdigit():
        n = int(status)
        return n if n > 0 else None
    return None


def _body_snippet(exc: ApiException, limit: int = 500) -> str | None:
    raw = exc.body
    if raw is None:
        return None
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = str(raw)
    text = text.strip()
    if not text:
        return None
    return text[:limit]


def _map_api_exception(exc: ApiException) -> KubernetesError:
    status = _coerce_http_status(exc.status)
    body = _body_snippet(exc)
    reason = (exc.reason or "").strip()
    if status is None:
        msg = reason or (body or str(exc) or "request failed")
        return KubernetesConnectionError(msg or "connection to API server failed")
    detail = reason or body or "request failed"
    return KubernetesApiError(
        f"HTTP {status}: {detail}",
        status=status,
        body=body,
    )


def _validate_k8s_name(label: str, value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{label} must be a non-empty string")
    if "\n" in stripped or "\r" in stripped:
        raise ValueError(f"{label} must not contain newline characters")
    return stripped


class KubernetesClient:
    """Thin wrapper around the official Kubernetes Python client (CoreV1)."""

    def __init__(
        self,
        timeout: float = 30.0,
        *,
        kube_context: str | None = None,
        kubeconfig_path: str | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._timeout = float(timeout)

        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config(
                config_file=kubeconfig_path,
                context=kube_context,
            )

        configuration = client.Configuration.get_default_copy()
        configuration.connect_timeout = self._timeout
        configuration.read_timeout = self._timeout

        self._api_client = client.ApiClient(configuration)
        self._core = client.CoreV1Api(self._api_client)

    def close(self) -> None:
        self._api_client.close()

    def __enter__(self) -> KubernetesClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _serialize(self, obj: object) -> dict[str, Any]:
        data = self._api_client.sanitize_for_serialization(obj)
        if not isinstance(data, dict):
            raise KubernetesError("unexpected Kubernetes API response shape")
        return data

    def _call_with_retry(self, operation: Callable[[], T]) -> T:
        last: ApiException | None = None
        for attempt in range(3):
            try:
                return operation()
            except ApiException as e:
                last = e
                status = _coerce_http_status(e.status)
                if status in _RETRY_STATUSES and attempt < 2:
                    time.sleep(_RETRY_DELAYS_SEC[attempt])
                    continue
                raise _map_api_exception(e) from e
            except Urllib3RequestError as e:
                raise KubernetesConnectionError(
                    str(e) or "request failed"
                ) from e
            except (TimeoutError, ConnectionError, OSError) as e:
                raise KubernetesConnectionError(
                    str(e) or "request failed"
                ) from e
        assert last is not None
        raise _map_api_exception(last)

    def list_pods(self, namespace: str) -> dict[str, Any]:
        """List Pods in a namespace; returns a JSON-serializable dict."""
        ns = _validate_k8s_name("namespace", namespace)
        result = self._call_with_retry(
            lambda: self._core.list_namespaced_pod(
                ns,
                _request_timeout=self._timeout,
            )
        )
        return self._serialize(result)

    def list_events(
        self,
        namespace: str,
        pod_name: str | None = None,
        *,
        field_selector: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """List Events in a namespace.

        ``pod_name`` adds ``involvedObject`` filters. ``field_selector`` is merged
        with those requirements (AND). ``limit`` is passed to the API server (not
        an in-memory cap).
        """
        ns = _validate_k8s_name("namespace", namespace)
        if limit is not None:
            if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
                raise ValueError("limit must be a positive integer when set")

        parts: list[str] = []
        if field_selector is not None:
            fs = field_selector.strip()
            if fs:
                if "\n" in fs or "\r" in fs:
                    raise ValueError("field_selector must not contain newline characters")
                parts.append(fs)

        if pod_name is not None:
            pn = pod_name.strip()
            if not pn:
                raise ValueError("pod_name must be a non-empty string when provided")
            if "\n" in pn or "\r" in pn:
                raise ValueError("pod_name must not contain newline characters")
            if "," in pn or "=" in pn:
                raise ValueError(
                    "pod_name contains characters not supported in field_selector; "
                    "omit pod_name to list namespace events"
                )
            parts.append(f"involvedObject.kind=Pod,involvedObject.name={pn}")

        merged_selector = ",".join(parts) if parts else None

        result = self._call_with_retry(
            lambda: self._core.list_namespaced_event(
                ns,
                field_selector=merged_selector,
                limit=limit,
                _request_timeout=self._timeout,
            )
        )
        return self._serialize(result)
