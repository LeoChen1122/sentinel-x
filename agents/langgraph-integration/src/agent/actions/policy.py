"""Execution policy: tenant ACL and action context helpers."""

from __future__ import annotations

from config.tenant_registry import assert_tenant_cluster_access
from agent.types import ActionContext, DiagnosisReport


def action_context_from_diagnosis(diagnosis: DiagnosisReport) -> ActionContext:
    return ActionContext(
        cluster_id=str(diagnosis["cluster_id"]),
        namespace=str(diagnosis["namespace"]),
        pod_name=str(diagnosis["pod_name"]),
        pod_id=str(diagnosis["pod_id"]),
        tenant_id=diagnosis.get("tenant_id"),
    )


def validate_execution_policy(ctx: ActionContext) -> None:
    """Raise ``TenantAccessError`` when tenant cannot act on cluster."""
    tid = ctx.get("tenant_id")
    if tid is not None and str(tid).strip():
        assert_tenant_cluster_access(str(tid).strip(), ctx["cluster_id"])
