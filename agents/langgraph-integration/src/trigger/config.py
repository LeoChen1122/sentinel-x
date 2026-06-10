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
            str(base / "var" / "lib" / "sentinel" / "inspect-patrol-state.json"),
        )
    ).resolve()
    dry_raw = os.environ.get("SENTINEL_PATROL_DRY_RUN", "true").strip().lower()
    default_dry_run = dry_raw not in ("0", "false", "no", "off")
    return PatrolConfig(
        enabled=enabled,
        cooldown_sec=cooldown_sec,
        state_path=state_path,
        default_dry_run=default_dry_run,
    )
