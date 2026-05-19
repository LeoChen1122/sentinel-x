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
| `src/testing/` | Multicluster MCP mocks (`multicluster_fixtures.py`, phase 4-0) |
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
from sync import sync_pods_and_events_resilient, sync_thread_id

result = sync_pods_and_events_resilient(
    pods_mcp, events_mcp, namespace, cluster_id="dev-cluster"
)
# Default LangGraph thread_id: "default:dev-cluster" (tenant:cluster)
sync_thread_id("dev-cluster", tenant_id="team-alpha")  # -> "team-alpha:dev-cluster"
```

### Phase 4-2: multicluster sync partition

| Concept | Behavior |
|---------|----------|
| `thread_id` | Default `{tenant_id or 'default'}:{cluster_id}` via `sync_thread_id()` |
| `SyncState` | Partitioned under `LANGGRAPH_SYNC_STATE_PATH/partitions/{tenant}/{cluster}.json` |
| `SyncStateRegistry` | One in-memory/disk state per tenant+cluster |
| `sync_clusters_resilient` | Tick multiple clusters with isolated state/thread |

```python
from sync import make_mock_cluster_sync, sync_clusters_resilient
from testing.multicluster_fixtures import CLUSTER_DEV, CLUSTER_PROD

sync_one = make_mock_cluster_sync()
sync_clusters_resilient([CLUSTER_DEV, CLUSTER_PROD], sync_one)
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
| `list_pods` | `cluster_id?`, `namespace?` | Pod rows (name, namespace, status) |
| `pod_status` | `cluster_id`, `namespace`, `name` | Single pod properties or `found: false` |
| `events_for_pod` | `cluster_id`, `namespace`, `name` | Events linked via `has_event` |
| `inspections_summary` | `cluster_id?` | Inspection entities + `inspects_pod` / `inspects_node` links |
| `list_events` | `cluster_id?`, `namespace?` | All Event entities (step 8) |
| `inspections_for_pod` | `cluster_id`, `namespace`, `name` | Inspections linked via `inspects_pod` (step 8) |

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
result = query_sentinel(
    "events_for_pod",
    thread_id=thread_id,
    cluster_id="local",
    namespace="default",
    name="shared-pod",
)
```

Use the same `thread_id` for sync and query so checkpointed graph state accumulates. `sync_*_resilient` derives it from `cluster_id` / `tenant_id` when omitted; override with explicit `thread_id` if needed.

## Step 8: Events + Inspections

Expand in order: **Pod → Event → Inspection** (model → adapter → sync → query).

### ID conventions (phase 4-0, scheme A)

All stable IDs include **`cluster_id`** as the first segment:

| Entity | ID pattern |
|--------|------------|
| Pod | `pod:{cluster_id}/{namespace}/{name}` |
| Event | `event:{cluster_id}:{namespace}:...` (structured or hash suffix) |
| Node | `node:{cluster_id}/{name}` |
| Inspection | `inspection:{cluster_id}:{timestamp}:{node}` |

- `tenant_id` is stored in `properties` only (not in ID strings).
- Inspection row `linked_pods` / `link_pods` must be **entity ids** (e.g. `pod:local/default/shared-pod`), not bare pod names.
- `linked_nodes` / `link_nodes` use `node:{cluster_id}/worker-01` form.
- Pod→Node edges remain optional (`pod_node_map` in `pods_events_to_batch`); Node entities are defined for future use.

### MCP contract (phase 4-0)

MCP list responses extend the step 3 shape with **`cluster_id`**:

```json
{ "query": "get_pods", "cluster_id": "dev-cluster", "results": [ ... ] }
```

Adapter resolves `cluster_id` from the payload or from an explicit argument. Without either, conversion raises.

### Multicluster mocks (no live K8s)

```python
from testing.multicluster_fixtures import (
    CLUSTER_DEV,
    CLUSTER_PROD,
    dual_cluster_merged_batch,
    pods_mcp,
)

batch = dual_cluster_merged_batch()  # dev + prod, same pod name, distinct IDs
```

```powershell
python scripts\full_pipeline_demo.py   # prints per-cluster list_pods / events_for_pod
python scripts\query_demo.py --cluster-id local
```

Tests: `tests/test_multicluster.py`.

### Sync APIs

```python
from sync import sync_inspections_resilient, sync_pods_events_inspections_resilient

sync_inspections_resilient(
    inspection_mcp,
    cluster_id="local",
    link_pods=["pod:local/default/shared-pod"],
)
sync_pods_events_inspections_resilient(
    pods_mcp, events_mcp, "default", inspection_mcp, cluster_id="local"
)
```

`sync_pods_events_inspections_resilient` merges Pod/Event and Inspection batches via `merge_graph_batches` (orphan edges dropped).

### Query ops (step 8)

| `op` | Parameters |
|------|------------|
| `list_events` | `cluster_id?`, `namespace?` |
| `inspections_for_pod` | `cluster_id`, `namespace`, `name` |

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

## Multicluster acceptance (mock)

Validates Node / Inspection IDs and edges, Adapter stability, Query with `cluster_id`, and per-cluster LangGraph `thread_id` (no live K8s required).

| Term | Meaning |
|------|---------|
| linked_events | Query op `events_for_pod` (via `has_event` edges) |
| linked_pods | Adapter row field; Query op `inspections_for_pod` / `inspections_summary` |

```powershell
python -m unittest tests.test_multicluster tests.test_multicluster_graph tests.test_multicluster_sync -v
python scripts\multicluster_validate_demo.py
```

Fixture: `dual_cluster_full_batch()` — dev + prod each with Pod, Event, Node, Inspection.

## Phase 4-0b (deferred)

Live multi-cluster wiring (not required for model validation):

- `configs/clusters.yaml` + per-cluster `CLUSTER_ID` env on MCP containers
- One MCP service per cluster in docker-compose
- `ClusterDataSource` abstraction for fetch + sync loops

## Boundaries

- **Adapter**: no HTTP, retries, or cron inside adapter functions.
- **Sync**: incremental + retry + chunking; does not call K8s MCP directly.
- **MCP servers**: live under repo `mcp-servers/`; this package only consumes their `{query, results}` shape.
