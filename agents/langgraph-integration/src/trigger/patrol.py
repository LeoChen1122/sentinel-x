"""Patrol: find unhealthy pods in graph and select one to inspect (W7)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, TypedDict

from clients.langgraph_client import query_sentinel
from trigger.config import PatrolConfig, patrol_config, patrol_namespaces

# Lower = higher priority
_SEVERITY_RANK = {
    "CrashLoop": 0,
    "ImagePullBackOff": 1,
    "Error": 2,
    "WarningEvents": 3,
}

_STATUS_PATTERNS: tuple[tuple[str, str], ...] = (
    ("CrashLoopBackOff", "CrashLoop"),
    ("CrashLoop", "CrashLoop"),
    ("ImagePullBackOff", "ImagePullBackOff"),
    ("ErrImagePull", "ImagePullBackOff"),
    ("Error", "Error"),
)


class PodCandidate(TypedDict):
    cluster_id: str
    namespace: str
    pod_name: str
    pod_id: str
    severity: str
    reason: str


def _classify_status(status: str) -> tuple[str, str] | None:
    upper = status.upper()
    for pattern, severity in _STATUS_PATTERNS:
        if pattern.upper() in upper:
            return severity, pattern
    return None


_TERMINAL_OK_STATUSES = frozenset({"Succeeded", "Completed", "Pending"})


def _event_confirms_active_crashloop(events_result: dict[str, Any]) -> bool:
    """Strict event check when pod phase is still Running (MCP phase-only fallback)."""
    events = events_result.get("events") or []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        props = ev.get("properties") or ev
        reason = str(props.get("reason") or "").upper()
        msg = str(props.get("message") or "").upper()
        if "CRASHLOOPBACKOFF" in reason or "CRASHLOOP" in reason:
            return True
        if "CRASH" in reason and "LOOP" in reason:
            return True
        if "CRASHLOOPBACKOFF" in msg or "CRASH LOOP" in msg:
            return True
    return False


def _event_confirms(events_result: dict[str, Any], severity: str) -> bool:
    events = events_result.get("events") or []
    if not events:
        return severity in ("CrashLoop", "ImagePullBackOff", "Error")
    for ev in events:
        if not isinstance(ev, dict):
            continue
        props = ev.get("properties") or ev
        reason = str(props.get("reason") or props.get("type") or "").upper()
        msg = str(props.get("message") or "").upper()
        if severity == "CrashLoop" and (
            "CRASHLOOP" in reason
            or "CRASH" in reason
            or "CRASHLOOP" in msg
            or "CRASH LOOP" in msg
        ):
            return True
        if severity == "ImagePullBackOff" and (
            "IMAGEPULL" in reason or "ERRIMAGE" in reason or "ERRIMAGEPULL" in reason
        ):
            return True
        if severity == "Error" and reason in ("FAILED", "ERROR"):
            return True
        if severity == "WarningEvents" and str(props.get("type") or "").lower() == "warning":
            return True
    return False


def find_inspect_candidates(
    *,
    thread_id: str,
    cluster_id: str,
    namespace: str | None = None,
    client: Any | None = None,
    tenant_id: str | None = None,
) -> list[PodCandidate]:
    """List pods worth inspecting from graph query state."""
    params: dict[str, Any] = {"cluster_id": cluster_id}
    if namespace:
        params["namespace"] = namespace
    if tenant_id:
        params["tenant_id"] = tenant_id

    pods_result = query_sentinel("list_pods", thread_id=thread_id, client=client, **params)
    pods = pods_result.get("pods") or []
    candidates: list[PodCandidate] = []

    for row in pods:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        ns = str(row.get("namespace") or namespace or "").strip()
        cid = str(row.get("cluster_id") or cluster_id).strip()
        status = str(row.get("status") or "")
        if not name or not ns:
            continue
        classified = _classify_status(status)
        if classified:
            severity, reason = classified
            pod_id = str(row.get("id") or f"pod:{cid}:{ns}:{name}")
            candidates.append(
                PodCandidate(
                    cluster_id=cid,
                    namespace=ns,
                    pod_name=name,
                    pod_id=pod_id,
                    severity=severity,
                    reason=reason,
                )
            )
            continue
        phase = status.strip()
        if phase in _TERMINAL_OK_STATUSES:
            continue
        if phase not in ("Running", "Unknown", ""):
            continue
        ev = query_sentinel(
            "events_for_pod",
            thread_id=thread_id,
            client=client,
            cluster_id=cid,
            namespace=ns,
            name=name,
            tenant_id=tenant_id,
        )
        events = ev.get("events") or []
        if not events:
            continue
        if _event_confirms_active_crashloop(ev):
            classified = ("CrashLoop", "CrashLoopBackOff")
        elif _event_confirms(ev, "ImagePullBackOff"):
            classified = ("ImagePullBackOff", "ImagePullBackOff")
        elif _event_confirms(ev, "Error"):
            classified = ("Error", "Error")
        else:
            continue
        severity, reason = classified
        if not _event_confirms(ev, severity):
            continue
        pod_id = str(row.get("id") or f"pod:{cid}:{ns}:{name}")
        candidates.append(
            PodCandidate(
                cluster_id=cid,
                namespace=ns,
                pod_name=name,
                pod_id=pod_id,
                severity=severity,
                reason=reason,
            )
        )

    candidates.sort(key=lambda c: (_SEVERITY_RANK.get(c["severity"], 99), c["pod_name"]))
    return candidates


def find_inspect_candidates_multi(
    *,
    thread_id: str,
    cluster_id: str,
    namespaces: list[str] | tuple[str, ...] | None = None,
    client: Any | None = None,
    tenant_id: str | None = None,
) -> list[PodCandidate]:
    """Scan multiple namespaces; merge and dedupe by pod_id."""
    ns_list = list(namespaces) if namespaces else list(patrol_namespaces())
    seen: set[str] = set()
    merged: list[PodCandidate] = []
    for ns in ns_list:
        for cand in find_inspect_candidates(
            thread_id=thread_id,
            cluster_id=cluster_id,
            namespace=ns,
            client=client,
            tenant_id=tenant_id,
        ):
            pid = cand["pod_id"]
            if pid in seen:
                continue
            seen.add(pid)
            merged.append(cand)
    merged.sort(key=lambda c: (_SEVERITY_RANK.get(c["severity"], 99), c["pod_name"]))
    return merged


def load_patrol_state(path: Path | None = None) -> dict[str, float]:
    """Load {pod_id: last_trigger_unix} from JSON file."""
    cfg = patrol_config()
    p = path or cfg.state_path
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    raw = data.get("last_trigger") if isinstance(data, dict) else data
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def save_patrol_state(state: dict[str, float], path: Path | None = None) -> None:
    cfg = patrol_config()
    p = path or cfg.state_path
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"last_trigger": state, "updated_at": time.time()}
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def select_pod_to_inspect(
    candidates: list[PodCandidate],
    state: dict[str, float] | None = None,
    *,
    cfg: PatrolConfig | None = None,
    now: float | None = None,
) -> PodCandidate | None:
    """Pick highest-priority candidate outside cooldown window."""
    cfg = cfg or patrol_config()
    state = state if state is not None else load_patrol_state(cfg.state_path)
    ts = now if now is not None else time.time()
    ordered = sorted(
        candidates,
        key=lambda c: (_SEVERITY_RANK.get(c["severity"], 99), c["pod_name"]),
    )
    for cand in ordered:
        pod_id = cand["pod_id"]
        last = state.get(pod_id)
        if last is not None and ts - last < cfg.cooldown_sec:
            continue
        return cand
    return None


def mark_pod_inspected(
    pod_id: str,
    state: dict[str, float] | None = None,
    *,
    cfg: PatrolConfig | None = None,
    now: float | None = None,
) -> dict[str, float]:
    """Update cooldown state after a successful trigger."""
    cfg = cfg or patrol_config()
    state = dict(state if state is not None else load_patrol_state(cfg.state_path))
    state[pod_id] = now if now is not None else time.time()
    save_patrol_state(state, cfg.state_path)
    return state
