from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

# Reuse integration query + agent logic (monorepo layout).
_INTEGRATION_SRC = Path(__file__).resolve().parents[2] / "langgraph-integration" / "src"
if str(_INTEGRATION_SRC) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_SRC))

from agent.diagnose import diagnose_from_gather_dict  # noqa: E402
from agent.execute import execute_recommended_actions  # noqa: E402
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
        tenant_id=req.get("tenant_id"),
    )
    payload["gather"] = dict(gather_result)
    return {"payload": payload}


def narrate(state: State) -> State:
    """Template + optional LLM polish using ``payload.gather`` and ``payload.diagnosis``."""
    payload = dict(state.get("payload") or {})
    raw_gather = payload.get("gather")
    if not isinstance(raw_gather, dict):
        return {"payload": payload}
    use_llm: bool | None = None
    req = parse_inspect_request(payload)
    if req is not None:
        use_llm = req.get("use_llm")
    raw_diagnosis = payload.get("diagnosis")
    diagnosis = raw_diagnosis if isinstance(raw_diagnosis, dict) else None
    raw_matches = payload.get("skill_matches")
    skill_matches = raw_matches if isinstance(raw_matches, list) else None
    report = build_report_from_gather_dict(
        raw_gather,
        use_llm=use_llm,
        diagnosis=diagnosis,
        skill_matches=skill_matches,
    )
    payload["narrative"] = dict(report)
    return {"payload": payload}


def retrieve_skills(state: State) -> State:
    """Search skill store from ``payload.diagnosis`` → ``payload.skill_matches``."""
    payload = dict(state.get("payload") or {})
    raw_diagnosis = payload.get("diagnosis")
    if not isinstance(raw_diagnosis, dict):
        return {"payload": payload}
    from agent.types import DiagnosisReport  # noqa: E402
    from skills.retrieve import retrieve_for_diagnosis  # noqa: E402

    diagnosis = DiagnosisReport(**raw_diagnosis)
    if not diagnosis.get("issues"):
        payload["skill_matches"] = []
        return {"payload": payload}
    matches = retrieve_for_diagnosis(diagnosis)
    payload["skill_matches"] = [dict(m) for m in matches]
    return {"payload": payload}


def diagnose(state: State) -> State:
    """Rule-based diagnosis from ``payload.gather`` → ``payload.diagnosis``."""
    payload = dict(state.get("payload") or {})
    raw_gather = payload.get("gather")
    if not isinstance(raw_gather, dict):
        return {"payload": payload}
    req = parse_inspect_request(payload)
    tenant_id = req.get("tenant_id") if req else None
    report = diagnose_from_gather_dict(raw_gather, tenant_id=tenant_id)
    payload["diagnosis"] = dict(report)
    return {"payload": payload}


def execute(state: State) -> State:
    """Simulate recommended actions from ``payload.diagnosis`` → ``payload.execution``."""
    payload = dict(state.get("payload") or {})
    raw_diagnosis = payload.get("diagnosis")
    if not isinstance(raw_diagnosis, dict):
        return {"payload": payload}
    dry_run = True
    req = parse_inspect_request(payload)
    if req is not None and "dry_run" in req:
        dry_run = bool(req.get("dry_run", True))
    from agent.actions.policy import action_context_from_diagnosis  # noqa: E402
    from agent.types import DiagnosisReport  # noqa: E402

    diagnosis = DiagnosisReport(**raw_diagnosis)
    result = execute_recommended_actions(
        diagnosis,
        dry_run=dry_run,
        context=action_context_from_diagnosis(diagnosis),
    )
    payload["execution"] = dict(result)
    return {"payload": payload}


def verify_skill(state: State) -> State:
    """W5 stub: mark skill verification false until sandbox/manual ack (W6+)."""
    payload = dict(state.get("payload") or {})
    raw_execution = payload.get("execution")
    dry_run = True
    if isinstance(raw_execution, dict):
        dry_run = bool(raw_execution.get("dry_run", True))
    payload["skill_verification"] = {
        "verified": False,
        "reason": "w5_dry_run_only" if dry_run else "w5_unverified",
    }
    return {"payload": payload}


def record_skill(state: State) -> State:
    """Persist skill Markdown when diagnosis has issues and recording is enabled."""
    payload = dict(state.get("payload") or {})
    from skills.config import skills_config  # noqa: E402
    from skills.store import get_default_store  # noqa: E402
    from skills.writer import build_skill_markdown  # noqa: E402
    from agent.types import DiagnosisReport, GatherResult  # noqa: E402

    cfg = skills_config()
    if not cfg.record_enabled:
        return {"payload": payload}

    raw_gather = payload.get("gather")
    raw_diagnosis = payload.get("diagnosis")
    if not isinstance(raw_gather, dict) or not isinstance(raw_diagnosis, dict):
        return {"payload": payload}

    diagnosis = DiagnosisReport(**raw_diagnosis)
    if not diagnosis.get("issues"):
        return {"payload": payload}

    gather = GatherResult(**raw_gather)
    verified = False
    raw_ver = payload.get("skill_verification")
    if isinstance(raw_ver, dict) and raw_ver.get("verified") is True:
        verified = True

    markdown = build_skill_markdown(gather, diagnosis, verified=verified)
    result = get_default_store().upsert_skill(markdown)
    payload["skill_record"] = dict(result)
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
builder.add_node("diagnose", diagnose)
builder.add_node("retrieve_skills", retrieve_skills)
builder.add_node("execute", execute)
builder.add_node("verify_skill", verify_skill)
builder.add_node("record_skill", record_skill)
builder.add_node("query", query)
builder.add_edge(START, "ingest")
builder.add_edge("ingest", "gather")
builder.add_edge("gather", "diagnose")
builder.add_edge("diagnose", "retrieve_skills")
builder.add_edge("retrieve_skills", "narrate")
builder.add_edge("narrate", "execute")
builder.add_edge("execute", "verify_skill")
builder.add_edge("verify_skill", "record_skill")
builder.add_edge("record_skill", "query")
builder.add_edge("query", END)

graph = builder.compile()
