# GitHub Release Notes (copy-paste)

Draft each release on GitHub → **Releases** → **Draft a new release**. Replace `your-org/sentinel-x` in tag URLs after publishing.

---

## v0.4.0 — One-shot Deploy + Alert Auto Close

**Title:** v0.4.0 — One-shot Deploy + Alert Auto Close  
**Tag:** `v0.4.0`  
**Target:** `main` (or commit at W25/W26 milestone)

### Added

- One-command server install (`install-sentinel-x.sh`) with `verify --full`
- Skills framework with SQLite FTS5 retrieval (W5)
- Docker sandbox pre-run for whitelisted kubectl (W6)
- W7 alert patrol cron + inspect trigger (`crash-demo` → `CrashLoop`)
- Optional FastAPI: `/health`, `POST /v1/inspect`, Alertmanager webhook handler
- Streamlit UI on `:8501`
- Sandbox fixture namespace sync cron

### Changed

- Architecture review v3; deploy matrix live evidence columns
- MCP pod status normalization for CrashLoopBackOff

### Fixed

- Patrol false positives from the kube-system BackOff events
- API token propagation via `sentinel-config-apply.sh`

---

## v0.3.0 — Prometheus MCP

**Title:** v0.3.0 — Prometheus MCP  
**Tag:** `v0.3.0`

### Added

- Prometheus MCP tools and live metrics sync
- `top_pods_by_cpu` / `pod_metrics` graph queries
- Offline kube-prometheus installer bundle

### Changed

- Pod entities enriched with CPU/memory from Prometheus

### Fixed

- Prom MCP connectivity via `host.docker.internal` NodePort pattern

---

## v0.2.0 — Agent Runtime

**Title:** v0.2.0 — Agent Runtime  
**Tag:** `v0.2.0`

### Added

- LangGraph multi-node inspect pipeline
- Integration package: adapter, sync, query, agent execute (dry-run)
- Systemd unit for LangGraph on production server

### Changed

- Structured graph state for inspections and entities

### Fixed

- Sync retry and chunking for large event lists

---

## v0.1.0 — Monitoring MVP

**Title:** v0.1.0 — Monitoring MVP  
**Tag:** `v0.1.0`

### Added

- Kubernetes MCP server and docker compose
- K8s → LangGraph sync and `list_pods` query
- Initial deploy documentation and sync cron

### Changed

- Repository layout: `agents/`, `mcp-servers/`, `deploy/`

### Fixed

- Kubeconfig inside MCP container for k3s host-gateway access
