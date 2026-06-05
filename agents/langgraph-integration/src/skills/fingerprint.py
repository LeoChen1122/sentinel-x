"""Skill fingerprint from diagnosis issues and actions."""

from __future__ import annotations

import hashlib


def skill_fingerprint(issues: list[str], actions: list[str]) -> str:
    normalized = "|".join(sorted(set(issues))) if issues else "unknown"
    actions_str = "|".join(sorted(set(actions))) if actions else "none"
    digest = hashlib.sha256(f"{normalized}|{actions_str}".encode()).hexdigest()
    return digest[:16]
