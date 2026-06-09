"""Typed contracts for Agent phase A: gather + inspection narrative."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

OnErrorMode = Literal["raise", "mark"]


class LinkedEntity(TypedDict, total=False):
    """Reference to a graph entity by stable id."""

    entity_id: str
    entity_type: str
    relation: str | None
    label: str | None


class ReportSection(TypedDict):
    title: str
    body: str
    linked_entities: list[LinkedEntity]


class InspectRequest(TypedDict, total=False):
    """LangGraph ``payload.inspect`` — narrative scope (not MCP query)."""

    cluster_id: str
    namespace: str
    pod_name: str
    tenant_id: str | None
    use_llm: bool | None
    dry_run: bool | None


class GatherResult(TypedDict):
    """Output of gather phase (``payload.gather``)."""

    cluster_id: str
    namespace: str
    pod_name: str
    pod_entity_id: str
    subgraph: dict[str, Any]
    queries: dict[str, Any]


class InspectionReport(TypedDict, total=False):
    """Final narrative (``payload.narrative``)."""

    cluster_id: str
    namespace: str
    pod_name: str
    pod_entity_id: str
    markdown: str
    sections: list[ReportSection]
    linked_events: list[LinkedEntity]
    linked_pods: list[LinkedEntity]
    linked_inspections: list[LinkedEntity]
    summary: str
    narrative_source: str
    ok: bool
    error: str | None
    error_stage: str | None
    llm_error: str | None


class ActionContext(TypedDict):
    """Scope passed to action handlers (cluster, pod, tenant)."""

    cluster_id: str
    namespace: str
    pod_name: str
    pod_id: str
    tenant_id: str | None


class ActionRecord(TypedDict, total=False):
    """One simulated or executed action from the action layer."""

    action: str
    target: str
    status: str
    message: str


class DiagnosisReport(TypedDict, total=False):
    """Rule-based diagnosis (``payload.diagnosis``)."""

    cluster_id: str
    namespace: str
    pod_name: str
    pod_id: str
    tenant_id: str | None
    issues: list[str]
    recommended_actions: list[str]
    severity: str
    diagnosis_source: str
    ok: bool
    error: str | None
    error_stage: str | None


class ExecutionResult(TypedDict, total=False):
    """Action layer output (``payload.execution``)."""

    dry_run: bool
    sandbox_pending: bool
    actions_taken: list[ActionRecord]
    skipped: list[str]
    ok: bool
    error: str | None
    error_stage: str | None
    execution_source: str


class SandboxRunRecord(TypedDict, total=False):
    """One sandbox kubectl run with audit metadata."""

    action: str
    command: list[str]
    exit_code: int
    status: str
    message: str
    audit_path: str
    run_id: str
    blocked: bool
    stdout: str
    stderr: str


class SandboxVerification(TypedDict, total=False):
    """Post-run verification (e.g. Ready held for N seconds)."""

    pass_: bool
    ready_seconds: int
    message: str
    deployment: str
    checked_pod: str


class SandboxResult(TypedDict, total=False):
    """Sandbox pre-run output (``payload.sandbox_result``)."""

    runs: list[SandboxRunRecord]
    ok: bool
    sandbox_source: str
    blocked: bool
    skipped: bool
    message: str
    verification: SandboxVerification
