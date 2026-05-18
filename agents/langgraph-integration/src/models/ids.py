from __future__ import annotations

import hashlib
import re

_SAFE = re.compile(r"[^a-zA-Z0-9._/-]+")


def _sanitize(part: str) -> str:
    return _SAFE.sub("_", part.strip())


def pod_id(namespace: str, name: str) -> str:
    """Stable Pod entity id: ``pod:{namespace}/{name}``."""
    ns = _sanitize(namespace)
    nm = _sanitize(name)
    if not ns or not nm:
        raise ValueError("namespace and name are required for pod_id")
    return f"pod:{ns}/{nm}"


def node_id(name: str) -> str:
    """Stable K8s Node entity id: ``node:{name}``."""
    nm = _sanitize(name)
    if not nm:
        raise ValueError("name is required for node_id")
    return f"node:{nm}"


def inspection_id(timestamp: str, node: str) -> str:
    """Stable inspection record id: ``inspection:{timestamp}:{node}``."""
    ts = _sanitize(timestamp)
    nd = _sanitize(node)
    if not ts or not nd:
        raise ValueError("timestamp and node are required for inspection_id")
    return f"inspection:{ts}:{nd}"


def event_id(
    *,
    namespace: str,
    object_kind: str,
    object_name: str,
    reason: str,
    last_timestamp: str | None = None,
    message: str | None = None,
) -> str:
    """Stable Event entity id.

    Uses a structured key when short enough; otherwise SHA-256 prefix of
    canonical fields (avoids collisions when many events share reason/time).
    """
    ns = _sanitize(namespace or "default")
    kind = _sanitize(object_kind or "Unknown")
    name = _sanitize(object_name or "unknown")
    rsn = _sanitize(reason or "Unknown")
    ts = _sanitize(last_timestamp or "")
    structured = f"event:{ns}:{kind}:{name}:{rsn}:{ts}"
    if len(structured) <= 200:
        return structured
    canonical = "|".join(
        [ns, kind, name, rsn, ts, _sanitize(message or "")]
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"event:{ns}:{digest}"
