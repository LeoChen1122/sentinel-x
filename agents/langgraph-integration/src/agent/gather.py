"""Gather cluster-scoped subgraph and query facts for inspection narrative."""

from __future__ import annotations

from typing import Any

from agent.types import GatherResult, InspectRequest
from models.ids import pod_id
from query.graph_view import GraphView
from query.operations import run_query


def _props_cluster(props: dict[str, Any]) -> str:
    return str(props.get("cluster_id", ""))


def _filter_subgraph(payload: dict[str, Any], cluster_id: str) -> dict[str, Any]:
    """Entities/edges whose endpoints belong to ``cluster_id`` (properties)."""
    view = GraphView.from_payload(payload)
    cid = cluster_id.strip()
    kept_entities = [
        ent
        for ent in view.entities.values()
        if _props_cluster(ent.get("properties") or {}) == cid
    ]
    kept_ids = {str(e["id"]) for e in kept_entities if e.get("id")}
    kept_edges = [
        e
        for e in view.edges
        if str(e.get("source_id", "")) in kept_ids
        and str(e.get("target_id", "")) in kept_ids
    ]
    return {"entities": kept_entities, "edges": kept_edges}


def gather_subgraph(
    payload: dict[str, Any],
    *,
    cluster_id: str,
    namespace: str,
    pod_name: str,
) -> GatherResult:
    """Build ``GatherResult`` from full graph payload and scoped queries."""
    cid = cluster_id.strip()
    ns = namespace.strip()
    pname = pod_name.strip()
    pid = pod_id(cid, ns, pname)
    subgraph = _filter_subgraph(payload, cid)
    queries = {
        "pod_status": run_query(
            payload, "pod_status", cluster_id=cid, namespace=ns, name=pname
        ),
        "events_for_pod": run_query(
            payload, "events_for_pod", cluster_id=cid, namespace=ns, name=pname
        ),
        "inspections_for_pod": run_query(
            payload, "inspections_for_pod", cluster_id=cid, namespace=ns, name=pname
        ),
    }
    return GatherResult(
        cluster_id=cid,
        namespace=ns,
        pod_name=pname,
        pod_entity_id=pid,
        subgraph=subgraph,
        queries=queries,
    )


def parse_inspect_request(payload: dict[str, Any]) -> InspectRequest | None:
    """Read ``payload.inspect`` if present and valid."""
    raw = payload.get("inspect")
    if not isinstance(raw, dict):
        return None
    cid = raw.get("cluster_id")
    ns = raw.get("namespace")
    pname = raw.get("pod_name")
    if not cid or not ns or not pname:
        return None
    req: InspectRequest = {
        "cluster_id": str(cid).strip(),
        "namespace": str(ns).strip(),
        "pod_name": str(pname).strip(),
    }
    tid = raw.get("tenant_id")
    if tid is not None and str(tid).strip():
        req["tenant_id"] = str(tid).strip()
    return req
