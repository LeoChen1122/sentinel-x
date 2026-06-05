"""Build skill Markdown from inspect gather + diagnosis."""

from __future__ import annotations

from typing import TYPE_CHECKING

from skills.fingerprint import skill_fingerprint
from skills.parse import compose_skill_markdown

if TYPE_CHECKING:
    from agent.types import DiagnosisReport, GatherResult

ISSUE_SKILL_NAMES: dict[str, str] = {
    "CrashLoop": "fix-crashloop-restart",
    "OOM": "fix-pod-oom",
    "SchedulingFailure": "fix-scheduling-failure",
    "InspectionFailed": "fix-inspection-failed",
    "WarningEvents": "review-warning-events",
}

ISSUE_SYMPTOMS: dict[str, str] = {
    "CrashLoop": "CrashLoopBackOff",
    "OOM": "Pod terminated with exit code 137 (OOMKilled)",
    "SchedulingFailure": "FailedScheduling",
    "InspectionFailed": "Inspection not ok",
    "WarningEvents": "Warning events on pod",
}

ISSUE_RISK: dict[str, str] = {
    "CrashLoop": "critical",
    "OOM": "critical",
    "SchedulingFailure": "warning",
    "InspectionFailed": "warning",
    "WarningEvents": "warning",
}


def skill_name_from_diagnosis(diagnosis: DiagnosisReport) -> str:
    issues = diagnosis.get("issues") or []
    if not issues:
        return "skill-unknown"
    primary = str(issues[0])
    return ISSUE_SKILL_NAMES.get(primary, f"fix-{primary.lower().replace(' ', '-')}")


def _pod_status_symptom(gather: GatherResult) -> str:
    q = gather.get("queries") or {}
    pod_status = q.get("pod_status") or {}
    if pod_status.get("found"):
        props = pod_status.get("properties") or {}
        status = str(props.get("status", "")).strip()
        if status:
            return status
    issues = []
    return ""


def build_skill_markdown(
    gather: GatherResult,
    diagnosis: DiagnosisReport,
    *,
    verified: bool = False,
) -> str:
    issues = [str(i) for i in (diagnosis.get("issues") or [])]
    actions = [str(a) for a in (diagnosis.get("recommended_actions") or [])]
    name = skill_name_from_diagnosis(diagnosis)
    primary_issue = issues[0] if issues else "unknown"
    symptom = _pod_status_symptom(gather) or ISSUE_SYMPTOMS.get(primary_issue, primary_issue)
    fp = skill_fingerprint(issues, actions)
    tags = ["k8s"] + issues[:3]

    fm = {
        "name": name,
        "version": "1.0",
        "fingerprint": fp,
        "tags": tags,
        "symptom": symptom,
        "issues": issues,
        "recommended_actions": actions,
        "risk_level": ISSUE_RISK.get(primary_issue, diagnosis.get("severity", "warning")),
        "verified": verified,
        "hit_count": 1,
        "source_count": 1,
    }

    problem_lines = [f"Detected issue(s): {', '.join(issues) or 'unknown'}."]
    if symptom:
        problem_lines.append(f"Symptom: {symptom}.")

    resolution_lines = [
        "1. Review container logs and recent events",
    ]
    for idx, action in enumerate(actions, start=2):
        resolution_lines.append(f"{idx}. {action} (dry-run in W5)")

    body = "\n".join(
        [
            "# Problem",
            "\n".join(problem_lines),
            "",
            "# Resolution",
            "\n".join(resolution_lines),
            "",
            "# Evidence",
            "Observed on:",
            f"- cluster: {gather['cluster_id']}",
            f"- namespace: {gather['namespace']}",
            f"- pod: {gather['pod_name']}",
            f"- severity: {diagnosis.get('severity', 'ok')}",
            f"- diagnosis_source: {diagnosis.get('diagnosis_source', 'rules_v1')}",
            "",
        ]
    )
    return compose_skill_markdown(fm, body)
