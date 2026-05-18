# langgraph-integration

MCP → graph pipeline for Sentinel-X: normalize K8s/Prometheus tool output into graph entities, then push to the local LangGraph server.

## Data flow

```text
MCP (k8s_get_pods / k8s_get_events / …)
  → adapter/     (field mapping, no HTTP)
  → models/      (GraphEntity, GraphBatch, stable IDs)
  → sync/        (incremental, retry, chunking, push to LangGraph)
  → clients/     (langgraph-sdk thin wrapper)
  → langgraph-server (graph id: sentinel)
```

Related package: [`../langgraph-server`](../langgraph-server) — run with `langgraph dev` and set `LANGGRAPH_API_URL` (see `.env.example`).

## Directory layout

| Path | Role |
|------|------|
| `src/adapter/` | MCP JSON → `GraphEntity` / `GraphBatch` (pure mapping) |
| `src/models/` | Entity types, edges, ID rules, `GraphBatch.from_pods_events` |
| `src/sync/` | `pipeline.py` — resilient push; `state.py` incremental; `scheduler.py` periodic loop |
| `src/clients/` | `langgraph_client.py` — SDK factory, sync stream, query API |
| `src/query/` | `GraphView`, `run_query`, CLI `format_query_result` (step 6) |
| `src/utils/` | `chunk_graph_batch`, `merge_graph_batches` (step 8) |
| `tests/` | Unit tests (no live LangGraph required for most cases) |
| `scripts/` | `full_pipeline_demo.py`, `query_demo.py`, `sync_once_demo.py`, `smoke_local_langgraph.py` |

## Development

```powershell
cd agents\langgraph-integration
pip install -r requirements.txt

# Tests (inserts src/ on path like existing tests)
python -m unittest discover -s tests -v

# Optional live smoke (langgraph dev on :2024)
$env:LANGGRAPH_API_URL = "http://127.0.0.1:2024"
python scripts\smoke_local_langgraph.py
```

Set `PYTHONPATH=src` when running ad-hoc scripts from this directory.

## Environment

Copy `.env.example` and set:

- `LANGGRAPH_API_URL` — LangGraph API base URL (e.g. `http://127.0.0.1:2024`)
- Optional: `LANGGRAPH_API_KEY` / `LANGSMITH_API_KEY` if your server requires it

### Sync (step 5)

| Variable | Default | Purpose |
|----------|---------|---------|
| `LANGGRAPH_SYNC_INCREMENTAL` | `1` | Skip unchanged entities (fingerprint cache) |
| `LANGGRAPH_SYNC_STATE_PATH` | — | Optional JSON file for fingerprint persistence |
| `LANGGRAPH_SYNC_MAX_RETRIES` | `3` | Push retry attempts |
| `LANGGRAPH_SYNC_RETRY_DELAYS` | `0.5,1.0,2.0` | Seconds between retries |
| `LANGGRAPH_SYNC_CHUNK_MAX_ENTITIES` | `500` | Max entities per LangGraph run |
| `LANGGRAPH_SYNC_CHUNK_MAX_EDGES` | `500` | Max edges per chunk |
| `LANGGRAPH_SYNC_MIN_INTERVAL_SEC` | `0.2` | Sleep between chunks |

## Sync usage

**Event-triggered** (after MCP returns):

```python
from sync import sync_pods_and_events_resilient

result = sync_pods_and_events_resilient(pods_mcp, events_mcp, namespace)
```

**Periodic** (caller fetches MCP, then sync):

```python
from sync import run_periodic_sync, sync_pods_and_events_resilient

def tick():
    pods, events = fetch_from_mcp()  # your code
    return sync_pods_and_events_resilient(pods, events, "default")

stats = run_periodic_sync(tick, interval_sec=60.0, max_iterations=None)
# stats.iterations, stats.failures; SIGINT/SIGTERM stop gracefully
```

Demo: `python scripts/sync_once_demo.py` (live LangGraph required).

## Query (step 6)

In-memory queries over a sync `payload` (`entities` + `edges`). The LangGraph `sentinel` graph merges ingest data per **thread** and runs `payload.query` in the `query` node.

| `op` | Parameters | Returns |
|------|------------|---------|
| `list_pods` | `namespace?` | Pod rows (name, namespace, status) |
| `pod_status` | `namespace`, `name` | Single pod properties or `found: false` |
| `events_for_pod` | `namespace`, `name` | Events linked via `has_event` |
| `inspections_summary` | — | Inspection entities + `inspects_pod` / `inspects_node` links |
| `list_events` | `namespace?` | All Event entities (step 8) |
| `inspections_for_pod` | `namespace`, `name` | Inspections linked via `inspects_pod` (step 8) |

**Local (no LangGraph):**

```powershell
python scripts\query_demo.py
```

**Live (sync + query on one thread):**

```powershell
$env:LANGGRAPH_API_URL = "http://127.0.0.1:2024"
$env:LANGGRAPH_RUN_LIVE = "1"
python scripts\query_demo.py --live --thread-id my-thread-1
```

**SDK:**

```python
from clients.langgraph_client import stream_sentinel_run, query_sentinel

thread_id = "my-thread-1"
stream_sentinel_run(batch.to_dict(wire_only=True), thread_id=thread_id)
result = query_sentinel("events_for_pod", thread_id=thread_id, namespace="default", name="demo-pod")
```

Use the same `thread_id` for sync and query so checkpointed graph state accumulates. Pass `thread_id` into `push_graph_batch` / `sync_*_resilient` for production sync.

## Step 8: Events + Inspections

Expand in order: **Pod → Event → Inspection** (model → adapter → sync → query).

### ID conventions

- Inspection row `linked_pods` / `link_pods` args must be **entity ids** (`pod:default/demo-pod`), not bare pod names.
- `linked_nodes` / `link_nodes` use `node:worker-01` form.
- Pod→Node edges remain optional (`pod_node_map` in `pods_events_to_batch`); Node entities are defined for future use.

### Sync APIs

```python
from sync import sync_inspections_resilient, sync_pods_events_inspections_resilient

thread_id = "cluster-default"
sync_inspections_resilient(inspection_mcp, thread_id=thread_id, link_pods=["pod:default/demo-pod"])
sync_pods_events_inspections_resilient(pods_mcp, events_mcp, "default", inspection_mcp, thread_id=thread_id)
```

`sync_pods_events_inspections_resilient` merges Pod/Event and Inspection batches via `merge_graph_batches` (orphan edges dropped).

### Query ops (step 8)

| `op` | Parameters |
|------|------------|
| `list_events` | `namespace?` |
| `inspections_for_pod` | `namespace`, `name` |

### Phase 1–3 acceptance

```powershell
# Phase 1–2: unit tests + mock demo (no langgraph dev)
python -m unittest discover -s tests -v
python scripts\full_pipeline_demo.py

# Phase 3 live
$env:LANGGRAPH_API_URL = "http://127.0.0.1:2024"
$env:LANGGRAPH_RUN_LIVE = "1"
python scripts\full_pipeline_demo.py --live --thread-id step8-demo
```

## Boundaries

- **Adapter**: no HTTP, retries, or cron inside adapter functions.
- **Sync**: incremental + retry + chunking; does not call K8s MCP directly.
- **MCP servers**: live under repo `mcp-servers/`; this package only consumes their `{query, results}` shape.
