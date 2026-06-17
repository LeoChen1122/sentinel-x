"""Patrol / trigger configuration (W7)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class PatrolConfig:
    enabled: bool
    cooldown_sec: int
    state_path: Path
    default_dry_run: bool
    namespaces: tuple[str, ...]


def patrol_namespaces(*, default_namespace: str | None = None) -> tuple[str, ...]:
    """Namespaces to scan for unhealthy pods (deduped, order preserved)."""
    raw = os.environ.get("SENTINEL_PATROL_NAMESPACES", "").strip()
    if raw:
        parts = tuple(n.strip() for n in raw.split(",") if n.strip())
        return parts if parts else ("kube-system",)

    primary = (default_namespace or os.environ.get("NAMESPACE", "kube-system")).strip()
    extra_raw = os.environ.get("SENTINEL_PATROL_EXTRA_NAMESPACES", "sentinel-sandbox").strip()
    out: list[str] = []
    for ns in (primary, *extra_raw.split(",")):
        ns = ns.strip()
        if ns and ns not in out:
            out.append(ns)
    return tuple(out) if out else ("kube-system",)


def patrol_config() -> PatrolConfig:
    root = os.environ.get("SENTINEL_ROOT", "").strip()
    base = Path(root) if root else _repo_root()
    enabled_raw = os.environ.get("SENTINEL_PATROL_ENABLED", "1").strip().lower()
    enabled = enabled_raw not in ("0", "false", "no", "off")
    try:
        cooldown_sec = max(60, int(os.environ.get("SENTINEL_PATROL_COOLDOWN_SEC", "3600")))
    except ValueError:
        cooldown_sec = 3600
    state_path = Path(
        os.environ.get(
            "SENTINEL_PATROL_STATE_PATH",
            "/var/lib/sentinel/inspect-patrol-state.json",
        )
    ).resolve()
    dry_raw = os.environ.get("SENTINEL_PATROL_DRY_RUN", "true").strip().lower()
    default_dry_run = dry_raw not in ("0", "false", "no", "off")
    return PatrolConfig(
        enabled=enabled,
        cooldown_sec=cooldown_sec,
        state_path=state_path,
        default_dry_run=default_dry_run,
        namespaces=patrol_namespaces(),
    )
