"""Query operations over graph payload (step 6 / phase 4-0 cluster scope)."""

from __future__ import annotations

from typing import Any

from config.tenant_registry import TenantAccessError, allowed_clusters, assert_tenant_cluster_access
from models.entities import EntityType, RelationType
from query.graph_view import GraphView


class QueryError(ValueError):
    """Unknown query op or missing parameters."""


def _require_cluster_id(cluster_id: str | None) -> str:
    if cluster_id is None or not str(cluster_id).strip():
        raise QueryError("cluster_id is required")
    return str(cluster_id).strip()


def _active_tenant_id(tenant_id: str | None) -> str | None:
    if tenant_id is None:
        return None
    tid = str(tenant_id).strip()
    return tid if tid else None


def _props_cluster(props: dict[str, Any]) -> str:
    return str(props.get("cluster_id", ""))


def _props_tenant(props: dict[str, Any]) -> str:
    return str(props.get("tenant_id", ""))


def _entity_matches_tenant(ent: dict[str, Any], tenant_id: str) -> bool:
    props = ent.get("properties") or {}
    return _props_tenant(props) == tenant_id


def _acl_cluster(tenant_id: str | None, cluster_id: str | None) -> None:
    tid = _active_tenant_id(tenant_id)
    if tid is None:
        return
    cid = _require_cluster_id(cluster_id)
    assert_tenant_cluster_access(tid, cid)


def run_query(payload: dict[str, Any], op: str, **params: Any) -> dict[str, Any]:
    """Run ``op`` against ``payload`` with ``entities`` / ``edges``."""
    view = GraphView.from_payload(payload)
    tenant_id = params.get("tenant_id")
    if op == "list_clusters_for_tenant":
        return _list_clusters_for_tenant(params.get("tenant_id"))
    if op == "list_pods":
        return _list_pods(
            view, params.get("cluster_id"), params.get("namespace"), tenant_id=tenant_id
        )
    if op == "pod_status":
        cid = _require_cluster_id(params.get("cluster_id"))
        _acl_cluster(tenant_id, cid)
        return _pod_status(
            view,
            cid,
            params.get("namespace"),
            params.get("name"),
            tenant_id=tenant_id,
        )
    if op == "events_for_pod":
        cid = _require_cluster_id(params.get("cluster_id"))
        _acl_cluster(tenant_id, cid)
        return _events_for_pod(
            view,
            cid,
            params.get("namespace"),
            params.get("name"),
            tenant_id=tenant_id,
        )
    if op == "inspections_summary":
        return _inspections_summary(view, params.get("cluster_id"), tenant_id=tenant_id)
    if op == "list_events":
        return _list_events(
            view, params.get("cluster_id"), params.get("namespace"), tenant_id=tenant_id
        )
    if op == "inspections_for_pod":
        cid = _require_cluster_id(params.get("cluster_id"))
        _acl_cluster(tenant_id, cid)
        return _inspections_for_pod(
            view,
            cid,
            params.get("namespace"),
            params.get("name"),
            tenant_id=tenant_id,
        )
    if op == "top_pods_by_cpu":
        return _top_pods_by_cpu(
            view,
            params.get("cluster_id"),
            params.get("namespace"),
            limit=params.get("limit", 10),
            tenant_id=tenant_id,
        )
    if op == "pod_metrics":
        cid = _require_cluster_id(params.get("cluster_id"))
        _acl_cluster(tenant_id, cid)
        return _pod_metrics(
            view,
            cid,
            params.get("namespace"),
            params.get("name"),
            tenant_id=tenant_id,
        )
    raise QueryError(f"unknown query op: {op}")


def _list_clusters_for_tenant(tenant_id: str | None) -> dict[str, Any]:
    tid = _active_tenant_id(tenant_id)
    if tid is None:
        raise QueryError("list_clusters_for_tenant requires tenant_id")
    clusters = allowed_clusters(tid)
    return {"op": "list_clusters_for_tenant", "tenant_id": tid, "clusters": clusters}


def _filter_entities_by_tenant(
    entities: list[dict[str, Any]], tenant_id: str | None
) -> list[dict[str, Any]]:
    tid = _active_tenant_id(tenant_id)
    if tid is None:
        return entities
    return [e for e in entities if _entity_matches_tenant(e, tid)]


def _list_pods(
    view: GraphView,
    cluster_id: str | None,
    namespace: str | None,
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    tid = _active_tenant_id(tenant_id)
    if tid is not None:
        _acl_cluster(tenant_id, cluster_id)
    pods = view.entities_by_type(EntityType.POD.value)
    if cluster_id is not None:
        cid = str(cluster_id).strip()
        pods = [p for p in pods if _props_cluster(p.get("properties") or {}) == cid]
    pods = _filter_entities_by_tenant(pods, tenant_id)
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
                "cpu_cores": props.get("cpu_cores"),
                "memory_bytes": props.get("memory_bytes"),
            }
        )
    return {"op": "list_pods", "count": len(rows), "pods": rows}


def _pod_status(
    view: GraphView,
    cluster_id: str,
    namespace: str | None,
    name: str | None,
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    if not namespace or not name:
        raise QueryError("pod_status requires namespace and name")
    pid = view.pod_entity_id(cluster_id, str(namespace), str(name))
    ent = view.entities.get(pid)
    tid = _active_tenant_id(tenant_id)
    if ent is None or (tid is not None and not _entity_matches_tenant(ent, tid)):
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
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    if not namespace or not name:
        raise QueryError("events_for_pod requires namespace and name")
    pid = view.pod_entity_id(cluster_id, str(namespace), str(name))
    tid = _active_tenant_id(tenant_id)
    pod_ent = view.entities.get(pid)
    if pod_ent is None or (tid is not None and not _entity_matches_tenant(pod_ent, tid)):
        return {
            "op": "events_for_pod",
            "pod_id": pid,
            "cluster_id": cluster_id,
            "namespace": namespace,
            "name": name,
            "count": 0,
            "events": [],
        }
    events = view.events_for_pod_id(pid)
    events = _filter_entities_by_tenant(events, tenant_id)
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
    view: GraphView,
    cluster_id: str | None,
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    tid = _active_tenant_id(tenant_id)
    if tid is not None:
        _acl_cluster(tenant_id, cluster_id)
    inspections = view.entities_by_type(EntityType.INSPECTION.value)
    if cluster_id is not None:
        cid = str(cluster_id).strip()
        inspections = [
            i
            for i in inspections
            if _props_cluster(i.get("properties") or {}) == cid
        ]
    inspections = _filter_entities_by_tenant(inspections, tenant_id)
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
    view: GraphView,
    cluster_id: str | None,
    namespace: str | None,
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    tid = _active_tenant_id(tenant_id)
    if tid is not None:
        _acl_cluster(tenant_id, cluster_id)
    events = view.entities_by_type(EntityType.EVENT.value)
    if cluster_id is not None:
        cid = str(cluster_id).strip()
        events = [e for e in events if _props_cluster(e.get("properties") or {}) == cid]
    events = _filter_entities_by_tenant(events, tenant_id)
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
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    if not namespace or not name:
        raise QueryError("inspections_for_pod requires namespace and name")
    pid = view.pod_entity_id(cluster_id, str(namespace), str(name))
    tid = _active_tenant_id(tenant_id)
    pod_ent = view.entities.get(pid)
    if pod_ent is None or (tid is not None and not _entity_matches_tenant(pod_ent, tid)):
        return {
            "op": "inspections_for_pod",
            "pod_id": pid,
            "cluster_id": cluster_id,
            "namespace": namespace,
            "name": name,
            "count": 0,
            "inspections": [],
        }
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
        if tid is not None and not _entity_matches_tenant(ent, tid):
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


def _metric_float(props: dict[str, Any], key: str) -> float | None:
    raw = props.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _top_pods_by_cpu(
    view: GraphView,
    cluster_id: str | None,
    namespace: str | None,
    *,
    limit: int = 10,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    tid = _active_tenant_id(tenant_id)
    if tid is not None:
        _acl_cluster(tenant_id, cluster_id)
    pods = view.entities_by_type(EntityType.POD.value)
    if cluster_id is not None:
        cid = str(cluster_id).strip()
        pods = [p for p in pods if _props_cluster(p.get("properties") or {}) == cid]
    pods = _filter_entities_by_tenant(pods, tenant_id)
    if namespace is not None:
        ns = str(namespace).strip()
        pods = [p for p in pods if str(p.get("properties", {}).get("namespace")) == ns]

    rows: list[dict[str, Any]] = []
    for p in pods:
        props = p.get("properties") or {}
        cpu = _metric_float(props, "cpu_cores")
        if cpu is None:
            continue
        rows.append(
            {
                "id": p.get("id"),
                "cluster_id": props.get("cluster_id"),
                "name": props.get("name"),
                "namespace": props.get("namespace"),
                "status": props.get("status"),
                "cpu_cores": cpu,
                "memory_bytes": props.get("memory_bytes"),
            }
        )
    rows.sort(key=lambda r: r["cpu_cores"], reverse=True)
    cap = max(1, int(limit)) if limit else 10
    rows = rows[:cap]
    return {"op": "top_pods_by_cpu", "count": len(rows), "pods": rows}


def _pod_metrics(
    view: GraphView,
    cluster_id: str,
    namespace: str | None,
    name: str | None,
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    if not namespace or not name:
        raise QueryError("pod_metrics requires namespace and name")
    pid = view.pod_entity_id(cluster_id, str(namespace), str(name))
    ent = view.entities.get(pid)
    tid = _active_tenant_id(tenant_id)
    if ent is None or (tid is not None and not _entity_matches_tenant(ent, tid)):
        return {
            "op": "pod_metrics",
            "found": False,
            "cluster_id": cluster_id,
            "namespace": namespace,
            "name": name,
        }
    props = ent.get("properties") or {}
    return {
        "op": "pod_metrics",
        "found": True,
        "id": pid,
        "cluster_id": cluster_id,
        "namespace": namespace,
        "name": name,
        "cpu_cores": _metric_float(props, "cpu_cores"),
        "memory_bytes": props.get("memory_bytes"),
        "status": props.get("status"),
    }


def run_pod_scope_queries(
    source: dict[str, Any] | GraphView,
    *,
    cluster_id: str,
    namespace: str,
    name: str,
    tenant_id: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Run pod_status / events_for_pod / inspections_for_pod on one ``GraphView``."""
    view = source if isinstance(source, GraphView) else GraphView.from_payload(source)
    cid = _require_cluster_id(cluster_id)
    _acl_cluster(tenant_id, cid)
    ns = str(namespace).strip()
    pname = str(name).strip()
    return {
        "pod_status": _pod_status(view, cid, ns, pname, tenant_id=tenant_id),
        "events_for_pod": _events_for_pod(view, cid, ns, pname, tenant_id=tenant_id),
        "inspections_for_pod": _inspections_for_pod(
            view, cid, ns, pname, tenant_id=tenant_id
        ),
    }


__all__ = [
    "QueryError",
    "TenantAccessError",
    "run_query",
    "run_pod_scope_queries",
]
