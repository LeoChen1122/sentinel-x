"""Trigger one LangGraph inspect run (thread-only, W7)."""

from __future__ import annotations

from typing import Any, TypedDict

from clients.langgraph_client import (
    get_inspect_outputs_from_stream,
    get_langgraph_client,
    stream_sentinel_run,
)
from models.scope import resolve_langgraph_thread_id


class InspectTriggerResult(TypedDict, total=False):
    ok: bool
    cluster_id: str
    namespace: str
    pod_name: str
    thread_id: str
    dry_run: bool
    issues: list[str]
    execution: dict[str, Any]
    sandbox_result: dict[str, Any]
    skill_verification: dict[str, Any]
    skill_record: dict[str, Any]
    narrative_summary: str
    error: str | None


def trigger_inspect(
    *,
    cluster_id: str,
    namespace: str,
    pod_name: str,
    dry_run: bool = True,
    thread_id: str | None = None,
    tenant_id: str | None = None,
    client: Any | None = None,
) -> InspectTriggerResult:
    """Run inspect on LangGraph (no mock ingest). Returns pipeline outputs subset."""
    tid = resolve_langgraph_thread_id(
        thread_id=thread_id,
        cluster_id=cluster_id,
        tenant_id=tenant_id,
    )
    payload: dict[str, Any] = {
        "inspect": {
            "cluster_id": cluster_id,
            "namespace": namespace,
            "pod_name": pod_name,
            "dry_run": dry_run,
        },
    }
    if tenant_id:
        payload["inspect"]["tenant_id"] = tenant_id

    lg = client or get_langgraph_client()
    try:
        chunks = list(stream_sentinel_run(payload, client=lg, thread_id=tid))
    except Exception as exc:
        return InspectTriggerResult(
            ok=False,
            cluster_id=cluster_id,
            namespace=namespace,
            pod_name=pod_name,
            thread_id=tid,
            dry_run=dry_run,
            error=str(exc),
        )

    outputs = get_inspect_outputs_from_stream(chunks)
    diagnosis = outputs.get("diagnosis") or {}
    execution = outputs.get("execution") or {}
    narrative = outputs.get("narrative") or {}
    issues = list(diagnosis.get("issues") or [])
    ok = bool(issues) and (
        bool(execution.get("actions_taken")) or bool(execution.get("skipped"))
    )
    if execution.get("ok") is False and execution.get("error"):
        ok = False

    return InspectTriggerResult(
        ok=ok,
        cluster_id=cluster_id,
        namespace=namespace,
        pod_name=pod_name,
        thread_id=tid,
        dry_run=dry_run,
        issues=issues,
        execution=dict(execution) if isinstance(execution, dict) else {},
        sandbox_result=dict(outputs.get("sandbox_result") or {})
        if isinstance(outputs.get("sandbox_result"), dict)
        else {},
        skill_verification=dict(outputs.get("skill_verification") or {})
        if isinstance(outputs.get("skill_verification"), dict)
        else {},
        skill_record=dict(outputs.get("skill_record") or {})
        if isinstance(outputs.get("skill_record"), dict)
        else {},
        narrative_summary=str(narrative.get("summary") or ""),
        error=str(execution.get("error") or "") or None,
    )
