# GitHub Release Notes (copy-paste) / 发布说明（复制粘贴）

Draft on GitHub → **Releases** → **Draft a new release**.  
在 GitHub **Releases** → **Draft a new release** 创建。

Replace `your-org/sentinel-x` in [CHANGELOG.md](../../CHANGELOG.md) after publishing.  
发布后请将 CHANGELOG 中的 `your-org/sentinel-x` 改为真实仓库路径。

**Paste the English blocks below into the release form.**  
**下方英文块粘贴到 Release 表单即可**（中文摘要仅供阅读）。

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

### 中文摘要

- 新增：一键安装、Skills FTS、Docker 沙箱、W7 巡检与 API inspect、Streamlit UI
- 变更：架构评审 v3、MCP CrashLoop 状态规范化
- 修复：巡检误报、API Token 配置传递

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

### 中文摘要

- 新增：Prom MCP、指标同步、top_pods_by_cpu、离线 Prom 安装包
- 变更：Pod 实体 enriched CPU/内存
- 修复：Prom MCP 经 NodePort 连通

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

### 中文摘要

- 新增：LangGraph 多节点 inspect 流水线、integration 包、systemd 部署
- 变更：图状态结构化
- 修复：大 event 列表 sync 重试与分块

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

### 中文摘要

- 新增：K8s MCP、sync、list_pods、部署文档与 cron
- 变更：仓库目录结构 agents / mcp-servers / deploy
- 修复：MCP 容器内 kubeconfig 访问 k3s

---

## Publish order | 发布顺序

`v0.1.0` → `v0.2.0` → `v0.3.0` → `v0.4.0` (set **latest** on v0.4.0 only)

See [README.md](README.md) for full steps | 完整步骤见 README.md
