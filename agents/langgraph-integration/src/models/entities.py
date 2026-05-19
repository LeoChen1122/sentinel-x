"""Graph entity / edge contracts for MCP → LangGraph (step 2).

MCP tool contract: ``{"query": str, "results": list[dict], "cluster_id": str}`` (phase 4-0).

MCP row → graph property mapping
---------------------------------

**Pod** (``k8s_get_pods`` / ``normalize_pod_list``):

| Graph property       | MCP ``results[]`` row | Notes                          |
|----------------------|------------------------|--------------------------------|
| name                 | name                   | required in row                |
| status               | status                 | Pod phase / Unknown            |
| namespace            | —                      | from tool arg ``namespace``    |
| labels               | —                      | optional; future normalize     |
| creationTimestamp    | —                      | optional; future normalize     |

**Event** (``k8s_get_events`` / ``normalize_event_list``):

| Graph property   | MCP row field   |
|------------------|-----------------|
| type             | type            |
| reason           | reason          |
| message          | message         |
| object_kind      | object_kind     |
| object_name      | object_name     |
| namespace        | namespace       |
| count            | count           |
| last_timestamp   | last_timestamp  |

**Node** (optional; not from current K8s MCP list tools):

| Graph property | Source                    |
|----------------|---------------------------|
| name           | Pod spec.nodeName / API   |

**Inspection** (optional; future inspection MCP):

| Graph property | Field      |
|----------------|------------|
| timestamp      | timestamp  |
| node           | node       |
| status         | status     |
| summary        | summary    |

Relations (internal kind ↔ wire ``relation``)
-----------------------------------------------

| Guide / internal ``kind`` | ``target_type`` | wire ``RelationType`` |
|---------------------------|-----------------|------------------------|
| ``emits`` (Pod→Event)     | —               | ``has_event``          |
| ``scheduled_on``          | —               | ``scheduled_on``       |
| ``inspects`` (→Pod)       | ``pod``         | ``inspects_pod``       |
| ``inspects`` (→Node)      | ``node``        | ``inspects_node``      |
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, NotRequired, TypedDict

logger = logging.getLogger(__name__)


class EntityType(StrEnum):
    POD = "pod"
    EVENT = "event"
    NODE = "node"
    INSPECTION = "inspection"


class RelationKind(StrEnum):
    """Internal relation standard (Adapter logic)."""

    EMITS = "emits"
    SCHEDULED_ON = "scheduled_on"
    INSPECTS = "inspects"


class RelationType(StrEnum):
    """Wire / serialized relation values (payload & storage)."""

    HAS_EVENT = "has_event"
    SCHEDULED_ON = "scheduled_on"
    INSPECTS_POD = "inspects_pod"
    INSPECTS_NODE = "inspects_node"


def wire_relation(
    kind: RelationKind,
    *,
    target_type: EntityType | None = None,
) -> RelationType:
    """Map internal ``RelationKind`` (+ optional inspect target) to wire ``RelationType``."""
    if kind is RelationKind.EMITS:
        return RelationType.HAS_EVENT
    if kind is RelationKind.SCHEDULED_ON:
        return RelationType.SCHEDULED_ON
    if kind is RelationKind.INSPECTS:
        if target_type is EntityType.POD:
            return RelationType.INSPECTS_POD
        if target_type is EntityType.NODE:
            return RelationType.INSPECTS_NODE
        raise ValueError("INSPECTS requires target_type POD or NODE")
    raise ValueError(f"unknown RelationKind: {kind}")


def relation_kind_from_wire(
    relation: RelationType,
) -> tuple[RelationKind, EntityType | None]:
    """Decode wire ``RelationType`` back to internal kind + inspect target."""
    if relation is RelationType.HAS_EVENT:
        return RelationKind.EMITS, None
    if relation is RelationType.SCHEDULED_ON:
        return RelationKind.SCHEDULED_ON, None
    if relation is RelationType.INSPECTS_POD:
        return RelationKind.INSPECTS, EntityType.POD
    if relation is RelationType.INSPECTS_NODE:
        return RelationKind.INSPECTS, EntityType.NODE
    raise ValueError(f"unknown RelationType: {relation}")


class McpPodRow(TypedDict, total=False):
    """One row from ``k8s_get_pods`` → ``results[]``."""

    name: str
    status: str


class McpEventRow(TypedDict, total=False):
    """One row from ``k8s_get_events`` → ``results[]``."""

    type: str
    reason: str
    message: str
    object_kind: str
    object_name: str
    namespace: str
    count: int
    last_timestamp: str


class PodProperties(TypedDict):
    name: str
    namespace: str
    status: str
    labels: NotRequired[dict[str, str]]
    creationTimestamp: NotRequired[str]


class EventProperties(TypedDict, total=False):
    namespace: str
    object_kind: str
    object_name: str
    reason: str
    type: str
    message: str
    count: int
    last_timestamp: str


class NodeProperties(TypedDict):
    name: str
    labels: NotRequired[dict[str, str]]


class InspectionProperties(TypedDict):
    timestamp: str
    node: str
    status: str
    summary: str


@dataclass(frozen=True, slots=True)
class GraphEntity:
    type: EntityType
    id: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "id": self.id,
            "properties": dict(self.properties),
        }


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source_id: str
    target_id: str
    kind: RelationKind
    relation: RelationType
    target_type: EntityType | None = None

    def to_dict(self, *, wire_only: bool = False) -> dict[str, Any]:
        out: dict[str, Any] = {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation.value,
        }
        if not wire_only:
            out["kind"] = self.kind.value
            if self.target_type is not None:
                out["target_type"] = self.target_type.value
        return out


def _make_edge(
    source_id: str,
    target_id: str,
    kind: RelationKind,
    *,
    target_type: EntityType | None = None,
) -> GraphEdge:
    return GraphEdge(
        source_id=source_id,
        target_id=target_id,
        kind=kind,
        relation=wire_relation(kind, target_type=target_type),
        target_type=target_type,
    )


@dataclass
class GraphBatch:
    entities: list[GraphEntity] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def to_dict(self, *, wire_only: bool = False) -> dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "edges": [e.to_dict(wire_only=wire_only) for e in self.edges],
        }

    @classmethod
    def from_pods_events(
        cls,
        pods_mcp: dict[str, Any],
        events_mcp: dict[str, Any],
        namespace: str,
        *,
        cluster_id: str | None = None,
        tenant_id: str | None = None,
        link_pod_events: bool = True,
    ) -> GraphBatch:
        """Build entities and Pod→Event edges from MCP ``{query, results}`` payloads."""
        from models.scope import resolve_cluster_id

        cid = resolve_cluster_id(pods_mcp, events_mcp, cluster_id=cluster_id)
        batch = cls()
        entity_by_id: dict[str, GraphEntity] = {}
        pod_by_key: dict[tuple[str, str], GraphEntity] = {}

        for row in pods_mcp.get("results") or []:
            if not isinstance(row, dict):
                logger.warning("Skipping pod row that is not a dict: %r", row)
                continue
            name = row.get("name")
            if name is None or not str(name).strip():
                logger.warning("Skipping pod row missing name: %r", row)
                continue
            ent = entity_from_pod_row(
                row, namespace, cluster_id=cid, tenant_id=tenant_id
            )
            entity_by_id[ent.id] = ent
            pod_by_key[(ent.properties["namespace"], ent.properties["name"])] = ent

        for row in events_mcp.get("results") or []:
            ent = entity_from_event_row(row, cluster_id=cid, tenant_id=tenant_id)
            entity_by_id[ent.id] = ent
            if not link_pod_events:
                continue
            if str(ent.properties.get("object_kind") or "") != "Pod":
                continue
            pod_key = (
                str(ent.properties.get("namespace") or namespace).strip(),
                str(ent.properties.get("object_name") or "").strip(),
            )
            pod_ent = pod_by_key.get(pod_key)
            if pod_ent is None:
                continue
            batch.edges.append(edge_pod_to_event(pod_ent.id, ent.id))

        batch.entities = list(entity_by_id.values())
        return batch


def entity_from_pod_row(
    row: McpPodRow | dict[str, Any],
    namespace: str,
    *,
    cluster_id: str,
    tenant_id: str | None = None,
    labels: dict[str, str] | None = None,
    creation_timestamp: str | None = None,
) -> GraphEntity:
    from models.ids import pod_id
    from models.scope import stamp_scope

    name = str(row["name"]).strip()
    props: PodProperties = {
        "name": name,
        "namespace": namespace.strip(),
        "status": str(row.get("status", "Unknown")),
    }
    out: dict[str, Any] = dict(props)
    if labels:
        out["labels"] = dict(labels)
    if creation_timestamp:
        out["creationTimestamp"] = creation_timestamp
    return GraphEntity(
        type=EntityType.POD,
        id=pod_id(cluster_id, namespace, name),
        properties=stamp_scope(out, cluster_id=cluster_id, tenant_id=tenant_id),
    )


def entity_from_event_row(
    row: McpEventRow | dict[str, Any],
    *,
    cluster_id: str,
    tenant_id: str | None = None,
) -> GraphEntity:
    from models.ids import event_id
    from models.scope import stamp_scope

    namespace = str(row.get("namespace") or "default").strip()
    object_kind = str(row.get("object_kind") or "Unknown").strip()
    object_name = str(row.get("object_name") or "unknown").strip()
    reason = str(row.get("reason") or "Unknown").strip()
    last_ts = row.get("last_timestamp")
    last_ts_str = str(last_ts).strip() if last_ts is not None else None

    props: dict[str, Any] = {
        "namespace": namespace,
        "object_kind": object_kind,
        "object_name": object_name,
        "reason": reason,
    }
    for key in ("type", "message", "count", "last_timestamp"):
        if key in row and row[key] is not None:
            props[key] = row[key]

    eid = event_id(
        cluster_id=cluster_id,
        namespace=namespace,
        object_kind=object_kind,
        object_name=object_name,
        reason=reason,
        last_timestamp=last_ts_str,
        message=str(row.get("message") or "") if row.get("message") else None,
    )
    return GraphEntity(
        type=EntityType.EVENT,
        id=eid,
        properties=stamp_scope(props, cluster_id=cluster_id, tenant_id=tenant_id),
    )


def entity_from_node(
    name: str,
    *,
    cluster_id: str,
    tenant_id: str | None = None,
    labels: dict[str, str] | None = None,
) -> GraphEntity:
    from models.ids import node_id
    from models.scope import stamp_scope

    props: dict[str, Any] = {"name": name.strip()}
    if labels:
        props["labels"] = dict(labels)
    return GraphEntity(
        type=EntityType.NODE,
        id=node_id(cluster_id, name),
        properties=stamp_scope(props, cluster_id=cluster_id, tenant_id=tenant_id),
    )


def entity_from_inspection(
    timestamp: str,
    node: str,
    status: str,
    summary: str,
    *,
    cluster_id: str,
    tenant_id: str | None = None,
) -> GraphEntity:
    from models.ids import inspection_id
    from models.scope import stamp_scope

    props: InspectionProperties = {
        "timestamp": timestamp.strip(),
        "node": node.strip(),
        "status": status.strip(),
        "summary": summary.strip(),
    }
    return GraphEntity(
        type=EntityType.INSPECTION,
        id=inspection_id(cluster_id, timestamp, node),
        properties=stamp_scope(
            dict(props), cluster_id=cluster_id, tenant_id=tenant_id
        ),
    )


def edge_pod_to_event(pod_entity_id: str, event_entity_id: str) -> GraphEdge:
    return _make_edge(pod_entity_id, event_entity_id, RelationKind.EMITS)


def edge_pod_to_node(pod_entity_id: str, node_entity_id: str) -> GraphEdge:
    return _make_edge(
        pod_entity_id, node_entity_id, RelationKind.SCHEDULED_ON
    )


def edge_inspection_to_pod(inspection_entity_id: str, pod_entity_id: str) -> GraphEdge:
    return _make_edge(
        inspection_entity_id,
        pod_entity_id,
        RelationKind.INSPECTS,
        target_type=EntityType.POD,
    )


def edge_inspection_to_node(inspection_entity_id: str, node_entity_id: str) -> GraphEdge:
    return _make_edge(
        inspection_entity_id,
        node_entity_id,
        RelationKind.INSPECTS,
        target_type=EntityType.NODE,
    )
