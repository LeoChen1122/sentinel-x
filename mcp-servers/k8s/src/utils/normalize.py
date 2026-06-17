from __future__ import annotations

import logging
import os
from typing import Any

from models.responses import NormalizedK8sListResponse

logger = logging.getLogger(__name__)


def _normalize_debug_enabled() -> bool:
    return os.getenv("K8S_NORMALIZE_DEBUG", "").strip().lower() in ("1", "true", "yes")


def _maybe_debug_list_payload(op: str, query: str, payload: dict[str, Any]) -> None:
    if not _normalize_debug_enabled():
        return
    raw = payload.get("items")
    if not isinstance(raw, list):
        logger.debug(
            "%s query=%r: payload.items is %s, not list",
            op,
            query,
            type(raw).__name__,
        )
        return
    non_dict = sum(1 for x in raw if not isinstance(x, dict))
    if non_dict:
        logger.debug(
            "%s query=%r: skipped %d non-dict items of %d",
            op,
            query,
            non_dict,
            len(raw),
        )


def _first_nonempty_str(d: dict[str, Any], keys: list[str]) -> str | None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _opt_nonempty_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _items_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("items")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for x in raw:
        if isinstance(x, dict):
            out.append(x)
    return out


def _pod_display_status(status_obj: dict[str, Any]) -> str:
    """Prefer container waiting/terminated reason over pod phase (CrashLoop keeps phase=Running)."""
    phase = _opt_nonempty_str(status_obj.get("phase")) or "Unknown"
    for key in ("containerStatuses", "initContainerStatuses"):
        containers = status_obj.get(key)
        if not isinstance(containers, list):
            continue
        for cs in containers:
            if not isinstance(cs, dict):
                continue
            state = cs.get("state")
            if not isinstance(state, dict):
                continue
            waiting = state.get("waiting")
            if isinstance(waiting, dict):
                reason = _opt_nonempty_str(waiting.get("reason"))
                if reason:
                    return reason
            terminated = state.get("terminated")
            if isinstance(terminated, dict):
                reason = _opt_nonempty_str(terminated.get("reason"))
                if reason and reason not in ("Completed",):
                    return reason
    return phase


def normalize_pod_list(
    query: str,
    payload: dict[str, Any],
    *,
    limit: int | None = None,
) -> NormalizedK8sListResponse:
    """Turn a ``list_namespaced_pod`` API body (serialized dict) into ``{query, results}``.

    Each result row is ``{"name": str, "status": str}`` where ``status`` prefers
    container waiting reason (e.g. ``CrashLoopBackOff``) over pod ``phase``.

    ``limit`` caps the number of rows returned (after filtering); use for large lists.
    Set env ``K8S_NORMALIZE_DEBUG=1`` for debug logs on odd payload shapes.
    """
    if limit is not None:
        if limit < 0:
            raise ValueError("limit must be non-negative when set")
        if limit == 0:
            return NormalizedK8sListResponse(query=query, results=[])
    _maybe_debug_list_payload("normalize_pod_list", query, payload)
    results: list[dict[str, Any]] = []
    for item in _items_list(payload):
        meta = item.get("metadata")
        if not isinstance(meta, dict):
            continue
        name = meta.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        status_obj = item.get("status")
        display = "Unknown"
        if isinstance(status_obj, dict):
            display = _pod_display_status(status_obj)
        results.append({"name": name, "status": display})
        if limit is not None and len(results) >= limit:
            break
    return NormalizedK8sListResponse(query=query, results=results)


def _event_count(item: dict[str, Any]) -> int | None:
    """Return event occurrence count from ``count`` or ``series.count`` (Kubernetes Events API)."""
    raw = item.get("count")
    if isinstance(raw, int) and raw >= 0:
        return raw
    series = item.get("series")
    if isinstance(series, dict):
        c = series.get("count")
        if isinstance(c, int) and c >= 0:
            return c
    return None


def _event_last_timestamp(item: dict[str, Any]) -> str | None:
    return _first_nonempty_str(
        item,
        ["eventTime", "lastTimestamp", "deprecatedLastTimestamp"],
    )


def normalize_event_list(
    query: str,
    payload: dict[str, Any],
    *,
    limit: int | None = None,
) -> NormalizedK8sListResponse:
    """Turn a ``list_namespaced_event`` API body (serialized dict) into ``{query, results}``.

    Each result row includes common fields agents use when correlating with Pods:
    ``type``, ``reason``, ``message``, ``object_kind``, ``object_name``, ``namespace``,
    ``count``, ``last_timestamp``. Missing values are omitted so payloads stay small.

    ``limit`` caps the number of rows returned (after filtering); prefer also filtering
    at the API/tool layer (time range, field selector) for large namespaces.

    Set env ``K8S_NORMALIZE_DEBUG=1`` for debug logs on odd payload shapes.
    """
    if limit is not None:
        if limit < 0:
            raise ValueError("limit must be non-negative when set")
        if limit == 0:
            return NormalizedK8sListResponse(query=query, results=[])
    _maybe_debug_list_payload("normalize_event_list", query, payload)
    results: list[dict[str, Any]] = []
    for item in _items_list(payload):
        meta = item.get("metadata")
        namespace = None
        if isinstance(meta, dict):
            namespace = _opt_nonempty_str(meta.get("namespace"))

        involved = item.get("involvedObject")
        object_kind = None
        object_name = None
        if isinstance(involved, dict):
            object_kind = _opt_nonempty_str(involved.get("kind"))
            object_name = _opt_nonempty_str(involved.get("name"))

        row: dict[str, Any] = {}
        if (t := _opt_nonempty_str(item.get("type"))) is not None:
            row["type"] = t
        if (r := _opt_nonempty_str(item.get("reason"))) is not None:
            row["reason"] = r
        if (m := _opt_nonempty_str(item.get("message"))) is not None:
            row["message"] = m
        if object_kind is not None:
            row["object_kind"] = object_kind
        if object_name is not None:
            row["object_name"] = object_name
        if namespace is not None:
            row["namespace"] = namespace
        cnt = _event_count(item)
        if cnt is not None:
            row["count"] = cnt
        last_ts = _event_last_timestamp(item)
        if last_ts is not None:
            row["last_timestamp"] = last_ts
        results.append(row)
        if limit is not None and len(results) >= limit:
            break
    return NormalizedK8sListResponse(query=query, results=results)
