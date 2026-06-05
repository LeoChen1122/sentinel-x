"""Template-based inspection narrative (phase A, no LLM)."""

from __future__ import annotations

from typing import Any

from agent.types import DiagnosisReport, GatherResult, InspectionReport, LinkedEntity, ReportSection
from models.entities import EntityType
from skills.models import SkillMatch


def _linked_event(row: dict[str, Any]) -> LinkedEntity:
    eid = str(row.get("id", ""))
    reason = row.get("reason")
    label = f"{row.get('type', '')} {reason}".strip() if reason else eid
    return LinkedEntity(
        entity_id=eid,
        entity_type=EntityType.EVENT.value,
        relation="has_event",
        label=label,
    )


def _linked_inspection(row: dict[str, Any]) -> LinkedEntity:
    iid = str(row.get("id", ""))
    status = row.get("status", "")
    return LinkedEntity(
        entity_id=iid,
        entity_type=EntityType.INSPECTION.value,
        relation="inspects_pod",
        label=f"{status} @ {row.get('node', '')}".strip(),
    )


def _linked_pod(entity_id: str, label: str | None = None) -> LinkedEntity:
    return LinkedEntity(
        entity_id=entity_id,
        entity_type=EntityType.POD.value,
        relation=None,
        label=label,
    )


def _append_skill_matches(
    report: InspectionReport,
    skill_matches: list[SkillMatch] | None,
) -> InspectionReport:
    if not skill_matches:
        return report
    lines: list[str] = []
    for match in skill_matches:
        extra = ""
        if match.get("hit_count", 1) > 1:
            extra += f" (seen {match['hit_count']} times)"
        if match.get("source_count", 1) > 1:
            extra += f" from {match['source_count']} pods"
        verified = "verified" if match.get("verified") else "unverified"
        lines.append(
            f"- **{match.get('name', '')}** — {match.get('symptom', '')}: "
            f"{match.get('summary', '')}{extra} [{verified}]"
        )
    section = ReportSection(
        title="Similar past skills",
        body="\n".join(lines),
        linked_entities=[],
    )
    sections = list(report.get("sections") or [])
    sections.append(section)
    md = (report.get("markdown") or "").rstrip() + "\n\n## Similar past skills\n\n" + "\n".join(lines) + "\n"
    updated = dict(report)
    updated["sections"] = sections
    updated["markdown"] = md
    return InspectionReport(**updated)


def build_report_template(
    gather: GatherResult,
    *,
    skill_matches: list[SkillMatch] | None = None,
) -> InspectionReport:
    """Turn gather facts into structured ``InspectionReport`` (phase A template)."""
    q = gather["queries"]
    pod_status = q.get("pod_status") or {}
    events_q = q.get("events_for_pod") or {}
    insp_q = q.get("inspections_for_pod") or {}

    cid = gather["cluster_id"]
    ns = gather["namespace"]
    pname = gather["pod_name"]
    pid = gather["pod_entity_id"]

    linked_events = [_linked_event(e) for e in events_q.get("events") or []]
    linked_inspections = [
        _linked_inspection(i) for i in insp_q.get("inspections") or []
    ]
    linked_pods = [_linked_pod(pid, label=pname)]

    sections: list[ReportSection] = []

    if pod_status.get("found"):
        props = pod_status.get("properties") or {}
        status = props.get("status", "unknown")
        sections.append(
            ReportSection(
                title="Pod status",
                body=f"Pod `{pname}` in namespace `{ns}` (cluster `{cid}`) is **{status}**.",
                linked_entities=[_linked_pod(pid, status)],
            )
        )
    else:
        sections.append(
            ReportSection(
                title="Pod status",
                body=f"Pod `{pname}` was not found in cluster `{cid}`.",
                linked_entities=[],
            )
        )

    if linked_events:
        lines = [
            f"- `{le['entity_id']}`: {le.get('label', '')}" for le in linked_events
        ]
        sections.append(
            ReportSection(
                title="Linked events",
                body="Events associated via `has_event`:\n" + "\n".join(lines),
                linked_entities=list(linked_events),
            )
        )
    else:
        sections.append(
            ReportSection(
                title="Linked events",
                body="No events linked to this pod.",
                linked_entities=[],
            )
        )

    if linked_inspections:
        lines = [
            f"- `{li['entity_id']}`: {li.get('label', '')}" for li in linked_inspections
        ]
        sections.append(
            ReportSection(
                title="Inspections",
                body="Inspection records linked via `inspects_pod`:\n"
                + "\n".join(lines),
                linked_entities=list(linked_inspections),
            )
        )
    else:
        sections.append(
            ReportSection(
                title="Inspections",
                body="No inspection records linked to this pod.",
                linked_entities=[],
            )
        )

    warning_count = sum(
        1
        for e in events_q.get("events") or []
        if str(e.get("type", "")).lower() == "warning"
    )
    insp_failed = any(
        str(i.get("status", "")).lower() not in ("ok", "healthy", "pass")
        for i in insp_q.get("inspections") or []
    )
    if warning_count or insp_failed:
        summary = (
            f"Cluster `{cid}`: pod `{pname}` needs attention "
            f"({warning_count} warning event(s)"
            + (", inspection not ok" if insp_failed else "")
            + ")."
        )
    else:
        summary = f"Cluster `{cid}`: pod `{pname}` looks healthy from graph facts."

    md_parts = [
        f"# Inspection report: {pname}",
        f"**Cluster:** `{cid}` | **Namespace:** `{ns}`",
        "",
        f"**Summary:** {summary}",
        "",
    ]
    for sec in sections:
        md_parts.append(f"## {sec['title']}")
        md_parts.append("")
        md_parts.append(sec["body"])
        md_parts.append("")
    markdown = "\n".join(md_parts).strip() + "\n"

    base = InspectionReport(
        cluster_id=cid,
        namespace=ns,
        pod_name=pname,
        pod_entity_id=pid,
        markdown=markdown,
        sections=sections,
        linked_events=linked_events,
        linked_pods=linked_pods,
        linked_inspections=linked_inspections,
        summary=summary,
        narrative_source="template",
        ok=True,
        error=None,
        error_stage=None,
        llm_error=None,
    )
    return _append_skill_matches(base, skill_matches)


def build_report(
    gather: GatherResult,
    *,
    use_llm: bool | None = None,
    diagnosis: DiagnosisReport | None = None,
    skill_matches: list[SkillMatch] | None = None,
) -> InspectionReport:
    """Template report; optionally polish with LLM (Qwen via DashScope compatible API)."""
    from agent.llm import polish_inspection_report, resolve_use_llm

    base = build_report_template(gather, skill_matches=None)
    if not resolve_use_llm(use_llm):
        return _append_skill_matches(base, skill_matches)
    polished = polish_inspection_report(base, gather, diagnosis=diagnosis)
    return _append_skill_matches(polished, skill_matches)


def build_report_from_gather_dict(
    gather: dict[str, Any],
    *,
    use_llm: bool | None = None,
    diagnosis: dict[str, Any] | DiagnosisReport | None = None,
    skill_matches: list[SkillMatch] | None = None,
) -> InspectionReport:
    """Accept wire ``payload.gather`` / optional ``payload.diagnosis`` dict."""
    diag: DiagnosisReport | None = None
    if diagnosis is not None:
        if isinstance(diagnosis, dict):
            diag = DiagnosisReport(**diagnosis)
        else:
            diag = diagnosis
    matches: list[SkillMatch] | None = skill_matches
    return build_report(
        GatherResult(**gather),
        use_llm=use_llm,
        diagnosis=diag,
        skill_matches=matches,
    )
