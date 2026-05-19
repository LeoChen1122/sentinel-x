from __future__ import annotations

import hashlib
import re

_SAFE = re.compile(r"[^a-zA-Z0-9._/-]+")


def _sanitize(part: str) -> str:
    return _SAFE.sub("_", part.strip())


def _sanitize_cluster(cluster_id: str) -> str:
    cid = _sanitize(cluster_id)
    if not cid:
        raise ValueError("cluster_id is required")
    return cid


def pod_id(cluster_id: str, namespace: str, name: str) -> str:
    """Stable Pod entity id: ``pod:{cluster_id}/{namespace}/{name}``."""
    cid = _sanitize_cluster(cluster_id)
    ns = _sanitize(namespace)
    nm = _sanitize(name)
    if not ns or not nm:
        raise ValueError("namespace and name are required for pod_id")
    return f"pod:{cid}/{ns}/{nm}"


def node_id(cluster_id: str, name: str) -> str:
    """Stable K8s Node entity id: ``node:{cluster_id}/{name}``."""
    cid = _sanitize_cluster(cluster_id)
    nm = _sanitize(name)
    if not nm:
        raise ValueError("name is required for node_id")
    return f"node:{cid}/{nm}"


def inspection_id(cluster_id: str, timestamp: str, node: str) -> str:
    """Stable inspection record id: ``inspection:{cluster_id}:{timestamp}:{node}``."""
    cid = _sanitize_cluster(cluster_id)
    ts = _sanitize(timestamp)
    nd = _sanitize(node)
    if not ts or not nd:
        raise ValueError("timestamp and node are required for inspection_id")
    return f"inspection:{cid}:{ts}:{nd}"


def event_id(
    *,
    cluster_id: str,
    namespace: str,
    object_kind: str,
    object_name: str,
    reason: str,
    last_timestamp: str | None = None,
    message: str | None = None,
) -> str:
    """Stable Event entity id (includes ``cluster_id``)."""
    cid = _sanitize_cluster(cluster_id)
    ns = _sanitize(namespace or "default")
    kind = _sanitize(object_kind or "Unknown")
    name = _sanitize(object_name or "unknown")
    rsn = _sanitize(reason or "Unknown")
    ts = _sanitize(last_timestamp or "")
    structured = f"event:{cid}:{ns}:{kind}:{name}:{rsn}:{ts}"
    if len(structured) <= 200:
        return structured
    canonical = "|".join(
        [cid, ns, kind, name, rsn, ts, _sanitize(message or "")]
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"event:{cid}:{ns}:{digest}"
