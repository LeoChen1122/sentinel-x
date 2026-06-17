# Changelog

All notable changes to Sentinel-X are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Project ops layer: `docs/adr/`, `docs/architecture/`, `docs/dev-log/`, CHANGELOG
- GitHub import templates under `docs/.github-import/`

### Changed

- README restructured for portfolio + engineering sections (bilingual)

---

## [0.4.0] - 2026-06-17

### Added

- P0 one-shot install: `deploy/install/install-sentinel-x.sh`, `verify --full`
- Skills storage + SQLite FTS retrieval (W5)
- Docker sandbox executor + `sentinel-sandbox` namespace policy (W6)
- W7 trigger layer: `trigger/patrol.py`, `trigger/inspect_trigger.py`, cron patrol
- FastAPI optional layer: `POST /v1/inspect`, Alertmanager webhook routes
- Streamlit minimal UI (W4)
- Dual-namespace sync cron (kube-system + sentinel-sandbox)

### Changed

- MCP pod normalization for accurate CrashLoop detection
- Deploy matrix and architecture review v3

### Fixed

- Patrol false positives from stale BackOff events
- Config apply propagates `SENTINEL_API_TOKEN` to API env

---

## [0.3.0] - 2026-05

### Added

- Prometheus MCP server (`prom_query`, `prom_query_range`)
- Prom metrics sync into LangGraph thread (`cpu_cores`, `memory_bytes`)
- Query helpers: `top_pods_by_cpu`, `pod_metrics`
- Offline kube-prometheus bundle (`dist/kube-prometheus-offline/`)

### Changed

- Pod adapter enriched with Prometheus metrics

---

## [0.2.0] - 2026-04

### Added

- LangGraph inspection pipeline: gather → diagnose → execute → query
- Rule-based diagnosis and action registry (dry-run)
- LangGraph integration layer: adapter, sync, query clients
- Unit test suite for integration package (~180+ cases)

### Changed

- Moved from demo scripts to systemd-managed `langgraph dev` on server

---

## [0.1.0] - 2026-03

### Added

- Kubernetes MCP server (`k8s_get_pods`, `k8s_get_events`)
- K8s → LangGraph live sync pipeline
- `list_pods`, `pod_status`, `events_for_pod` query API
- MCP docker compose layout
- Initial deploy runbooks (`docs/deploy/`)

[Unreleased]: https://github.com/your-org/sentinel-x/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/your-org/sentinel-x/releases/tag/v0.4.0
[0.3.0]: https://github.com/your-org/sentinel-x/releases/tag/v0.3.0
[0.2.0]: https://github.com/your-org/sentinel-x/releases/tag/v0.2.0
[0.1.0]: https://github.com/your-org/sentinel-x/releases/tag/v0.1.0
