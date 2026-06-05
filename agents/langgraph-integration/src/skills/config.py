"""Skills environment configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class SkillsConfig:
    skills_dir: Path
    db_path: Path
    record_enabled: bool
    search_limit: int


def skills_config() -> SkillsConfig:
    root = os.environ.get("SENTINEL_ROOT", "").strip()
    base = Path(root) if root else _repo_root()
    skills_dir = Path(
        os.environ.get("SENTINEL_SKILLS_DIR", str(base / "skills"))
    ).resolve()
    db_path = Path(
        os.environ.get("SENTINEL_SKILLS_DB", str(skills_dir / ".index" / "skills.db"))
    ).resolve()
    record = os.environ.get("SENTINEL_SKILLS_RECORD", "1").strip().lower()
    record_enabled = record not in ("0", "false", "no", "off")
    limit_raw = os.environ.get("SENTINEL_SKILLS_SEARCH_LIMIT", "3").strip()
    try:
        search_limit = max(1, int(limit_raw))
    except ValueError:
        search_limit = 3
    return SkillsConfig(
        skills_dir=skills_dir,
        db_path=db_path,
        record_enabled=record_enabled,
        search_limit=search_limit,
    )
