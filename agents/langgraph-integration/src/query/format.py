"""CLI text formatting for query results (step 6 visualization)."""

from __future__ import annotations

from typing import Any


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "(empty)\n"
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    sep = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    line = "-+-".join("-" * w for w in widths)
    body = [" | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) for row in rows]
    return sep + "\n" + line + "\n" + "\n".join(body) + "\n"


def format_query_result(result: dict[str, Any]) -> str:
    """Human-readable summary for terminal output."""
    op = result.get("op", "unknown")
    if op == "list_pods":
        rows = [
            [
                str(p.get("namespace", "")),
                str(p.get("name", "")),
                str(p.get("status", "")),
            ]
            for p in result.get("pods") or []
        ]
        return f"Pods ({result.get('count', 0)})\n" + _table(
            ["namespace", "name", "status"], rows
        )
    if op == "pod_status":
        if not result.get("found"):
            return f"Pod not found: {result.get('namespace')}/{result.get('name')}\n"
        props = result.get("properties") or {}
        lines = [f"Pod {result.get('id')}", f"  status: {props.get('status')}"]
        for k, v in sorted(props.items()):
            if k not in ("name", "namespace", "status"):
                lines.append(f"  {k}: {v}")
        return "\n".join(lines) + "\n"
    if op == "events_for_pod":
        rows = [
            [
                str(e.get("type", "")),
                str(e.get("reason", "")),
                str(e.get("last_timestamp", "")),
            ]
            for e in result.get("events") or []
        ]
        header = (
            f"Events for pod {result.get('namespace')}/{result.get('name')} "
            f"({result.get('count', 0)})\n"
        )
        return header + _table(["type", "reason", "last_timestamp"], rows)
    if op == "inspections_summary":
        rows = [
            [
                str(i.get("timestamp", "")),
                str(i.get("node", "")),
                str(i.get("status", "")),
                str(len(i.get("linked_pods") or [])),
            ]
            for i in result.get("inspections") or []
        ]
        return f"Inspections ({result.get('count', 0)})\n" + _table(
            ["timestamp", "node", "status", "pods_linked"], rows
        )
    if op == "list_events":
        rows = [
            [
                str(e.get("namespace", "")),
                str(e.get("reason", "")),
                str(e.get("object_name", "")),
                str(e.get("last_timestamp", "")),
            ]
            for e in result.get("events") or []
        ]
        return f"Events ({result.get('count', 0)})\n" + _table(
            ["namespace", "reason", "object_name", "last_timestamp"], rows
        )
    if op == "inspections_for_pod":
        rows = [
            [
                str(i.get("timestamp", "")),
                str(i.get("node", "")),
                str(i.get("status", "")),
            ]
            for i in result.get("inspections") or []
        ]
        header = (
            f"Inspections for pod {result.get('namespace')}/{result.get('name')} "
            f"({result.get('count', 0)})\n"
        )
        return header + _table(["timestamp", "node", "status"], rows)
    return str(result) + "\n"
