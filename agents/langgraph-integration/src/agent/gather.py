"""Gather cluster-scoped subgraph and query facts for inspection narrative."""

from __future__ import annotations

from typing import Any

from agent.types import GatherResult, InspectRequest
from config.tenant_registry import assert_tenant_cluster_access
from models.ids import pod_id
from query.graph_view import GraphView
from query.operations import run_pod_scope_queries


def _props_cluster(props: dict[str, Any]) -> str:
    return str(props.get("cluster_id", ""))


def _props_tenant(props: dict[str, Any]) -> str:
    return str(props.get("tenant_id", ""))


def _active_tenant_id(tenant_id: str | None) -> str | None:
    if tenant_id is None:
        return None
    tid = str(tenant_id).strip()
    return tid if tid else None


def _subgraph_from_view(
    view: GraphView,
    cluster_id: str,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Filter entities/edges from an existing view (no second payload parse)."""
    cid = cluster_id.strip()
    tid = _active_tenant_id(tenant_id)
    kept_entities = [
        ent
        for ent in view.entities.values()
        if _props_cluster(ent.get("properties") or {}) == cid
        and (tid is None or _props_tenant(ent.get("properties") or {}) == tid)
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
    tenant_id: str | None = None,
) -> GatherResult:
    """Build ``GatherResult`` from full graph payload and scoped queries.

    Parses the payload into a single ``GraphView`` and reuses it for subgraph
    filtering and all pod-scoped queries (avoids repeated full-graph scans).
    """
    cid = cluster_id.strip()
    ns = namespace.strip()
    pname = pod_name.strip()
    tid = _active_tenant_id(tenant_id)
    if tid is not None:
        assert_tenant_cluster_access(tid, cid)
    pid = pod_id(cid, ns, pname)

    view = GraphView.from_payload(payload)
    subgraph = _subgraph_from_view(view, cid, tenant_id=tid)
    queries = run_pod_scope_queries(
        view,
        cluster_id=cid,
        namespace=ns,
        name=pname,
        tenant_id=tid,
    )
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
    use_llm_raw = raw.get("use_llm", raw.get("llm"))
    if use_llm_raw is not None:
        if isinstance(use_llm_raw, bool):
            req["use_llm"] = use_llm_raw
        else:
            req["use_llm"] = str(use_llm_raw).strip().lower() in ("1", "true", "yes")
    if "dry_run" in raw:
        val = raw["dry_run"]
        if isinstance(val, bool):
            req["dry_run"] = val
        else:
            req["dry_run"] = str(val).strip().lower() not in ("0", "false", "no")
    return req
