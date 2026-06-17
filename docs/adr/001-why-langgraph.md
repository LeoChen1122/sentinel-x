# ADR-001: Why LangGraph

## Status

Accepted (2026-06-17)

## Context

Sentinel-X needs an agent runtime that:

- Orchestrates multi-step SRE workflows (sync → diagnose → execute → sandbox → record)
- Keeps **inspect context** in a durable thread (pods, events, prior diagnoses)
- Supports incremental rollout (W1–W7) without rewriting the whole stack each week

Alternatives considered:

- **CrewAI / multi-agent frameworks** — fast to demo, but opaque hand-offs and harder to test node-by-node
- **Plain LangChain chains** — linear; awkward for conditional branches (sandbox vs dry-run, skill hit/miss)
- **Custom asyncio pipeline** — full control, high maintenance

## Decision

Use **LangGraph** as the orchestration layer:

- Graph defined in [`agents/langgraph-server/src/graph.py`](../../agents/langgraph-server/src/graph.py)
- Integration layer (sync, query, trigger) in [`agents/langgraph-integration/`](../../agents/langgraph-integration/)
- LangGraph SDK client for production sync/query and W7 triggers

Pipeline (current):

```text
ingest → gather → diagnose → retrieve_skills → narrate
  → execute → sandbox_run → verify_skill → record_skill → query
```

Checkpoint persistence (SQLite) is planned for Phase 4 — graph structure stays the same.

## Consequences

**Positive**

- Each step is a testable node; ~210+ unit tests cover adapter/sync/trigger paths
- Thread ID maps cleanly to cluster/tenant (`CLUSTER_ID`, `LANGGRAPH_THREAD_ID`)
- LangGraph Studio / `langgraph dev` for local debugging

**Negative**

- Two packages to maintain (`langgraph-server` graph + `langgraph-integration` data plane)
- Checkpoint story still in-memory on server until SqliteSaver lands
- LangGraph SDK version coupling with server image

## References

- [Architecture overview](../architecture/overview.md)
- [ADR-002: Why MCP](002-why-mcp.md)
