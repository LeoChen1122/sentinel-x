from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

# Reuse integration query logic (monorepo layout: agents/langgraph-integration/src).
_INTEGRATION_SRC = Path(__file__).resolve().parents[2] / "langgraph-integration" / "src"
if str(_INTEGRATION_SRC) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_SRC))

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
builder.add_node("query", query)
builder.add_edge(START, "ingest")
builder.add_edge("ingest", "query")
builder.add_edge("query", END)

graph = builder.compile()
