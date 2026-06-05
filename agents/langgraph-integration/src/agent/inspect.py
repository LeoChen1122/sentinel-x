"""Orchestration: graph payload → inspection report + diagnosis + actions."""

from __future__ import annotations

from typing import Any

from agent.diagnose import diagnose_from_gather
from agent.execute import execute_recommended_actions
from agent.gather import gather_subgraph
from agent.llm import polish_inspection_report, resolve_use_llm
from agent.narrative import _append_skill_matches, build_report_template
from agent.types import (
    DiagnosisReport,
    ExecutionResult,
    GatherResult,
    InspectionReport,
    OnErrorMode,
)
from models.ids import pod_id


class InspectPipelineError(Exception):
    """Raised when ``on_error='raise'`` and a pipeline stage fails."""

    def __init__(self, stage: str, cause: BaseException) -> None:
        self.stage = stage
        self.cause = cause
        super().__init__(f"inspect pipeline failed at {stage}: {cause}")


def _scope(
    *,
    cluster_id: str,
    namespace: str,
    pod_name: str,
    tenant_id: str | None,
) -> dict[str, str | None]:
    cid = cluster_id.strip()
    ns = namespace.strip()
    pname = pod_name.strip()
    tid = tenant_id.strip() if tenant_id and str(tenant_id).strip() else None
    return {
        "cluster_id": cid,
        "namespace": ns,
        "pod_name": pname,
        "tenant_id": tid,
        "pod_entity_id": pod_id(cid, ns, pname),
    }


def _resolve_gather(
    payload: dict[str, Any],
    scope: dict[str, str | None],
    gather: GatherResult | None,
) -> GatherResult:
    if gather is not None:
        return gather
    return gather_subgraph(
        payload,
        cluster_id=str(scope["cluster_id"]),
        namespace=str(scope["namespace"]),
        pod_name=str(scope["pod_name"]),
        tenant_id=scope["tenant_id"],
    )


def _error_narrative(scope: dict[str, str | None], stage: str, exc: BaseException) -> InspectionReport:
    cid = str(scope["cluster_id"])
    ns = str(scope["namespace"])
    pname = str(scope["pod_name"])
    pid = str(scope["pod_entity_id"])
    msg = str(exc)
    return InspectionReport(
        cluster_id=cid,
        namespace=ns,
        pod_name=pname,
        pod_entity_id=pid,
        markdown=f"# Inspection error\n\nStage `{stage}` failed: {msg}\n",
        sections=[],
        linked_events=[],
        linked_pods=[],
        linked_inspections=[],
        summary=f"Inspection failed at {stage}: {msg}",
        narrative_source="error",
        ok=False,
        error=msg,
        error_stage=stage,
        llm_error=None,
    )


def _error_diagnosis(scope: dict[str, str | None], stage: str, exc: BaseException) -> DiagnosisReport:
    msg = str(exc)
    return DiagnosisReport(
        cluster_id=str(scope["cluster_id"]),
        namespace=str(scope["namespace"]),
        pod_name=str(scope["pod_name"]),
        pod_id=str(scope["pod_entity_id"]),
        tenant_id=scope["tenant_id"],
        issues=[],
        recommended_actions=[],
        severity="ok",
        diagnosis_source="error",
        ok=False,
        error=msg,
        error_stage=stage,
    )


def _error_execution(stage: str, exc: BaseException, *, dry_run: bool) -> ExecutionResult:
    return ExecutionResult(
        dry_run=dry_run,
        actions_taken=[],
        skipped=[],
        ok=False,
        error=str(exc),
        error_stage=stage,
    )


def _normalize_stage_output(report: dict[str, Any], *, ok: bool = True) -> dict[str, Any]:
    """Ensure ``ok`` / ``error`` / ``error_stage`` are present on stage outputs."""
    report.setdefault("ok", ok)
    if ok:
        report.setdefault("error", None)
        report.setdefault("error_stage", None)
    return report


def _run_stage(
    stage: str,
    on_error: OnErrorMode,
    fn: Any,
    *args: Any,
    **kwargs: Any,
) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        if on_error == "raise":
            raise InspectPipelineError(stage, exc) from exc
        return exc


def build_inspection_with_diagnosis(
    payload: dict[str, Any],
    *,
    cluster_id: str,
    namespace: str,
    pod_name: str,
    tenant_id: str | None = None,
    use_llm: bool | None = None,
    dry_run: bool = True,
    gather: GatherResult | None = None,
    on_error: OnErrorMode = "raise",
) -> tuple[InspectionReport, DiagnosisReport, ExecutionResult]:
    """Gather once → template → diagnose → optional LLM polish → execute.

    Pass a pre-built ``gather`` to skip re-querying the graph (e.g. after
    LangGraph ``gather`` node). Set ``on_error='mark'`` for error fields instead
    of raising.
    """
    scope = _scope(
        cluster_id=cluster_id,
        namespace=namespace,
        pod_name=pod_name,
        tenant_id=tenant_id,
    )

    gather_out = _run_stage(
        "gather",
        on_error,
        _resolve_gather,
        payload,
        scope,
        gather,
    )
    if isinstance(gather_out, BaseException):
        exc = gather_out
        return (
            _error_narrative(scope, "gather", exc),
            _error_diagnosis(scope, "gather", exc),
            _error_execution("gather", exc, dry_run=dry_run),
        )

    diagnosis_out = _run_stage(
        "diagnose",
        on_error,
        diagnose_from_gather,
        gather_out,
        tenant_id=scope["tenant_id"],
    )
    if isinstance(diagnosis_out, BaseException):
        exc = diagnosis_out
        return (
            _error_narrative(scope, "diagnose", exc),
            _error_diagnosis(scope, "diagnose", exc),
            _error_execution("diagnose", exc, dry_run=dry_run),
        )
    diagnosis = DiagnosisReport(**_normalize_stage_output(dict(diagnosis_out)))

    skill_matches = []
    if diagnosis.get("issues"):
        from skills.retrieve import retrieve_for_diagnosis

        skill_matches = retrieve_for_diagnosis(diagnosis)

    try:
        if resolve_use_llm(use_llm):
            narrative_template = build_report_template(gather_out, skill_matches=None)
        else:
            narrative_template = build_report_template(
                gather_out, skill_matches=skill_matches
            )
    except Exception as exc:
        if on_error == "raise":
            raise InspectPipelineError("narrative", exc) from exc
        return (
            _error_narrative(scope, "narrative", exc),
            diagnosis,
            _error_execution("narrative", exc, dry_run=dry_run),
        )

    if resolve_use_llm(use_llm):
        narrative_out = _run_stage(
            "narrative",
            on_error,
            polish_inspection_report,
            narrative_template,
            gather_out,
            diagnosis=diagnosis,
        )
        if isinstance(narrative_out, BaseException):
            exc = narrative_out
            return (
                _error_narrative(scope, "narrative", exc),
                diagnosis,
                _error_execution("narrative", exc, dry_run=dry_run),
            )
        narrative = InspectionReport(**_normalize_stage_output(dict(narrative_out)))
        narrative = _append_skill_matches(narrative, skill_matches or None)
    else:
        narrative = InspectionReport(**_normalize_stage_output(dict(narrative_template)))

    execution_out = _run_stage(
        "execute",
        on_error,
        execute_recommended_actions,
        diagnosis,
        dry_run=dry_run,
    )
    if isinstance(execution_out, BaseException):
        exc = execution_out
        return (
            narrative,
            diagnosis,
            _error_execution("execute", exc, dry_run=dry_run),
        )
    execution: ExecutionResult = execution_out
    execution.setdefault("ok", True)
    execution.setdefault("error", None)
    execution.setdefault("error_stage", None)
    return narrative, diagnosis, execution


def build_inspection_report(
    payload: dict[str, Any],
    *,
    cluster_id: str,
    namespace: str,
    pod_name: str,
    tenant_id: str | None = None,
    use_llm: bool | None = None,
    gather: GatherResult | None = None,
    on_error: OnErrorMode = "raise",
) -> InspectionReport:
    """Gather subgraph + narrative only; reuses ``gather`` when provided."""
    scope = _scope(
        cluster_id=cluster_id,
        namespace=namespace,
        pod_name=pod_name,
        tenant_id=tenant_id,
    )
    gather_out = _run_stage(
        "gather",
        on_error,
        _resolve_gather,
        payload,
        scope,
        gather,
    )
    if isinstance(gather_out, BaseException):
        return _error_narrative(scope, "gather", gather_out)

    try:
        template = build_report_template(gather_out)
    except Exception as exc:
        if on_error == "raise":
            raise InspectPipelineError("narrative", exc) from exc
        return _error_narrative(scope, "narrative", exc)
    if not resolve_use_llm(use_llm):
        return InspectionReport(**_normalize_stage_output(dict(template)))
    narrative_out = _run_stage(
        "narrative",
        on_error,
        polish_inspection_report,
        template,
        gather_out,
        diagnosis=None,
    )
    if isinstance(narrative_out, BaseException):
        return _error_narrative(scope, "narrative", narrative_out)
    return InspectionReport(**_normalize_stage_output(dict(narrative_out)))
