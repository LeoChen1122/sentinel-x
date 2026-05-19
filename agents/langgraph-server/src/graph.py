from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

# Reuse integration query + agent logic (monorepo layout).
_INTEGRATION_SRC = Path(__file__).resolve().parents[2] / "langgraph-integration" / "src"
if str(_INTEGRATION_SRC) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_SRC))

from agent.gather import gather_subgraph, parse_inspect_request  # noqa: E402
from agent.narrative import build_report_from_gather_dict  # noqa: E402
from query.graph_view import GraphView  # noqa: E402
from query.operations import run_query  # noqa: E402


def _merge_payload(
    current: dict[str, Any] | None, update: dict[str, Any] | None
) -> dict[str, Any]:
    """Accumulate entities/edges across thread runs; overlay query fields."""
    current = dict(current or {})
    update = dict(update or {})
    view = GraphView.from_payload(current)
    ent_u, edge_u = _payload_entities_edges(update)
    if ent_u or edge_u:
        if view.entities or view.edges:
            view.merge_payload({"entities": ent_u, "edges": edge_u})
        else:
            view = GraphView.from_payload(
                {
                    **{k: v for k, v in current.items() if k not in ("entities", "edges")},
                    "entities": ent_u,
                    "edges": edge_u,
                }
            )
    merged = view.to_payload() if (view.entities or view.edges) else dict(current)
    for key, value in update.items():
        if key not in ("entities", "edges"):
            merged[key] = value
    return merged


class State(TypedDict):
    payload: Annotated[dict[str, Any], _merge_payload]


def _payload_entities_edges(payload: dict[str, Any]) -> tuple[list, list]:
    entities = payload.get("entities")
    edges = payload.get("edges")
    ent_list = list(entities) if isinstance(entities, list) else []
    edge_list = list(edges) if isinstance(edges, list) else []
    return ent_list, edge_list


def ingest(state: State) -> State:
    """Merge incoming entities/edges into accumulated graph payload."""
    payload = dict(state.get("payload") or {})
    incoming = dict(payload)
    ent_in, edge_in = _payload_entities_edges(incoming)

    if ent_in or edge_in:
        view = GraphView.from_payload(payload)
        if not view.entities and not view.edges:
            base = {k: v for k, v in payload.items() if k not in ("entities", "edges")}
            view = GraphView.from_payload(
                {**base, "entities": ent_in, "edges": edge_in}
            )
        else:
            view.merge_payload({"entities": ent_in, "edges": edge_in})
        merged = view.to_payload()
        for key, value in payload.items():
            if key not in ("entities", "edges"):
                merged[key] = value
        payload = merged
    else:
        if "entities" not in payload:
            payload.setdefault("entities", [])
        if "edges" not in payload:
            payload.setdefault("edges", [])

    return {"payload": payload}


def gather(state: State) -> State:
    """Run scoped queries when ``payload.inspect`` is set; write ``payload.gather``."""
    payload = dict(state.get("payload") or {})
    req = parse_inspect_request(payload)
    if req is None:
        return {"payload": payload}
    gather_result = gather_subgraph(
        payload,
        cluster_id=req["cluster_id"],
        namespace=req["namespace"],
        pod_name=req["pod_name"],
    )
    payload["gather"] = dict(gather_result)
    return {"payload": payload}


def narrate(state: State) -> State:
    """Build inspection report from ``payload.gather`` → ``payload.narrative``."""
    payload = dict(state.get("payload") or {})
    raw_gather = payload.get("gather")
    if not isinstance(raw_gather, dict):
        return {"payload": payload}
    use_llm: bool | None = None
    req = parse_inspect_request(payload)
    if req is not None and "use_llm" in req:
        use_llm = req.get("use_llm")
    report = build_report_from_gather_dict(raw_gather, use_llm=use_llm)
    payload["narrative"] = dict(report)
    return {"payload": payload}


def query(state: State) -> State:
    """Run ``payload.query`` against accumulated graph; set ``query_result``."""
    payload = dict(state.get("payload") or {})
    q = payload.get("query")
    if isinstance(q, dict) and q.get("op"):
        op = str(q["op"])
        params = {k: v for k, v in q.items() if k != "op"}
        payload["query_result"] = run_query(payload, op, **params)
    return {"payload": payload}


builder = StateGraph(State)
builder.add_node("ingest", ingest)
builder.add_node("gather", gather)
builder.add_node("narrate", narrate)
builder.add_node("query", query)
builder.add_edge(START, "ingest")
builder.add_edge("ingest", "gather")
builder.add_edge("gather", "narrate")
builder.add_edge("narrate", "query")
builder.add_edge("query", END)

graph = builder.compile()
