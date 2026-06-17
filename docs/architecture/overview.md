# System Overview

High-level data and control flow for Sentinel-X.

```mermaid
flowchart TB
  User["User / Cron / Alertmanager"]
  API["Sentinel API\napps/api"]
  Trigger["Trigger layer\ntrigger/patrol, inspect_trigger"]
  Runtime["Agent runtime\nlanggraph-integration"]
  Graph["LangGraph\ngraph.py pipeline"]
  Skills["Skill Registry\nSQLite FTS"]
  MCP["MCP Servers"]
  K8s["Kubernetes MCP"]
  Prom["Prometheus MCP"]
  SB["Sandbox MCP / Docker"]

  User --> API
  User --> Trigger
  API --> Trigger
  Trigger --> Runtime
  Runtime --> Graph
  Graph --> Skills
  Graph --> Runtime
  Runtime --> MCP
  MCP --> K8s
  MCP --> Prom
  Graph --> SB
```

## Layers

| Layer | Role | Key paths |
|-------|------|-----------|
| **Entry** | HTTP inspect, Alertmanager webhook, cron patrol | `apps/api/`, `deploy/sync/sentinel-inspect-patrol.sh` |
| **Trigger** | Normalize alerts → `trigger_inspect` | `agents/langgraph-integration/src/trigger/` |
| **Runtime** | Sync K8s/Prom into graph thread; query helpers | `agents/langgraph-integration/src/sync/`, `query/` |
| **Graph** | ingest → gather → diagnose → … → record → query | `agents/langgraph-server/src/graph.py` |
| **Skills** | Retrieve and record runbooks (W5) | `skills/`, `src/skills/` |
| **MCP** | Standard tool boundary to cluster APIs | `mcp-servers/` |

## Deep dive

- Internal review: [Architecture Review v3](../ARCHITECTURE-REVIEW.md)
- Deploy topology: [DEPLOY-ONE-SHOT.md](../deploy/DEPLOY-ONE-SHOT.md)
