# Sentinel-X 架构评审

> **评审日期**：2026-06-04  
> **基线**：W1–W4 生产服务器 live 验收已通过（k3s + MCP + LangGraph + cron sync + 可选 Prom + Streamlit UI）  
> **范围**：`agents/`、`mcp-servers/`、`apps/`、`deploy/`、`docs/`、`dist/`

---

## 1. 当前架构（实际 vs README 愿景）

### 1.1 组件映射

| 组件 | 实际位置 | README / 愿景 | 状态 |
|------|----------|---------------|------|
| K8s MCP | `mcp-servers/k8s/` + `docker-compose.yml` | MCP 工具层 | **Live** |
| Prometheus MCP | `mcp-servers/prometheus/` | 同上 | **Live** |
| 数据面（Adapter / Sync / Query） | `agents/langgraph-integration/src/` | LangGraph 集成 | **Live** |
| 编排图（ingest → gather → diagnose → …） | `agents/langgraph-server/src/graph.py` | Agent 图 | **Live** |
| 运维脚本 | `deploy/*.sh`、`deploy/*.service` | deploy 模板 | **Live** |
| 部署文档 | `docs/deploy/DEPLOY-*.md`（8 篇 + ROADMAP） | 文档 | **Live，偏冗长** |
| Streamlit UI | `apps/ui/app.py` | MVP UI | **Minimal live** |
| 离线 Prom bundle | `dist/kube-prometheus-offline/` | 未在 README 树中列出 | **Live（运维用）** |
| FastAPI `apps/api` | — | W7 可选 | **未实现** |
| `sandbox/`、`skills/` | — | W5/W6 | **未实现** |
| 根目录 `docker-compose.yml` | — | 统一 compose | **未实现**（仅 `mcp-servers/`） |
| 顶层 `configs/clusters.yaml` | `agents/langgraph-integration/configs/tenants.example.yaml` | 多集群配置 | **仅 mock/示例** |

### 1.2 运行时拓扑（与生产一致）

```text
[k3s API :6443]
       │ kubeconfig（宿主机 ~/.kube，经 sync-kubeconfig 改写 server）
       ▼
[MCP-K8s 容器] ──docker exec──► mcp_k8s_sync_live.py ──┐
[MCP-Prom 容器] ──docker exec──► mcp_prom_sync_live.py ─┤
       ▲ host.docker.internal:30909                      │
[Prometheus NodePort]（可选，离线 helm）                  ▼
                                              [langgraph dev :2024]
                                              in-memory checkpoint
                                                       │
                                    query / inspect / top_pods_by_cpu
                                                       │
                                              [Streamlit :8501]（可选）
```

### 1.3 与 README「目录结构」差距

- README 已用 **Implementation status** 表标注差距，W4 后基本诚实；仍缺：`dist/` 说明、一键安装入口（本次 P0 补 `install-sentinel-x.sh`）。
- 愿景中的 **微沙箱、Skills、根 compose** 未落地，不影响当前 Phase 1 闭环，但易造成新人按旧版桌面方案找目录。

---

## 2. 架构合理性

### 2.1 数据流

| 阶段 | 路径 | 评价 |
|------|------|------|
| 采集 | MCP 容器内调 K8s/Prom API → JSON | 清晰；容器隔离 API 凭证 |
| 传输 | `mcp_k8s.py` / `mcp_prom.py` 经 `docker exec` 拉 JSON | 务实，免 MCP HTTP 网关；强依赖容器名 |
| 适配 | `adapter/k8s.py`、`adapter/metrics.py` → `GraphBatch` | 边界清楚 |
| 写入 | `sync/pipeline.py` → LangGraph `ingest` stream | 与 query 共用 thread，设计正确 |
| 读取 | `query/operations.py` + `graph.py` query 节点 | 单线程图视图一致 |
| 诊断 | `agent/gather` → `diagnose` → `narrative` → `execute`（dry-run） | 与 sync 解耦，适合 inspect |

**增量 sync**：`sync/state.py` 指纹 + `/var/lib/sentinel/sync-state` 分区，cron 友好；LangGraph 重启后靠 cron 重建图，与 in-memory checkpoint 形成 **可接受的运维契约**。

### 2.2 边界与耦合

**做得好的：**

- MCP 与 integration **进程分离**（容器 vs venv Python），升级 MCP 镜像不影响 LangGraph。
- `langgraph-server` 图薄包装，业务在 `langgraph-integration/src`，避免双份 diagnose 逻辑。
- `deploy/` 仅 shell/systemd，不嵌入 Python 业务。

**耦合点（可接受但需文档）：**

- `graph.py` 通过 `sys.path.insert` 导入 integration（见 §3.2）。
- 容器名、`thread_id`、`cluster_id` 散布在 env、cron、UI 默认值（`5ad00ee0-...` = `uuid5("default:k3s-prod")`）。
- Prom 依赖 **NodePort + host.docker.internal**，与 k3s 网络模型绑定。

### 2.3 分层评价

| 层 | 文件示例 | 结论 |
|----|----------|------|
| MCP tools | `mcp-servers/k8s/src/tools/` | 薄，合适 |
| Clients | `clients/mcp_k8s.py`, `mcp_prom.py` | 对称性好 |
| Adapter | `adapter/k8s.py`, `metrics.py` | 必要，非过度抽象 |
| Sync | `sync/pipeline.py` | 略长（~350 行）但职责集中 |
| Query | `query/operations.py` | 操作注册清晰 |
| Agent | `agent/diagnose.py`, `narrative.py` | 规则+模板为主，LLM 可选 |

---

## 3. 代码健康

### 3.1 测试覆盖

| 区域 | 位置 | 约略规模 | 覆盖质量 |
|------|------|----------|----------|
| Integration 单测 | `agents/langgraph-integration/tests/` | ~24 文件，150+ `def test_` | **强**：adapter、sync、query、agent、multicluster mock |
| MCP Prom/K8s fetch | `test_mcp_k8s_fetch.py`, `test_mcp_prom_fetch.py` | 快照/解析 | 中（非真 docker） |
| LangGraph server | `agents/langgraph-server/tests/test_graph_nodes.py` | 少量 smoke | **弱**（W4 刚补） |
| MCP 服务 | `mcp-servers/prometheus/tests/` | prom 工具 | 中；k8s 仅 mock |
| E2E live | `test_langgraph_inspect_live.py` | 需环境 | 默认 skip |
| UI | — | 无 | **缺口** |
| deploy 脚本 | — | 无 shell 测试 | 依赖手工 + `bash -n` |

**结论**：核心业务逻辑单测充分；**生产路径**（docker exec、systemd、cron）主要靠文档与 live 验收，自动化 E2E 不足。

### 3.2 `sys.path` 注入

广泛存在于：

- `agents/langgraph-server/src/graph.py`（生产关键路径）
- `agents/langgraph-integration/scripts/*.py`、几乎全部 `tests/*.py`
- `apps/ui/app.py`
- `mcp-servers/*/src/server.py`

**原因**：`langgraph-integration/src` 非安装型 package（无 `pyproject.toml` 可编辑安装），monorepo 快速迭代。

**风险**：IDE/类型检查不友好；重命名目录易静默失败；与 `pip install -e` 最佳实践不符。

**建议（P1）**：对 integration 增加最小 `pyproject.toml` + `pip install -e .`，逐步去掉生产路径上的 path hack。

### 3.3 错误处理

- `utils/errors.py`、`sync/retry.py`：重试与 resilient push **一致**。
- MCP clients：`RuntimeError` + docker stderr，够用。
- Shell：`sync-k8s.sh` / `sync-prom.sh` 有 flock、日志、LangGraph 可达性 WARN。
- **缺口**：`docker exec` 失败时少结构化错误码；UI 对 API 失败仅 `st.error` 文本。

### 3.4 客户端一致性（`mcp_k8s` vs `mcp_prom`）

| 能力 | `mcp_k8s.py` | `mcp_prom.py` |
|------|--------------|---------------|
| docker exec 内联脚本 | ✅ | ✅ |
| snapshot 文件 | ✅ | ✅ |
| TypedDict / Mcp*Response | ✅ | ✅ |
| attach_cluster_id | ✅ | N/A（Prom 在 sync 层合并） |

**对称性良好**；Prom 多 PromQL 环境变量，文档已在 `sync-prom.env.example`。

---

## 4. 冗余 / 膨胀（具体路径）

### 4.1 文档重复

- **同一 `thread_id`、容器名、验证命令** 在以下文件中重复出现 5–10 次：  
  `docs/deploy/DEPLOY-SERVER.md`、`DEPLOY-SYNC-CRON.md`、`DEPLOY-PROM-SYNC.md`、`DEPLOY-UI-LIVE.md`、`DEPLOY-INSPECT-LIVE.md`、`DEPLOY-LANGGRAPH-SYSTEMD.md`、`ROADMAP.md §8`、`apps/ui/README.md`。
- **缓解**：以 `DEPLOY-SERVER.md` + 新建 `DEPLOY-ONE-SHOT.md` 为入口，子文档只保留差异步骤。

### 4.2 脚本与 bundle 重复

- `deploy/prometheus/install-kube-prometheus-offline.sh` 与 `dist/kube-prometheus-offline/install-kube-prometheus-offline.sh` **内容镜像**（维护两份；dist 由 PS1 复制）。
- `deploy/prometheus/kube-prometheus-values-minimal.yaml` 与 bundle 内 values 可能漂移。

### 4.3 代码层

| 项 | 路径 | 说明 |
|----|------|------|
| 多集群 mock | `sync/multicluster.py`, `tests/test_multicluster*.py` | live 未用，但为 Phase 4 预留，**可保留** |
| demo 脚本 | `agents/langgraph-integration/scripts/demo/`（10+） | 已从 `scripts/live/` 隔离；非运行时 |
| MCP tar 产物 | `mcp-servers/images/*.tar` | 可能与 `docker build` 重复；确认是否仍需要 scp 预构建 |
| `dist/kube-prometheus-offline/` 体积 | 整 chart 入库 | 离线必需，但拉高 clone/scp 成本；宜与源码分包 |

### 4.4 死代码 / 未接线

- README 规划的 `apps/api`、`sandbox/`、`skills/`：**无实现**（非死代码，是占位）。
- `langgraph-server/.langgraph_api/*.pckl`：本地 dev 产物，应在 `.gitignore`（若已跟踪则污染仓库）。

### 4.5 过度抽象？

**总体否**。Adapter + Sync + Query 三分合理；未引入多余 Repository/DAO 层。  
唯一可议点：`query/graph_view.py` 与 `utils/graph_merge.py` 概念重叠，但行数可控。

---

## 5. 风险与技术债

| 风险 | 严重度 | 现状 / 缓解 |
|------|--------|-------------|
| **LangGraph in-memory checkpoint** | P0 运维 | **已整改**：Checkpoint 契约 + `ExecStartPost` hook + `verify --after-restart`；Phase 2 见 ROADMAP W8+ |
| **docker-compose 1.29 `ContainerConfig`** | P1 运维 | `docker rm` + `up -d`（`DEPLOY-MCP-KUBECONFIG.md`）；建议统一 `docker compose` v2 |
| **离线 / 无 GitHub** | P0 部署 | scp 全仓库 + `dist/` bundle；一键脚本不依赖外网 |
| **环境变量分散** | P1 | **已整改**：`/etc/sentinel/sentinel-x.env` SSOT + `sentinel-config-discover/apply` |
| **thread_id 硬编码在 UI** | P2 | **已整改**：`apps/ui/app.py` 使用 `resolve_langgraph_thread_id` |
| **k3s RC + 无 systemd 历史** | P2 | 生产已 enable；新机需前置检查 |
| **MCP kubeconfig 127.0.0.1** | P0 | `sentinel-sync-kubeconfig.sh` 已固化 |
| **执行层 live 写 K8s** | 安全 | 当前 dry-run only；未来需审批与策略 |
| **评估报告与代码脱节** | 文档 | W4 README 已同步；需保持 ROADMAP 周更 |

---

## 6. 建议（按优先级）

### P0（新服务器下周落地） — **已完成（W23 技术债整改）**

1. **一键安装**：`deploy/install/install-sentinel-x.sh` + `docs/deploy/DEPLOY-ONE-SHOT.md` ✅
2. **安装后验证脚本**：`deploy/verify/verify-sentinel-x.sh`（含 `--after-restart`）✅
3. **Checkpoint 契约**：`docs/deploy/DEPLOY-REFERENCE.md` + post-restart hook ✅
4. **配置 SSOT**：`deploy/config/sentinel-config-discover.sh` + `sentinel-config-apply.sh` ✅

### P1（1–2 周内） — **部分已完成**

1. **`pip install -e` integration package**，去掉 `graph.py` / UI 的 `sys.path`。（待做）
2. **合并 kube-prometheus 安装脚本** 为单一来源 ✅（`deploy/` canonical，`dist/` copy only）
3. **docker compose v2** 检测写入 installer；弃用 v1 混用说明。（待做）
4. **收敛 DEPLOY 文档** ✅ — [deploy/DEPLOY-REFERENCE.md](deploy/DEPLOY-REFERENCE.md) + 子文档瘦身

### P2（Phase 2 前）

1. LangGraph **持久化 checkpoint** 调研（官方 Postgres）— 见 [ROADMAP.md](ROADMAP.md) W8+ Checkpoint Phase 2。
2. **结构化配置**：`configs/clusters.yaml` 驱动 sync cron 多实例（替代多份 env）。
3. UI / inspect **集成测试**（mock LangGraph SDK）。
4. ~~**清理** demo 脚本目录或移到 `examples/`~~ ✅ 已迁至 `scripts/demo/`

---

## 7. 总结

Sentinel-X 在 Phase 1 目标上 **架构方向正确**：MCP 采集 → Adapter/Sync → LangGraph 单 thread 图 → Query/Inspect/UI，边界与生产验收一致。主要技术债集中在 **运维体验**（env 分散、文档重复、compose 版本、内存 checkpoint），而非核心业务建模。代码单测覆盖 integration 层较充分，生产 E2E 与 packaging（`sys.path`）是下一阶段的性价比最高的改进点。

**公平评价**：在 W1–W4 live 已通过的前提下，当前结构适合继续 W5 Skills / W6 沙箱；不宜在大重构前阻塞，应优先 **一键部署 + 配置收敛 + checkpoint 路线图**。
