from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from clients.kubernetes import KubernetesClient
from models.responses import NormalizedK8sListResponse
from utils.normalize import normalize_event_list

K8S_GET_EVENTS_TOOL_META: dict[str, Any] = {
    "name": "k8s_get_events",
    "readonly": True,
    "risk": "low",
    "category": "kubernetes",
}


def _nonempty_env(var: str | None) -> str | None:
    return var.strip() if var and var.strip() else None


def _client_kwargs_from_env() -> dict[str, Any]:
    raw = os.getenv("K8S_REQUEST_TIMEOUT", "30").strip() or "30"
    try:
        timeout = float(raw)
    except ValueError:
        timeout = 30.0
    kubeconfig_path = _nonempty_env(os.getenv("K8S_KUBECONFIG"))
    kube_context = _nonempty_env(os.getenv("K8S_CONTEXT"))
    return {
        "timeout": timeout,
        "kubeconfig_path": kubeconfig_path,
        "kube_context": kube_context,
    }


def _parse_since_time(value: str) -> datetime:
    s = value.strip()
    if not s:
        raise ValueError("since_time must be a non-empty RFC3339 / ISO-8601 string")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as e:
        raise ValueError(
            "since_time must be a valid RFC3339 / ISO-8601 timestamp"
        ) from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_event_timestamp(raw: str) -> datetime | None:
    s = raw.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _event_item_best_time(item: dict[str, Any]) -> datetime | None:
    """Pick the latest parseable timestamp on an Event dict (serialized form)."""
    best: datetime | None = None
    for key in (
        "eventTime",
        "lastTimestamp",
        "deprecatedLastTimestamp",
        "firstTimestamp",
        "deprecatedFirstTimestamp",
    ):
        v = item.get(key)
        if not isinstance(v, str):
            continue
        dt = _parse_event_timestamp(v)
        if dt is None:
            continue
        if best is None or dt > best:
            best = dt
    meta = item.get("metadata")
    if isinstance(meta, dict):
        ct = meta.get("creationTimestamp")
        if isinstance(ct, str):
            dt = _parse_event_timestamp(ct)
            if dt is not None and (best is None or dt > best):
                best = dt
    return best


def _filter_event_payload_by_since(
    payload: dict[str, Any],
    since: datetime,
) -> dict[str, Any]:
    raw = payload.get("items")
    if not isinstance(raw, list):
        return payload
    kept: list[Any] = []
    for x in raw:
        if not isinstance(x, dict):
            continue
        t = _event_item_best_time(x)
        if t is None:
            continue
        if t >= since:
            kept.append(x)
    return {**payload, "items": kept}


def k8s_get_events(
    namespace: str,
    pod_name: str | None = None,
    limit: int | None = None,
    *,
    since_time: str | None = None,
    api_limit: int | None = None,
    field_selector: str | None = None,
) -> dict[str, Any]:
    """List Events in a namespace (optionally for one Pod) and return normalized results.

    ``api_limit`` and ``field_selector`` are applied by the Kubernetes API (smaller
    payloads over the wire). ``since_time`` filters the returned list in-process
    using the best available Event timestamp (RFC3339 / ISO-8601, ``Z`` allowed).

    ``limit`` is passed to :func:`normalize_event_list` only (post-filter row cap).
    """
    if not namespace or not namespace.strip():
        raise ValueError("namespace must be a non-empty string")
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative when set")
    if api_limit is not None and api_limit < 1:
        raise ValueError("api_limit must be a positive integer when set")

    pod = _nonempty_env(pod_name)
    fs = _nonempty_env(field_selector)

    since_dt: datetime | None = None
    if since_time is not None:
        st = since_time.strip()
        if not st:
            raise ValueError("since_time must be non-empty when provided")
        since_dt = _parse_since_time(st)

    opts = _client_kwargs_from_env()
    with KubernetesClient(
        opts["timeout"],
        kube_context=opts["kube_context"],
        kubeconfig_path=opts["kubeconfig_path"],
    ) as client:
        payload = client.list_events(
            namespace,
            pod,
            field_selector=fs,
            limit=api_limit,
        )

    if since_dt is not None:
        payload = _filter_event_payload_by_since(payload, since_dt)

    normalized: NormalizedK8sListResponse = normalize_event_list(
        "get_events",
        payload,
        limit=limit,
    )
    return dict(normalized)
