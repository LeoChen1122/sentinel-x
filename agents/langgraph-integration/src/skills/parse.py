"""Parse skill Markdown frontmatter and body (no PyYAML)."""

from __future__ import annotations

import re
from typing import Any

_LIST_RE = re.compile(r"^\[(.*)\]$")
_BOOL = {"true": True, "false": False}


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    m = _LIST_RE.match(value)
    if m:
        inner = m.group(1).strip()
        if not inner:
            return []
        return [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
    low = value.lower()
    if low in _BOOL:
        return _BOOL[low]
    if value.isdigit():
        return int(value)
    return value.strip("'\"")


def split_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    text = markdown.strip()
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm: dict[str, Any] = {}
    for line in parts[1].splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        fm[key.strip()] = _parse_scalar(raw)
    body = parts[2].lstrip("\n")
    return fm, body


def render_frontmatter(fields: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, list):
            inner = ", ".join(str(v) for v in value)
            lines.append(f"{key}: [{inner}]")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def compose_skill_markdown(fields: dict[str, Any], body: str) -> str:
    return render_frontmatter(fields) + "\n\n" + body.strip() + "\n"


def summary_from_body(body: str, *, max_len: int = 160) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("#"):
            continue
        if line:
            if len(line) > max_len:
                return line[: max_len - 3] + "..."
            return line
    return ""
