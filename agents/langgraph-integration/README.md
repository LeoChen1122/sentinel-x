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
| `scripts/live/` | Production cron entry points (`mcp_k8s_sync_live.py`, `mcp_prom_sync_live.py`) |
| `scripts/demo/` | Dev demos and smoke tests (`*_demo.py`, `skill_write_demo.py`) |
| `src/skills/` | W5 Skills: FTS store, writer, retrieve (see [`skills/README.md`](../../skills/README.md)) |

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
from sync import langgraph_thread_id, sync_pods_and_events_resilient, sync_thread_id

result = sync_pods_and_events_resilient(
    pods_mcp, events_mcp, namespace, cluster_id="dev-cluster"
)
# Logical thread key (logs / sync state partition): "default:dev-cluster"
sync_thread_id("dev-cluster", tenant_id="team-alpha")  # -> "team-alpha:dev-cluster"
# LangGraph API thread_id (must be UUID):
langgraph_thread_id("dev-cluster")  # -> deterministic UUID5
```

### Phase 4-2: multicluster sync partition

| Concept | Behavior |
|---------|----------|
| `thread_id` | LangGraph API: `langgraph_thread_id()` (UUID5 from logical `{tenant}:{cluster}`) |
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

Use the same LangGraph `thread_id` (UUID) for sync, query, and inspect so checkpointed graph state accumulates. `sync_*_resilient` calls `resolve_langgraph_thread_id(cluster_id=..., tenant_id=...)` when omitted. Pass `--thread-id` as a UUID or any label (mapped via UUID5). Logical key: `sync_thread_id()`.

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

## Agent phase A: inspection narrative (mock, no LLM)

Graph flow (W6): `ingest → gather → diagnose → retrieve_skills → narrate → execute → sandbox_run → verify_skill → record_skill → query → END` ([`langgraph-server/src/graph.py`](../langgraph-server/src/graph.py)).

| `payload` field | Role |
|-----------------|------|
| `inspect` | `{cluster_id, namespace, pod_name}` — triggers gather/narrate |
| `gather` | Subgraph + `run_query` facts |
| `diagnosis` | `DiagnosisReport` (rules_v1: issues, recommended_actions, severity) |
| `skill_matches` | Top-N similar past skills (FTS + synonym query) |
| `narrative` | `InspectionReport` (markdown, sections, linked_events/pods) |
| `execution` | `ExecutionResult` (`sandbox_pending` when `dry_run=false`) |
| `sandbox_result` | Docker kubectl runs + audit paths |
| `skill_verification` | `{ verified, reason, audit_run_id }` from sandbox |
| `skill_record` | Upsert result (fingerprint, path, hit_count) |
| `query` | Optional legacy `run_query` (step 6) |

```python
from agent import build_inspection_report

report = build_inspection_report(
    payload,
    cluster_id="dev-cluster",
    namespace="default",
    pod_name="shared-pod",
)
print(report["markdown"])
```

```powershell
python -m unittest tests.test_agent_narrative -v
python scripts\inspect_narrative_demo.py
```

**linked_events** = `events_for_pod` (`has_event` edges). **linked_pods** = `inspections_for_pod` (`inspects_pod`).

## Agent LLM narrative (Qwen `qwen3.6-plus`)

Polishes `markdown` and `summary` via **OpenAI-compatible API** (DashScope / 百炼), aligned with the official Model Studio sample. Default model **`qwen3.6-plus`**, China endpoint **`https://dashscope.aliyuncs.com/compatible-mode/v1`**. **`qwen3.6-flash`** still works via `SENTINEL_LLM_MODEL`. Rule diagnosis runs first; LLM may reference `issues` / `recommended_actions` in prose only. **`enable_thinking` is off by default** so JSON narrative stays stable.

| Variable | Default | Purpose |
|----------|---------|---------|
| `SENTINEL_LLM_ENABLED` | `0` | Set `1` with API key to enable |
| `DASHSCOPE_API_KEY` | — | Preferred for Qwen (or `OPENAI_API_KEY`) |
| `OPENAI_BASE_URL` | China compatible URL | Intl: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| `SENTINEL_LLM_MODEL` | `qwen3.6-plus` | Model id |
| `SENTINEL_LLM_ENABLE_THINKING` | `0` | `1` = stream + thinking (not for production narrative) |
| `SENTINEL_LLM_TIMEOUT_SEC` | `60` | HTTP timeout |

Pipeline: `gather → diagnose → retrieve_skills → template → LLM polish (optional) → execute → sandbox_run → verify_skill → record_skill`. LangGraph: `gather → diagnose → retrieve_skills → narrate` so `narrate` sees `payload.diagnosis` and `payload.skill_matches`.

```python
from agent import build_inspection_with_diagnosis, llm_narrative_config

print(llm_narrative_config())
narrative, diagnosis, execution = build_inspection_with_diagnosis(
    payload,
    cluster_id="dev-cluster",
    namespace="default",
    pod_name="crash-pod",
    use_llm=True,
)
print(narrative["narrative_source"])  # "llm" or "template"
print(narrative.get("llm_error"))
```

`payload.inspect.use_llm` or `payload.inspect.llm` = `true`. On API failure: `narrative_source=template`, `llm_error` set.

```powershell
$env:SENTINEL_LLM_ENABLED = "1"
$env:DASHSCOPE_API_KEY = "sk-..."
$env:OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
python scripts\qwen_dashscope_smoke.py
python scripts\qwen_dashscope_smoke.py --thinking
python -m unittest tests.test_agent_narrative_llm -v
python scripts\llm_narrative_demo.py
python scripts\diagnose_narrative_demo.py --pod-name crash-pod --llm
python scripts\inspect_narrative_demo.py --llm
```

## Agent phase C: tenant ACL (mock registry)

Runtime ACL over mock tenant → cluster mapping. **Omitting `tenant_id` keeps third-edition behavior** (no registry lookup, no property filter).

| Tenant | Allowed clusters |
|--------|------------------|
| `team-alpha` | `dev-cluster` |
| `team-beta` | `dev-cluster`, `prod-cluster` |

- `tenant_id` lives in **properties** and request params only; **ID strings are unchanged**.
- Unauthorized cluster → `TenantAccessError`; authorized cluster but another tenant’s entity → empty / `found: false`.
- Optional override: copy `configs/tenants.example.yaml` → `configs/tenants.yaml`.

```python
from agent import build_inspection_report

report = build_inspection_report(
    payload,
    cluster_id="dev-cluster",
    namespace="default",
    pod_name="alpha-dev-pod",
    tenant_id="team-alpha",
)
```

```powershell
python -m unittest tests.test_tenant_acl tests.test_agent_tenant_narrative -v
python scripts\inspect_narrative_demo.py --tenant-id team-alpha --cluster-id dev-cluster
python scripts\inspect_narrative_demo.py --tenant-id team-alpha --cluster-id prod-cluster
```

Fixture: `tenant_acl_matrix_batch()` — four cells (alpha/beta × dev/prod) in one payload.

## LangGraph dev 接入清单

``LANGGRAPH_RUN_LIVE=1`` means the **local** ``langgraph dev`` HTTP API (``agents/langgraph-server``), not LangGraph Cloud unless you point ``LANGGRAPH_API_URL`` at cloud and set ``LANGGRAPH_API_KEY``.

| Step | Command / check |
|------|-----------------|
| 1. Start server | ``cd agents/langgraph-server`` → ``langgraph dev`` (note port, usually 2024). **Windows:** keep ``.env`` ASCII-only (UTF-8 Chinese comments break ``python-dotenv`` under GBK). |
| 2. Env | ``LANGGRAPH_API_URL=http://127.0.0.1:2024`` ``LANGGRAPH_RUN_LIVE=1`` |
| 3. Verify | ``python scripts/langgraph_live_verify.py`` (connectivity, graph ``sentinel``, thread create, inspect) |
| 4. Inspect demo | ``python scripts/inspect_langgraph_live_demo.py --pod-name crash-pod`` |

**Thread IDs:** ``langgraph_thread_id()`` returns a valid UUID (UUID5 from ``tenant:cluster``). The SDK also requires the thread to **exist** on the server — ``stream_sentinel_run`` calls ``ensure_langgraph_thread()`` (``threads.create`` when missing). Logical key for logs: ``sync_thread_id()``.

**Errors:** ``badly formed hexadecimal UUID`` → use ``langgraph_thread_id`` / ``resolve_langgraph_thread_id``, not ``default:dev-cluster`` directly. ``Thread or assistant not found`` → run verify script; ensure ``langgraph dev`` is up and graph ``sentinel`` is in ``langgraph.json``.

## Agent phase F: diagnosis + action registry (LangGraph E2E)

**Inspect E2E** on LangGraph dev: sync/query optional; pass mock graph + ``payload.inspect`` in one run.

| Piece | Role |
|-------|------|
| [`get_inspect_outputs_from_stream`](src/clients/langgraph_client.py) | Read ``gather`` / ``narrative`` / ``diagnosis`` / ``execution`` / ``skill_*`` from stream |
| [`src/skills/`](src/skills/) | W5: SQLite FTS retrieval + skill writer; ``retrieve_skills`` → ``record_skill`` graph nodes |
| [`agent/actions/`](src/agent/actions/) | ``ActionHandler`` registry; built-ins simulated; unknown → ``skipped`` |
| [`execute.py`](src/agent/execute.py) | ``execution_source=registry_v1``; tenant ACL at execute via ``validate_execution_policy`` |

```powershell
$env:LANGGRAPH_API_URL = "http://127.0.0.1:2024"
$env:LANGGRAPH_RUN_LIVE = "1"
python scripts\langgraph_live_verify.py
python scripts\inspect_langgraph_live_demo.py --pod-name crash-pod
python scripts\full_pipeline_demo.py --live --inspect
python -m unittest tests.test_langgraph_inspect_live tests.test_agent_diagnose -v
```

Live K8s writes remain **off** unless ``SENTINEL_EXECUTE_LIVE=1`` and handlers are wired (phase 4-0b / Action MCP).

## W6 Sandbox (pre-run)

Docker + kubectl whitelist; **only** `sentinel-sandbox` namespace (production namespaces → `blocked` + audit).

| Module | Role |
|--------|------|
| [`src/sandbox/runner.py`](src/sandbox/runner.py) | `run_sandbox_for_execution` orchestration |
| [`src/sandbox/planner.py`](src/sandbox/planner.py) | `restart_pod` / `scale_up` → kubectl argv |
| [`src/sandbox/policy.py`](src/sandbox/policy.py) | Default-deny command validation |
| [`sandbox/Dockerfile`](../../sandbox/Dockerfile) | Executor image |

```powershell
docker build -t sentinel-x-sandbox:latest sandbox/
kubectl apply -f sandbox/fixtures/crash-loop-deployment.yaml
python scripts\demo\sandbox_demo.py --pod-name crash-demo-xxxxx
python -m unittest tests.test_sandbox_policy tests.test_sandbox_integration -v
```

`dry_run=false` without `SENTINEL_EXECUTE_LIVE=1` → sandbox only (never production writes).

## W5 Skills (retrieve + record)

SQLite FTS5 store under repo [`skills/`](../../skills/). Graph layer uses ``SkillStore`` Protocol — swap to Chroma/PGVector later without changing nodes.

| Module | Role |
|--------|------|
| [`src/skills/store.py`](src/skills/store.py) | ``SqliteFtsSkillStore``: index, search, fingerprint dedup |
| [`src/skills/retrieve.py`](src/skills/retrieve.py) | ``ISSUE_SYNONYMS``, ``build_search_query``, ``retrieve_for_diagnosis`` |
| [`src/skills/writer.py`](src/skills/writer.py) | ``build_skill_markdown`` — frontmatter = general knowledge; Evidence = pod context |
| [`src/skills/fingerprint.py`](src/skills/fingerprint.py) | Sorted issues/actions → 16-char sha256 |

| Env | Default | Purpose |
|-----|---------|---------|
| `SENTINEL_SKILLS_DIR` | `{repo}/skills` | Markdown root |
| `SENTINEL_SKILLS_DB` | `{dir}/.index/skills.db` | FTS index |
| `SENTINEL_SKILLS_RECORD` | `1` | `0` disables auto-write after inspect |
| `SENTINEL_SKILLS_SEARCH_LIMIT` | `3` | Top-N matches (deduped by fingerprint) |

Narrative adds ``## Similar past skills`` when matches exist. Second inspect on the same CrashLoop scenario should surface the seed example or a prior record.

```powershell
python scripts\demo\skill_write_demo.py
python -m unittest tests.test_skills_store tests.test_skills_fingerprint tests.test_skills_writer tests.test_skills_retrieve_integration -v
```

See also [`skills/README.md`](../../skills/README.md) and [`docs/deploy/DEPLOY-REFERENCE.md`](../../docs/deploy/DEPLOY-REFERENCE.md#skills-环境w5).

## Agent phase D/E: diagnosis + execute stub

Rule engine over gather facts (same queries as narrative); **no live K8s/MCP write APIs**.

| Rule signal | Issue | Action |
|-------------|-------|--------|
| `CrashLoopBackOff` / `BackOff` event | `CrashLoop` | `restart_pod` |
| `FailedScheduling` | `SchedulingFailure` | `check_node_capacity` |
| OOM in event | `OOM` | `scale_up` |
| Inspection not ok | `InspectionFailed` | `run_inspection` |
| Warning events only | `WarningEvents` | `review_events` |

Omitting `tenant_id` keeps third-edition gather/query behavior; ACL still applies in gather when `tenant_id` is set.

```python
from agent import build_inspection_with_diagnosis

narrative, diagnosis, execution = build_inspection_with_diagnosis(
    payload,
    cluster_id="dev-cluster",
    namespace="default",
    pod_name="crash-pod",
    dry_run=True,
)
```

`payload.inspect.dry_run` (default `true`) controls the LangGraph `execute` node. Live execution requires `SENTINEL_EXECUTE_LIVE=1` and is **not implemented** in this phase (`NotImplementedError` if `dry_run=false`).

**Performance:** `gather_subgraph` parses the graph once and runs all pod-scoped queries on the same `GraphView`. Pass a pre-built `gather` into `build_inspection_report` / `build_inspection_with_diagnosis` after the LangGraph `gather` node to avoid a second scan.

**Errors:** `on_error="mark"` returns `ok=False` and `error` / `error_stage` on narrative/diagnosis/execution instead of raising. Default remains `on_error="raise"`.

**LLM latency:** `SENTINEL_LLM_TIMEOUT_SEC` (default 60) applies to the HTTP client; failures/timeouts fall back to template (`llm_error` set when polish fails).

```powershell
python -m unittest tests.test_agent_diagnose -v
python scripts\diagnose_narrative_demo.py --cluster-id dev-cluster --pod-name crash-pod
python scripts\diagnose_narrative_demo.py --tenant-id team-alpha --cluster-id dev-cluster --matrix
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
