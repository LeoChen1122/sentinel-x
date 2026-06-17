# ADR-002: Why MCP

## Status

Accepted (2026-06-17)

## Context

Sentinel-X must read Kubernetes and Prometheus from the agent without:

- Embedding cluster credentials in the LangGraph process
- Tightly coupling graph nodes to `kubernetes` / `requests` client code
- Blocking future tools (logs, Argo, custom metrics) behind large refactors

Alternatives considered:

- **Direct Python clients in graph nodes** — fewer moving parts, but credential sprawl and no tool boundary
- **REST wrapper microservices** — custom protocol per tool; no ecosystem reuse
- **OpenAI function calling only** — model vendor lock-in for tool schema

## Decision

Use **Model Context Protocol (MCP)** with **FastMCP** servers:

| Server | Path | Tools |
|--------|------|-------|
| Kubernetes | `mcp-servers/k8s/` | `k8s_get_pods`, `k8s_get_events` |
| Prometheus | `mcp-servers/prometheus/` | `prom_query`, `prom_query_range` |

Runtime pattern:

- MCP containers run via `mcp-servers/compose/docker-compose.yml`
- Integration layer calls tools via `docker exec` + stdio ([`mcp_k8s_sync_live.py`](../../agents/langgraph-integration/scripts/live/mcp_k8s_sync_live.py))
- Pod status normalization lives in MCP layer ([`normalize.py`](../../mcp-servers/k8s/src/normalize.py))

## Consequences

**Positive**

- Clear security boundary: only MCP containers hold kubeconfig / Prom URL
- New observability source = new MCP server, not graph surgery
- Tool schemas are stable inputs for future LLM tool-use

**Negative**

- `docker exec` adds latency vs in-process calls
- Two containers to patch/restart on deploy
- MCP spec still evolving; we pin FastMCP versions in each server

## References

- [MCP compose README](../../mcp-servers/compose/README.md) (if present) or `mcp-servers/`
- [DEPLOY-MCP-KUBECONFIG.md](../deploy/DEPLOY-MCP-KUBECONFIG.md)
