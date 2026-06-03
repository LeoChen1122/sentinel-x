# Sentinel-X 项目总纲

> 本文档为 **主路线图**：概括当前进度、按优先级排列的后续周计划，以及每周总结的索引。  
> 每周结束后在 [`docs/weekly/`](weekly/) 新增一份周总结，并回链到本文档对应周次。

**最后更新**：2026-06-02  
**当前阶段**：Phase 1b — K8s live sync 已打通，进入验收与运维固化

---

## 1. 项目目标（MVP 一句话）

让 Agent **看见**云原生系统（Pod / Event / 指标），**判断**故障类型，**试**在沙箱预演修复，**记**沉淀 Skills——形成「查 / 判 / 试 / 记」闭环。

---

## 2. 阶段对照表

| 阶段 | 文档来源 | 目标 | 整体进度 |
|------|----------|------|----------|
| Phase 0 | README | 目录、Skill 模板、工程底座 | 80% |
| Phase 1 | 桌面「看见系统」 | MCP + Agent 可查询 Pod/指标 | **70%** |
| Phase 1b | 桌面 phase1b guide | K8s MCP → LangGraph live sync | **首通完成，验收中** |
| Phase 3 | LangGraph 集成（第三版） | Adapter / Sync / Query 数据面 | 代码 90%，live 60% |
| Phase 4 | 多集群（第四版） | cluster_id / tenant 隔离 | mock 100%，live 0% |
| Phase 5 | Diagnosis / 动作层 | gather → diagnose → execute | 代码 75%，live 20% |
| MVP 2–5 | 第一版开发方案 | 沙箱 / Skills / Streamlit UI | 0–25% |

---

## 3. 当前进度概况（截至 2026-06-02）

### 3.1 已完成

| 模块 | 内容 | 位置 / 证据 |
|------|------|-------------|
| K8s MCP | `k8s_get_pods` / `k8s_get_events`，FastMCP stdio | `mcp-servers/k8s/` |
| Prometheus MCP | `prom_query` / `prom_query_range`（未进 sync 链） | `mcp-servers/prometheus/` |
| 图模型与 Adapter | Pod / Event / Node / Inspection，稳定 ID | `agents/langgraph-integration/src/models/` |
| Sync 管道 | 增量、重试、分块、多集群 mock | `src/sync/` |
| Query | `list_pods`、`pod_status`、`events_for_pod` 等 6 个 op | `src/query/` |
| LangGraph 图 | ingest → gather → diagnose → narrate → execute → query | `agents/langgraph-server/src/graph.py` |
| Agent | 规则诊断、模板/LLM 叙事、动作注册表（模拟） | `src/agent/` |
| 单测 | ~175 用例，23 个 test 文件 | `agents/langgraph-integration/tests/` |
| **服务器 live** | k3s 离线恢复；MCP kubeconfig 宿主机 IP；sync 成功 | 7 pods / 65 events → 66 entities |

**Live sync 关键参数（生产服务器）**：

```text
cluster_id   = k3s-prod
namespace    = kube-system
thread_id    = 5ad00ee0-6f4d-5cd6-a021-99469a86e4e1
MCP_CONTAINER= mcp-servers_mcp-k8s_1
LANGGRAPH    = http://127.0.0.1:2024
```

### 3.2 进行中 / 未验收

- Live `list_pods` / `events_for_pod` 查询验收
- `langgraph dev` systemd 常驻、cron 增量 sync
- 真实 Pod 上 inspect → diagnose → execute(dry-run) E2E
- 仓库 `deploy/` 运维模板入库

### 3.3 未开始（按 MVP 愿景）

- Prometheus → 图 / 查询（Phase 1 指标目标）
- Streamlit UI、`apps/api`
- Skills 存储与检索（Markdown + Chroma）
- Docker / gVisor 沙箱预演
- Live K8s 写操作（restart_pod 等）
- 多集群 live（`configs/clusters.yaml`）

### 3.4 架构现状

```text
[k3s API] ← kubeconfig ← [MCP 容器] ← docker exec ← [mcp_k8s_sync_live]
                                                          ↓
                                              [langgraph dev :2024]
                                                          ↓
                                    [query / inspect / diagnose]（部分 live 待验收）
```

---

## 4. 优先级原则

1. **P0 — 闭环可演示**：live 数据能查、能 inspect，服务可重启恢复  
2. **P1 — Phase 1 补全**：Prometheus 进图，回答 CPU/内存类问题  
3. **P2 — 可观测与协作**：最小 UI、周总结与 deploy 文档  
4. **P3 — MVP 深水区**：Skills、沙箱、live execute  
5. **P4 — 扩展**：多集群 live、Action MCP、Loki 等  

---

## 5. 后续周计划（按优先级）

> 以 **2026-06-02** 为 W1 起点；每周末在 `docs/weekly/` 填写对应文件，勾选完成项并记录阻塞项。

### W1（当前周）— P0：Phase 1b 验收与运维固化

**目标**：从「sync 成功一次」变为「可持续看见系统」。

| 序号 | 任务 | 产出 / 验收 |
|------|------|-------------|
| W1-1 | Live query 验收 | `list_pods` 返回 ~7；`events_for_pod` 有数据 |
| W1-2 | langgraph systemd | 重启后服务自启；文档记录端口与 `.env` 要求 → **[DEPLOY-LANGGRAPH-SYSTEMD.md](DEPLOY-LANGGRAPH-SYSTEMD.md)** |
| W1-3 | cron 增量 sync | 每 5min `mcp_k8s_sync_live.py`；日志 `/var/log/sentinel-sync.log` |
| W1-4 | MCP kubeconfig 固化 | `~/.kube/config` 用宿主机 IP；compose 可选 `extra_hosts` |
| W1-5 | deploy 入库 | `deploy/sentinel-langgraph.service`、`deploy/sync-k8s.sh` |
| W1-6 | 代码对齐 | 服务器 `mcp_k8s.py` 与仓库 stdin 版一致 |

**W1 完成标准**：cron 跑满 24h 无报错；query 与 kubectl pod 数一致。

---

### W2 — P0：Live Inspect + 诊断 E2E

**目标**：对齐第五版「Diagnosis Engine」，对 **真实集群 Pod** 跑通 inspect 链。

| 序号 | 任务 | 产出 / 验收 |
|------|------|-------------|
| W2-1 | 选目标 Pod | kube-system 系统 Pod 或自建 crash 测试 Pod |
| W2-2 | inspect live | `inspect_langgraph_live_demo.py --live` 出 gather/diagnosis/narrative |
| W2-3 | execution dry-run | `execution` 含模拟 `restart_pod` 等，无 live 写 |
| W2-4 | 可选 LLM | DashScope 开启后 narrative_source=llm |
| W2-5 | 文档 | 更新 ROADMAP §3 + 周总结 W2 |

**W2 完成标准**：stream 中四类输出齐全；diagnosis.issues 对 crash Pod 非空（若用测试 Pod）。

---

### W3 — P1：Prometheus 进图（Phase 1c）

**目标**：补桌面 Phase 1「CPU/内存」查询能力。

| 序号 | 任务 | 产出 / 验收 |
|------|------|-------------|
| W3-1 | `clients/mcp_prom.py` | docker exec 或 snapshot 拉 Prom MCP JSON |
| W3-2 | `scripts/mcp_prom_sync_live.py` | 指标映射到图或 Pod 属性 |
| W3-3 | Adapter 扩展 | 指标实体或 enrichment 字段 |
| W3-4 | Query op | 如 `top_pods_by_cpu` 或 `pod_metrics` |
| W3-5 | 单测 + 服务器验收 | mock + 可选 live（Prometheus 可达） |

**W3 完成标准**：sync 后能回答「哪个 Pod CPU 使用最高」（Phase 1 原文验收项）。

---

### W4 — P2：最小演示面 + 工程文档

**目标**：非 CLI 也能看结果；换机可复现部署。

| 序号 | 任务 | 产出 / 验收 |
|------|------|-------------|
| W4-1 | Streamlit 最小页 | list_pods + inspect 结果展示 |
| W4-2 | 部署指南 | `docs/DEPLOY-SERVER.md`（k3s 离线、MCP、LangGraph、sync） |
| W4-3 | README 同步 | 根 README 与实现差距标注（评估报告过时项修正） |
| W4-4 | langgraph-server  smoke 测试 | 至少 1 个 graph 节点单测 |

**W4 完成标准**：浏览器打开 UI 可见 live pod 列表；新人按 DEPLOY 文档可复现 W1。

---

### W5 — P3：Skills 基础（「记」）

**目标**：诊断结果可沉淀、可检索。

| 序号 | 任务 | 产出 / 验收 |
|------|------|-------------|
| W5-1 | `skills/` 目录与模板 | 对齐 README Skill 示例 |
| W5-2 | skill_writer 节点或脚本 | 成功 inspect 后生成 Markdown |
| W5-3 | 检索 | SQLite FTS 或 Chroma 最小集成 |
| W5-4 | Agent 接入 | diagnose 后检索相似 Skill 摘要 |

**W5 完成标准**：同一 CrashLoop 场景第二次可命中历史 Skill 摘要。

---

### W6 — P3：沙箱预演（「试」）

**目标**：修复命令不进生产，先进受限容器。

| 序号 | 任务 | 产出 / 验收 |
|------|------|-------------|
| W6-1 | `sandbox/` 模块 | Docker 受限执行 kubectl 子集 |
| W6-2 | planner + sandbox_verifier | LangGraph 或 integration 编排 |
| W6-3 | 审计日志 | 命令、stdout、exit code 落盘 |
| W6-4 | 与 execute 衔接 | dry_run=false 仍只进沙箱，不触生产 |

**W6 完成标准**：restart/scale 类命令在沙箱跑通并出审计记录。

---

### W7 — P3：告警入口 + 半自动闭环

**目标**：从「人工 query」到「事件驱动一次诊断」。

| 序号 | 任务 | 产出 / 验收 |
|------|------|-------------|
| W7-1 | 告警/Webhook 或 cron 巡检 | Event 阈值触发 inspect |
| W7-2 | FastAPI 薄层（可选） | 接收告警 → 触发 LangGraph run |
| W7-3 | 端到端演示脚本 | 告警 → 诊断 → 沙箱 → 报告 |
| W7-4 | Phase 2 MVP 评审 | 对照第一版方案「查判试记」清单 |

---

### W8+ — P4：扩展（按需）

| 方向 | 内容 |
|------|------|
| 多集群 live | `configs/clusters.yaml`、每集群 MCP、``sync_clusters_resilient`` live |
| Live execute | Action MCP、`SENTINEL_EXECUTE_LIVE=1`、审批流 |
| 观测扩展 | Loki 日志 MCP、Node live sync、Deployment 拓扑 |
| 稳定化 | k3s stable 版、langgraph 持久化、监控 sync/langgraph 健康 |

---

## 6. 风险与依赖

| 风险 | 缓解 |
|------|------|
| `langgraph dev` 内存 checkpoint，重启丢图 | cron sync 重建；后续评估持久化方案 |
| 服务器无法访问 GitHub | 本机 scp / 离线包；deploy 文档写清 |
| MCP 容器内 kubeconfig 127.0.0.1 | 统一宿主机 IP 或 `host.docker.internal` |
| k3s RC 版 + 历史无 systemd | `systemctl enable k3s`；考虑 stable 替换 |
| 评估报告 / README 与代码脱节 | W4 同步更新 |

---

## 7. 每周总结规范

- **路径**：`docs/weekly/YYYY-Www.md`（ISO 周，如 `2026-W22.md`）
- **模板**：[`docs/weekly/TEMPLATE.md`](weekly/TEMPLATE.md)
- **必写**：本周完成、未完成、阻塞、指标（sync 次数、pod 数、单测数）、下周 Wn 勾选

### 周总结索引

| 周次 | 文件 | 主题 | 状态 |
|------|------|------|------|
| W1 | [2026-W22.md](weekly/2026-W22.md) | Phase 1b live sync 首通 + 运维 | 进行中 |
| W2 | — | Live inspect E2E | 待开始 |
| W3 | — | Prometheus 进图 | 待开始 |
| W4 | — | UI + 部署文档 | 待开始 |
| W5 | — | Skills | 待开始 |
| W6 | — | 沙箱 | 待开始 |
| W7 | — | 告警 + 半自动闭环 | 待开始 |

---

## 8. 关键命令速查（服务器）

```bash
# 环境
source /opt/sentinel-x/.venv/bin/activate
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
export LANGGRAPH_API_URL=http://127.0.0.1:2024

# Sync
export MCP_CONTAINER=mcp-servers_mcp-k8s_1
export CLUSTER_ID=k3s-prod
export NAMESPACE=kube-system
python /opt/sentinel-x/agents/langgraph-integration/scripts/mcp_k8s_sync_live.py

# Query（替换 thread_id）
export LANGGRAPH_THREAD_ID=5ad00ee0-6f4d-5cd6-a021-99469a86e4e1
python /opt/sentinel-x/agents/langgraph-integration/scripts/query_demo.py --live

# Inspect
export LANGGRAPH_RUN_LIVE=1
python /opt/sentinel-x/agents/langgraph-integration/scripts/inspect_langgraph_live_demo.py --live --pod-name <name>
```

---

## 9. 相关文档

| 文档 | 位置 |
|------|------|
| 仓库 README | [`README.md`](../README.md) |
| LangGraph 集成 README | [`agents/langgraph-integration/README.md`](../agents/langgraph-integration/README.md) |
| Phase 1b 操作指南 | 桌面 `sentinel-x-k8s-mcp-phase1b-guide.md` |
| 桌面 Phase 系列 | `Desktop/Sentinel-X/` |
