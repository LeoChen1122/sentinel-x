"""Skill retrieval query building with issue synonyms."""

from __future__ import annotations

from typing import TYPE_CHECKING

from skills.config import skills_config
from skills.models import SkillMatch
from skills.store import SkillStore, get_default_store

if TYPE_CHECKING:
    from agent.types import DiagnosisReport

ISSUE_SYNONYMS: dict[str, list[str]] = {
    "CrashLoop": [
        "CrashLoopBackOff",
        "restart loop",
        "Back-off restarting failed container",
    ],
    "OOM": ["OOMKilled", "exit code 137", "memory limit"],
    "SchedulingFailure": ["FailedScheduling", "node capacity"],
    "InspectionFailed": ["inspection failed", "inspection not ok"],
    "WarningEvents": ["warning event", "Warning"],
}


def _quote_fts_term(term: str) -> str:
    term = term.strip()
    if not term:
        return ""
    if " " in term or "-" in term:
        escaped = term.replace('"', '""')
        return f'"{escaped}"'
    return term


def build_search_query(diagnosis: DiagnosisReport) -> str:
    """Build FTS OR query from diagnosis issues and actions."""
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        t = term.strip()
        if not t:
            return
        key = t.lower()
        if key in seen:
            return
        seen.add(key)
        quoted = _quote_fts_term(t)
        if quoted:
            terms.append(quoted)

    for issue in diagnosis.get("issues") or []:
        add(str(issue))
        for syn in ISSUE_SYNONYMS.get(str(issue), []):
            add(syn)

    for action in diagnosis.get("recommended_actions") or []:
        add(str(action))

    if not terms:
        return ""
    return " OR ".join(terms)


def retrieve_for_diagnosis(
    diagnosis: DiagnosisReport,
    *,
    store: SkillStore | None = None,
    limit: int | None = None,
) -> list[SkillMatch]:
    cfg = skills_config()
    st = store or get_default_store()
    query = build_search_query(diagnosis)
    if not query:
        return []
    lim = limit if limit is not None else cfg.search_limit
    return st.search(query, limit=lim)
