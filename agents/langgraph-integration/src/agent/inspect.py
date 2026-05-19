"""Orchestration: graph payload → inspection report."""

from __future__ import annotations

from typing import Any

from agent.gather import gather_subgraph
from agent.narrative import build_report
from agent.types import InspectionReport


def build_inspection_report(
    payload: dict[str, Any],
    *,
    cluster_id: str,
    namespace: str,
    pod_name: str,
    tenant_id: str | None = None,
    use_llm: bool | None = None,
) -> InspectionReport:
    """Pure function: gather subgraph + narrative (template or LLM polish)."""
    _ = tenant_id  # phase C ACL
    gather = gather_subgraph(
        payload,
        cluster_id=cluster_id,
        namespace=namespace,
        pod_name=pod_name,
    )
    return build_report(gather, use_llm=use_llm)
