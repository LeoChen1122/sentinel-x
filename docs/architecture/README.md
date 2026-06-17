# Architecture

Public-facing architecture diagrams for Sentinel-X. For component-level status and live evidence, see [Architecture Review v3](../ARCHITECTURE-REVIEW.md).

| Diagram | Description |
|---------|-------------|
| [Overview](overview.md) | User → API → Agent → LangGraph → Skills → MCP |
| [Alert loop](alert-loop.md) | Alert → Analyze → Root cause → Fix → Sandbox → Auto close |
| [Sandbox](sandbox.md) | Agent → Sandbox manager → Docker executor |

## Code map

| Layer | Path |
|-------|------|
| API / webhooks | `apps/api/` |
| Trigger (patrol, inspect) | `agents/langgraph-integration/src/trigger/` |
| LangGraph graph | `agents/langgraph-server/src/graph.py` |
| Data plane (sync, query) | `agents/langgraph-integration/src/` |
| MCP servers | `mcp-servers/k8s/`, `mcp-servers/prometheus/` |
| Skills | `skills/`, `agents/langgraph-integration/src/skills/` |
| Sandbox | `sandbox/`, `agents/langgraph-integration/src/sandbox/` |
| Deploy | `deploy/install/`, `deploy/config/` |
