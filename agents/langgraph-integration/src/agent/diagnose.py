"""Rule-based diagnosis from gather facts (phase 5, no LLM)."""

from __future__ import annotations

from typing import Any

from agent.types import DiagnosisReport, GatherResult

_OK_INSPECTION = frozenset({"ok", "healthy", "pass"})


def _active_tenant_id(tenant_id: str | None) -> str | None:
    if tenant_id is None:
        return None
    tid = str(tenant_id).strip()
    return tid if tid else None


def _dedupe_stable(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _severity_rank(severity: str) -> int:
    return {"ok": 0, "warning": 1, "critical": 2}.get(severity, 0)


def _max_severity(current: str, candidate: str) -> str:
    return candidate if _severity_rank(candidate) > _severity_rank(current) else current


def diagnose_from_gather(
    gather: GatherResult,
    *,
    tenant_id: str | None = None,
) -> DiagnosisReport:
    """Derive ``DiagnosisReport`` from ``gather['queries']`` (deterministic rules)."""
    q = gather.get("queries") or {}
    pod_status = q.get("pod_status") or {}
    events_q = q.get("events_for_pod") or {}
    insp_q = q.get("inspections_for_pod") or {}

    cid = gather["cluster_id"]
    ns = gather["namespace"]
    pname = gather["pod_name"]
    pid = gather["pod_entity_id"]
    tid = _active_tenant_id(tenant_id)

    issues: list[str] = []
    actions: list[str] = []
    severity = "ok"

    if pod_status.get("found"):
        status = str((pod_status.get("properties") or {}).get("status", ""))
        if status == "CrashLoopBackOff":
            issues.append("CrashLoop")
            actions.append("restart_pod")
            severity = _max_severity(severity, "critical")

    for ev in events_q.get("events") or []:
        reason = str(ev.get("reason", ""))
        message = str(ev.get("message", ""))

        if "BackOff" in reason:
            issues.append("CrashLoop")
            actions.append("restart_pod")
            severity = _max_severity(severity, "critical")
        if reason == "FailedScheduling":
            issues.append("SchedulingFailure")
            actions.append("check_node_capacity")
            severity = _max_severity(severity, "warning")
        if "OOM" in reason.upper() or "OOM" in message.upper():
            issues.append("OOM")
            actions.append("scale_up")
            severity = _max_severity(severity, "critical")

    for insp in insp_q.get("inspections") or []:
        st = str(insp.get("status", "")).lower()
        if st and st not in _OK_INSPECTION:
            issues.append("InspectionFailed")
            actions.append("run_inspection")
            severity = _max_severity(severity, "warning")

    warning_count = sum(
        1
        for e in events_q.get("events") or []
        if str(e.get("type", "")).lower() == "warning"
    )
    if warning_count and not issues:
        issues.append("WarningEvents")
        actions.append("review_events")
        severity = "warning"

    issues = _dedupe_stable(issues)
    actions = _dedupe_stable(actions)

    if not issues:
        severity = "ok"

    return DiagnosisReport(
        cluster_id=cid,
        namespace=ns,
        pod_name=pname,
        pod_id=pid,
        tenant_id=tid,
        issues=issues,
        recommended_actions=actions,
        severity=severity,
        diagnosis_source="rules_v1",
        ok=True,
        error=None,
        error_stage=None,
    )


def diagnose_from_gather_dict(
    gather: dict[str, Any],
    *,
    tenant_id: str | None = None,
) -> DiagnosisReport:
    """Accept wire ``payload.gather`` dict."""
    return diagnose_from_gather(GatherResult(**gather), tenant_id=tenant_id)
