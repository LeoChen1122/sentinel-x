"""Typed contracts for Agent phase A: gather + inspection narrative."""

from __future__ import annotations

from typing import Any, TypedDict


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


class GatherResult(TypedDict):
    """Output of gather phase (``payload.gather``)."""

    cluster_id: str
    namespace: str
    pod_name: str
    pod_entity_id: str
    subgraph: dict[str, Any]
    queries: dict[str, Any]


class InspectionReport(TypedDict):
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
