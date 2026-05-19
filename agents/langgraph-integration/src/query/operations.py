"""Query operations over graph payload (step 6 / phase 4-0 cluster scope)."""

from __future__ import annotations

from typing import Any

from models.entities import EntityType, RelationType
from query.graph_view import GraphView


class QueryError(ValueError):
    """Unknown query op or missing parameters."""


def _require_cluster_id(cluster_id: str | None) -> str:
    if cluster_id is None or not str(cluster_id).strip():
        raise QueryError("cluster_id is required")
    return str(cluster_id).strip()


def _props_cluster(props: dict[str, Any]) -> str:
    return str(props.get("cluster_id", ""))


def run_query(payload: dict[str, Any], op: str, **params: Any) -> dict[str, Any]:
    """Run ``op`` against ``payload`` with ``entities`` / ``edges``."""
    view = GraphView.from_payload(payload)
    if op == "list_pods":
        return _list_pods(view, params.get("cluster_id"), params.get("namespace"))
    if op == "pod_status":
        return _pod_status(
            view,
            _require_cluster_id(params.get("cluster_id")),
            params.get("namespace"),
            params.get("name"),
        )
    if op == "events_for_pod":
        return _events_for_pod(
            view,
            _require_cluster_id(params.get("cluster_id")),
            params.get("namespace"),
            params.get("name"),
        )
    if op == "inspections_summary":
        return _inspections_summary(view, params.get("cluster_id"))
    if op == "list_events":
        return _list_events(view, params.get("cluster_id"), params.get("namespace"))
    if op == "inspections_for_pod":
        return _inspections_for_pod(
            view,
            _require_cluster_id(params.get("cluster_id")),
            params.get("namespace"),
            params.get("name"),
        )
    raise QueryError(f"unknown query op: {op}")


def _list_pods(
    view: GraphView, cluster_id: str | None, namespace: str | None
) -> dict[str, Any]:
    pods = view.entities_by_type(EntityType.POD.value)
    if cluster_id is not None:
        cid = str(cluster_id).strip()
        pods = [p for p in pods if _props_cluster(p.get("properties") or {}) == cid]
    if namespace is not None:
        ns = str(namespace).strip()
        pods = [p for p in pods if str(p.get("properties", {}).get("namespace")) == ns]
    rows = []
    for p in pods:
        props = p.get("properties") or {}
        rows.append(
            {
                "id": p.get("id"),
                "cluster_id": props.get("cluster_id"),
                "name": props.get("name"),
                "namespace": props.get("namespace"),
                "status": props.get("status"),
            }
        )
    return {"op": "list_pods", "count": len(rows), "pods": rows}


def _pod_status(
    view: GraphView,
    cluster_id: str,
    namespace: str | None,
    name: str | None,
) -> dict[str, Any]:
    if not namespace or not name:
        raise QueryError("pod_status requires namespace and name")
    pid = view.pod_entity_id(cluster_id, str(namespace), str(name))
    ent = view.entities.get(pid)
    if ent is None:
        return {
            "op": "pod_status",
            "found": False,
            "cluster_id": cluster_id,
            "namespace": namespace,
            "name": name,
        }
    return {
        "op": "pod_status",
        "found": True,
        "id": pid,
        "cluster_id": cluster_id,
        "properties": dict(ent.get("properties") or {}),
    }


def _events_for_pod(
    view: GraphView,
    cluster_id: str,
    namespace: str | None,
    name: str | None,
) -> dict[str, Any]:
    if not namespace or not name:
        raise QueryError("events_for_pod requires namespace and name")
    pid = view.pod_entity_id(cluster_id, str(namespace), str(name))
    events = view.events_for_pod_id(pid)
    rows = []
    for ev in events:
        props = ev.get("properties") or {}
        rows.append(
            {
                "id": ev.get("id"),
                "type": props.get("type"),
                "reason": props.get("reason"),
                "message": props.get("message"),
                "last_timestamp": props.get("last_timestamp"),
            }
        )
    return {
        "op": "events_for_pod",
        "pod_id": pid,
        "cluster_id": cluster_id,
        "namespace": namespace,
        "name": name,
        "count": len(rows),
        "events": rows,
    }


def _inspections_summary(
    view: GraphView, cluster_id: str | None
) -> dict[str, Any]:
    inspections = view.entities_by_type(EntityType.INSPECTION.value)
    if cluster_id is not None:
        cid = str(cluster_id).strip()
        inspections = [
            i
            for i in inspections
            if _props_cluster(i.get("properties") or {}) == cid
        ]
    rows = []
    for insp in inspections:
        props = insp.get("properties") or {}
        iid = str(insp.get("id", ""))
        linked_pods = [
            e["target_id"]
            for e in view.edges
            if e.get("relation") == RelationType.INSPECTS_POD.value
            and str(e.get("source_id")) == iid
        ]
        linked_nodes = [
            e["target_id"]
            for e in view.edges
            if e.get("relation") == RelationType.INSPECTS_NODE.value
            and str(e.get("source_id")) == iid
        ]
        rows.append(
            {
                "id": iid,
                "cluster_id": props.get("cluster_id"),
                "timestamp": props.get("timestamp"),
                "node": props.get("node"),
                "status": props.get("status"),
                "summary": props.get("summary"),
                "linked_pods": linked_pods,
                "linked_nodes": linked_nodes,
            }
        )
    return {"op": "inspections_summary", "count": len(rows), "inspections": rows}


def _list_events(
    view: GraphView, cluster_id: str | None, namespace: str | None
) -> dict[str, Any]:
    events = view.entities_by_type(EntityType.EVENT.value)
    if cluster_id is not None:
        cid = str(cluster_id).strip()
        events = [e for e in events if _props_cluster(e.get("properties") or {}) == cid]
    if namespace is not None:
        ns = str(namespace).strip()
        events = [
            e
            for e in events
            if str((e.get("properties") or {}).get("namespace", "")) == ns
        ]
    rows = []
    for ev in events:
        props = ev.get("properties") or {}
        rows.append(
            {
                "id": ev.get("id"),
                "cluster_id": props.get("cluster_id"),
                "namespace": props.get("namespace"),
                "type": props.get("type"),
                "reason": props.get("reason"),
                "object_kind": props.get("object_kind"),
                "object_name": props.get("object_name"),
                "last_timestamp": props.get("last_timestamp"),
            }
        )
    return {"op": "list_events", "count": len(rows), "events": rows}


def _inspections_for_pod(
    view: GraphView,
    cluster_id: str,
    namespace: str | None,
    name: str | None,
) -> dict[str, Any]:
    if not namespace or not name:
        raise QueryError("inspections_for_pod requires namespace and name")
    pid = view.pod_entity_id(cluster_id, str(namespace), str(name))
    inspection_ids = {
        str(e["source_id"])
        for e in view.edges
        if e.get("relation") == RelationType.INSPECTS_POD.value
        and str(e.get("target_id")) == pid
        and e.get("source_id")
    }
    rows = []
    for iid in sorted(inspection_ids):
        ent = view.entities.get(iid)
        if ent is None:
            continue
        props = ent.get("properties") or {}
        rows.append(
            {
                "id": iid,
                "timestamp": props.get("timestamp"),
                "node": props.get("node"),
                "status": props.get("status"),
                "summary": props.get("summary"),
            }
        )
    return {
        "op": "inspections_for_pod",
        "pod_id": pid,
        "cluster_id": cluster_id,
        "namespace": namespace,
        "name": name,
        "count": len(rows),
        "inspections": rows,
    }
