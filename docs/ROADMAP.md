# Sentinel-X 项目总纲

> 本文档为 **主路线图**：概括当前进度、按优先级排列的后续周计划，以及每周总结的索引。  
> 每周结束后在 [`docs/weekly/`](weekly/) 新增一份周总结，并回链到本文档对应周次。

**最后更新**：2026-06-17  
**当前阶段**：P0 一键部署 **W1–W7 live ✅**；**W7 自动 patrol live ✅**（[`2026-W26.md`](weekly/2026-W26.md)）

### 对外文档索引（Portfolio / 简历向）

| 文档 | 说明 |
|------|------|
| [Architecture](architecture/README.md) | 三张公开架构图（overview / alert-loop / sandbox） |
| [ADR](adr/README.md) | 架构决策记录 ADR-001~004 |
| [Dev Log](dev-log/README.md) | 轻量开发日志（vs 下方 weekly 详细周报） |
| [CHANGELOG](../CHANGELOG.md) | 版本变更 v0.1–v0.4 |
| [GitHub import](.github-import/README.md) | Project / Release 导入指南（中英双语） |

---

## 1. 项目目标（MVP 一句话）

让 Agent **看见**云原生系统（Pod / Event / 指标），**判断**故障类型，**试**在沙箱预演修复，**记**沉淀 Skills——形成「查 / 判 / 试 / 记」闭环。

---

## 2. 阶段对照表

| 阶段 | 文档来源 | 目标 | 整体进度 |
|------|----------|------|----------|
| Phase 0 | README | 目录、Skill 模板、工程底座 | 80% |
| Phase 1 | 桌面「看见系统」 | MCP + Agent 可查询 Pod/指标 | **90%** |
| Phase 1b | 桌面 phase1b guide | K8s MCP → LangGraph live sync | **验收完成** |
| Phase 1c | W3 Prometheus 进图 | Prom MCP → Pod 指标 enrichment | **live 验收完成** |
| Phase 3 | LangGraph 集成（第三版） | Adapter / Sync / Query 数据面 | 代码 90%，live 75% |
| Phase 4 | 多集群（第四版） | cluster_id / tenant 隔离 | mock 100%，live 0% |
| Phase 5 | Diagnosis / 动作层 | gather → diagnose → execute → sandbox | 代码 75%，live **~55%** |
| MVP 2–5 | 第一版开发方案 | 沙箱 / Skills / Streamlit UI | UI **live**；Skills **live**；沙箱 **W6 live ✅** |

---

## 3. 当前进度概况（截至 2026-06-02）

### 3.1 已完成

| 模块 | 内容 | 位置 / 证据 |
|------|------|-------------|
| K8s MCP | `k8s_get_pods` / `k8s_get_events`，FastMCP stdio | `mcp-servers/k8s/` |
| Prometheus MCP | `prom_query` / `prom_query_range` | `mcp-servers/prometheus/` |
| 图模型与 Adapter | Pod / Event / Node / Inspection；Pod 指标 enrichment | `agents/langgraph-integration/src/models/`、`adapter/metrics.py` |
| Sync 管道 | 增量、重试、分块；`sync_pod_metrics_resilient` | `src/sync/` |
| **Prom → 图** | `mcp_prom.py` + `mcp_prom_sync_live.py`；Pod `cpu_cores` / `memory_bytes` | `src/clients/mcp_prom.py`，[DEPLOY-PROM-SYNC.md](deploy/DEPLOY-PROM-SYNC.md) |
| Query | `list_pods`、`pod_status`、`events_for_pod`、`top_pods_by_cpu`、`pod_metrics` 等 | `src/query/` |
| LangGraph 图 | ingest → gather → diagnose → retrieve → narrate → execute → sandbox → verify → record → query | `agents/langgraph-server/src/graph.py` |
| Agent | 规则诊断、模板/LLM 叙事、动作注册表（模拟） | `src/agent/` |
| 单测 | ~180+ 用例 | `agents/langgraph-integration/tests/` |
| **服务器 live** | k3s 离线恢复；MCP kubeconfig 宿主机 IP；sync 成功 | 7 pods / 65 events → 66 entities |
| **Prom live** | kube-prometheus NodePort 30909；Prom sync + `top_pods_by_cpu` | entities=7；metrics-server 最高 CPU |
| **UI live** | Streamlit `:8501`；SSH 隧道；Pods 表含 cpu/memory | 8 pods kube-system；[DEPLOY-UI-LIVE.md](deploy/DEPLOY-UI-LIVE.md) |
| **P0 one-shot live** | 全栈 install + `verify --full` | `sentinel-x` 2026-06-17；[DEPLOY-ONE-SHOT.md](deploy/DEPLOY-ONE-SHOT.md)、[2026-W25.md](weekly/2026-W25.md) |
| **W7 inspect trigger live** | `trigger_inspect` → `issues=['CrashLoop']` | 手动 `--pod` 路径；thread `5ad00ee0-…` |
| **W7 auto patrol live** | MCP `normalize` + patrol 补丁；`crash-demo` auto inspect + cooldown | [`2026-W26.md`](weekly/2026-W26.md)；[`DEPLOY-ALERT-INSPECT.md`](deploy/DEPLOY-ALERT-INSPECT.md) |

**Live sync 关键参数**：见 [DEPLOY-REFERENCE.md](deploy/DEPLOY-REFERENCE.md)（`CLUSTER_ID`、`LANGGRAPH_THREAD_ID` 由 config apply 生成）。

### 3.2 进行中 / 未验收

- W2-4 可选 LLM（DashScope timeout）
- W3 可选 Prom cron（`sentinel-sync-prom.sh`）

### 3.3 未开始（按 MVP 愿景）

- Chroma / embedding Skills 后端
- gVisor 沙箱（W6 用 Docker + namespace 策略）
- Live K8s 写操作（`SENTINEL_EXECUTE_LIVE=1`，W8+）
- 多集群 live（`configs/clusters.yaml`）

### 3.4 架构现状

```text
[k3s API] ← kubeconfig ← [MCP-K8s] ← docker exec ← [mcp_k8s_sync_live]
         ← kube-system + sentinel-sandbox cron sync
                                                          ↓
[Prometheus :30909] ← host.docker.internal ← [MCP-Prom] ← docker exec ← [mcp_prom_sync_live]
                                                          ↓
                                              [langgraph dev :2024]
                                                          ↓
                                    [query / inspect / top_pods_by_cpu / pod_metrics]
                       │                    ↑
              [Streamlit UI :8501]  ← SSH tunnel (W4 live ✅)
              [sentinel-inspect-patrol.sh] ── cron patrol (W7 live ✅)
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
| W1-2 | langgraph systemd | 重启后服务自启；文档记录端口与 `.env` 要求 → **[DEPLOY-LANGGRAPH-SYSTEMD.md](deploy/DEPLOY-LANGGRAPH-SYSTEMD.md)** |
| W1-3 | cron 增量 sync | 每 5min `mcp_k8s_sync_live.py`；日志 `/var/log/sentinel-sync.log` → **[DEPLOY-SYNC-CRON.md](deploy/DEPLOY-SYNC-CRON.md)** |
| W1-4 | MCP kubeconfig 固化 | `~/.kube/config` 宿主机 IP 或 `host.docker.internal`；compose `extra_hosts` → **[DEPLOY-MCP-KUBECONFIG.md](deploy/DEPLOY-MCP-KUBECONFIG.md)** |
| W1-5 | deploy 入库 | `deploy/sentinel-langgraph.service`、`deploy/sync-k8s.sh` ✅ |
| W1-6 | 代码对齐 | 服务器 `mcp_k8s.py` 与仓库 stdin 版一致 |

**W1 完成标准**：cron 跑满 24h 无报错；query 与 kubectl pod 数一致。

---

### W2 — P0：Live Inspect + 诊断 E2E

**目标**：对齐第五版「Diagnosis Engine」，对 **真实集群 Pod** 跑通 inspect 链。

| 序号 | 任务 | 产出 / 验收 |
|------|------|-------------|
| W2-1 | 选目标 Pod | kube-system 系统 Pod 或自建 crash 测试 Pod |
| W2-2 | inspect live | `LANGGRAPH_RUN_LIVE=1` + `inspect_langgraph_live_demo.py --thread-only` → gather/diagnosis/narrative → **[DEPLOY-INSPECT-LIVE.md](deploy/DEPLOY-INSPECT-LIVE.md)** |
| W2-3 | execution dry-run | `execution` 含模拟 `restart_pod` 等，无 live 写（Path B CrashLoop） |
| W2-4 | 可选 LLM | DashScope + `--llm`；`narrative_source=llm` |
| W2-5 | 文档 | 本文 + ROADMAP §3 + 周总结 W2 |

**W2 完成标准**：stream 中四类输出齐全；diagnosis.issues 对 crash Pod 非空（若用测试 Pod）。

---

### W3 — P1：Prometheus 进图（Phase 1c）— **已完成**

**目标**：补桌面 Phase 1「CPU/内存」查询能力。

**部署文档** → **[DEPLOY-PROM-SYNC.md](deploy/DEPLOY-PROM-SYNC.md)**（前置 Prometheus → **[DEPLOY-PROMETHEUS-K3S.md](deploy/DEPLOY-PROMETHEUS-K3S.md)**）

| 序号 | 任务 | 产出 / 验收 | 状态 |
|------|------|-------------|------|
| W3-0 | k3s 内 Prometheus | 离线 helm pull / helm-charts zip → NodePort 30909 | ✅ live |
| W3-1 | `clients/mcp_prom.py` | docker exec stdin 或 snapshot 拉 Prom JSON | ✅ 代码 |
| W3-2 | `scripts/live/mcp_prom_sync_live.py` | K8s pods + Prom → `sync_pod_metrics_resilient` | ✅ 代码 |
| W3-3 | Adapter 扩展 | `adapter/metrics.py`；Pod `cpu_cores` / `memory_bytes` | ✅ 代码 |
| W3-4 | Query op | `top_pods_by_cpu`、`pod_metrics`；`list_pods` 含指标字段 | ✅ 代码 |
| W3-5 | 单测 + 服务器验收 | `test_mcp_prom_fetch.py`；live Prom 可达 + query | ✅ live |
| W3-6 | 运维 | `deploy/sync-prom.sh` + env；可选 cron | ✅ 模板 |

**服务器工作流（摘要）**：

1. **前置**：W1 LangGraph + K8s cron 正常；按 [DEPLOY-PROMETHEUS-K3S.md](deploy/DEPLOY-PROMETHEUS-K3S.md) 安装 Prometheus（NodePort **30909**）；`mcp-servers/compose/.env` 中 `PROMETHEUS_BASE_URL=http://host.docker.internal:30909`。  
2. **MCP**：`docker-compose up -d mcp-prometheus`；容器内 `prom_query` 有 vector 结果。  
3. **手工 sync**：`MCP_K8S_CONTAINER` + `MCP_PROM_CONTAINER` → `mcp_prom_sync_live.py`。  
4. **查询**：`top_pods_by_cpu` 返回带 `cpu_cores` 的 Pod 排序列表。  
5. **可选 cron**：`sentinel-sync-prom.sh`（建议在 K8s sync 之后）。

**W3 完成标准**：sync 后能回答「哪个 Pod CPU 使用最高」（Phase 1 原文验收项）。**已于 2026-06-04 live 验收通过**（`sync ok: entities=7`；`top_pods_by_cpu` 返回 `cpu_cores`）。

**默认 PromQL**（cAdvisor / container 指标）：

```promql
sum(rate(container_cpu_usage_seconds_total{container!="",pod!=""}[5m])) by (pod, namespace)
sum(container_memory_working_set_bytes{container!="",pod!=""}) by (pod, namespace)
```

---

### W4 — P2：最小演示面 + 工程文档 — **已完成**

**目标**：非 CLI 也能看结果；换机可复现部署。

**部署总览** → **[DEPLOY-SERVER.md](deploy/DEPLOY-SERVER.md)** · **UI 服务器步骤** → **[DEPLOY-UI-LIVE.md](deploy/DEPLOY-UI-LIVE.md)**

| 序号 | 任务 | 产出 / 验收 | 状态 |
|------|------|-------------|------|
| W4-1 | Streamlit 最小页 | list_pods + inspect 结果展示 | ✅ live |
| W4-2 | 部署指南 | `docs/deploy/DEPLOY-SERVER.md` + `DEPLOY-UI-LIVE.md` | ✅ |
| W4-3 | README 同步 | 根 README 与实现差距标注 | ✅ |
| W4-4 | langgraph-server smoke 测试 | 至少 1 个 graph 节点单测 | ✅ |

**W4 完成标准**：浏览器打开 UI 可见 live pod 列表；新人按 DEPLOY 文档可复现 W1。**已于 2026-06-04 live 验收通过**（SSH 隧道 `:8501`；8 pods；`cpu_cores`/`memory` 列可见）。

---

### W5 — P3：Skills 基础（「记」）

**目标**：诊断结果可沉淀、可检索。

| 序号 | 任务 | 产出 / 验收 |
|------|------|-------------|
| W5-1 | `skills/` 目录与模板 | ✅ Skill/Evidence 分离；[`skills/TEMPLATE.md`](../skills/TEMPLATE.md) |
| W5-2 | skill_writer + `record_skill` | ✅ `src/skills/writer.py`；execute → verify → record 节点 |
| W5-3 | 检索 | ✅ SQLite FTS5 + `ISSUE_SYNONYMS`；`SkillStore` Protocol |
| W5-4 | Agent 接入 | ✅ `retrieve_skills` → narrative `Similar past skills` |

**W5 完成标准**：同一 CrashLoop 场景第二次可命中历史 Skill 摘要。**单元测试已覆盖**（`test_skills_retrieve_integration.py`）。

---

### W6 — P3：沙箱预演（「试」）— **代码 + live 已完成**

**目标**：修复命令不进生产，先进受限容器。

| 序号 | 任务 | 产出 / 验收 | 状态 |
|------|------|-------------|------|
| W6-1 | `sandbox/` 模块 | Docker 受限执行 kubectl 子集 | ✅ code + **live** |
| W6-2 | planner + verifier | `src/sandbox/` + `sandbox_run` 图节点 | ✅ code + **live** |
| W6-3 | 审计日志 | `sandbox/audit/*.jsonl` | ✅ code + **live** |
| W6-4 | 与 execute 衔接 | `dry_run=false` → 沙箱；生产 ns block | ✅ code + **live** |

**W6 完成标准**：restart/scale 在 `sentinel-sandbox` 跑通并出审计；`verify_skill` → `verified: true`。**已于 2026-06-09 live 验收**（[`2026-W23.md §7`](weekly/2026-W23.md)）；见 [`sandbox/README.md`](../sandbox/README.md)。

---

### W7 — P3：告警入口 + 半自动闭环 — **live ✅**

**目标**：从「人工 query」到「事件驱动一次诊断」。

**部署文档** → **[DEPLOY-ALERT-INSPECT.md](deploy/DEPLOY-ALERT-INSPECT.md)** · live 证据 → **[2026-W25.md §7](weekly/2026-W25.md)**、**[2026-W26.md](weekly/2026-W26.md)**

| 序号 | 任务 | 产出 / 验收 | 状态 |
|------|------|-------------|------|
| W7-1 | cron 巡检 → inspect | `src/trigger/` + `sentinel-inspect-patrol.sh` | ✅ live（手动 + **auto patrol**；[`2026-W26.md`](weekly/2026-W26.md)） |
| W7-2 | FastAPI 薄层（可选） | `POST /v1/inspect` + Alertmanager webhook | ✅ `/health` live；POST inspect / webhook **W8+** |
| W7-3 | E2E demo | `alert_to_inspect_demo.py` | ✅ 代码 |
| W7-4 | Phase 2 MVP 评审 | DEPLOY-ALERT-INSPECT §验收清单 | ✅ **核心 4 项**（Alertmanager webhook 仍 W8+） |

**W7 完成标准**：CrashLoop Pod 触发 inspect（默认 dry_run）。**已于 2026-06-17 live 验收**（手动 + auto `crash-demo` → `issues=['CrashLoop']`；cooldown — [`2026-W26.md`](weekly/2026-W26.md)）。

---

### W8+ — P4：扩展（按需）

| 方向 | 内容 |
|------|------|
| **Checkpoint Phase 2** | W5 Skills + W6 沙箱 live 验收后：评估 LangGraph Postgres checkpointer（官方）vs 单机 SQLite；spike `langgraph dev` → `langgraph up` + 持久化 store 对 `stream_sentinel_run` / `thread_id` 的影响 |
| 多集群 live | `configs/clusters.yaml`、每集群 MCP、``sync_clusters_resilient`` live |
| Live execute | Action MCP、`SENTINEL_EXECUTE_LIVE=1`、审批流 |
| 观测扩展 | Loki 日志 MCP、Node live sync、Deployment 拓扑 |
| 稳定化 | k3s stable 版、langgraph 持久化、监控 sync/langgraph 健康 |

---

## 6. 风险与依赖

| 风险 | 缓解 |
|------|------|
| `langgraph dev` 内存 checkpoint，重启丢图 | post-restart hook + cron sync；Phase 2 持久化见 W8+ |
| 服务器无法访问 GitHub | 本机 scp / 离线包；deploy 文档写清 |
| MCP 容器内 kubeconfig 127.0.0.1 | 统一宿主机 IP 或 `host.docker.internal` |
| MCP Pod status 仅 `phase` | CrashLoop 在图中为 `Running`；`normalize.py` 取 waiting reason |
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
| W1 | [2026-W22.md](weekly/2026-W22.md) | Phase 1b 验收与运维固化 | **已完成** |
| W2 | [2026-W22.md](weekly/2026-W22.md) | Live inspect E2E | **已完成** → [DEPLOY-INSPECT-LIVE.md](deploy/DEPLOY-INSPECT-LIVE.md) |
| W3 | [2026-W22.md](weekly/2026-W22.md) §6 | Prometheus 进图 | **已完成** → [DEPLOY-PROM-SYNC.md](deploy/DEPLOY-PROM-SYNC.md) |
| W4 | [2026-W22.md](weekly/2026-W22.md) §7 | UI + 部署文档 | **已完成** → [DEPLOY-UI-LIVE.md](deploy/DEPLOY-UI-LIVE.md) |
| W5 | [2026-W23.md](weekly/2026-W23.md) §7 | Skills | **live 已完成** → [`skills/README.md`](../skills/README.md) |
| W6 | [2026-W23.md](weekly/2026-W23.md) §7 | 沙箱预演 | **live 已完成** → [`sandbox/README.md`](../sandbox/README.md) |
| W7 | [2026-W25.md](weekly/2026-W25.md)、[2026-W26.md](weekly/2026-W26.md) | 告警 + 半自动闭环 | **live ✅** → [DEPLOY-ALERT-INSPECT.md](deploy/DEPLOY-ALERT-INSPECT.md) |
| W26 | [2026-W26.md](weekly/2026-W26.md) | MCP normalize + auto patrol | **live ✅** |
| P0 | [2026-W25.md](weekly/2026-W25.md) | 一键部署 W1–W7 全栈 | **live ✅** → [DEPLOY-ONE-SHOT.md](deploy/DEPLOY-ONE-SHOT.md) |

---

## 8. 关键命令速查（服务器）

```bash
# 环境
source /opt/sentinel-x/.venv/bin/activate
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# 刷新全部 env（容器重建 / Prom 安装后）
sudo bash /opt/sentinel-x/deploy/config/sentinel-config-discover.sh --write
sudo bash /opt/sentinel-x/deploy/config/sentinel-config-apply.sh --reload

# Sync
sudo /usr/local/bin/sentinel-sync-k8s.sh
sudo /usr/local/bin/sentinel-sync-prom.sh   # W3

# 验证
sudo bash /opt/sentinel-x/deploy/verify/verify-sentinel-x.sh

# Inspect（source sync-k8s.env 获取 LANGGRAPH_THREAD_ID）
set -a && source /etc/sentinel/sync-k8s.env && set +a
export LANGGRAPH_RUN_LIVE=1
python /opt/sentinel-x/agents/langgraph-integration/scripts/demo/inspect_langgraph_live_demo.py \
  --thread-only --cluster-id "$CLUSTER_ID" --namespace "$NAMESPACE" \
  --pod-name <name> --thread-id "$LANGGRAPH_THREAD_ID"

# W7 patrol（需 CrashLoop 等不健康 Pod 在图中）
sudo /usr/local/bin/sentinel-inspect-patrol.sh
tail -20 /var/log/sentinel-patrol.log
```

---

## 9. 相关文档

| 文档 | 位置 |
|------|------|
| **部署参考（canonical）** | [`docs/deploy/DEPLOY-REFERENCE.md`](deploy/DEPLOY-REFERENCE.md) |
| W4 服务器部署总览 | [`docs/deploy/DEPLOY-SERVER.md`](deploy/DEPLOY-SERVER.md) |
| W4 Streamlit live | [`docs/deploy/DEPLOY-UI-LIVE.md`](deploy/DEPLOY-UI-LIVE.md) |
| W2 Live inspect E2E | [`docs/deploy/DEPLOY-INSPECT-LIVE.md`](deploy/DEPLOY-INSPECT-LIVE.md) |
| W7 Alert patrol + API | [`docs/deploy/DEPLOY-ALERT-INSPECT.md`](deploy/DEPLOY-ALERT-INSPECT.md) |
| W3 Prom metrics sync | [`docs/deploy/DEPLOY-PROM-SYNC.md`](deploy/DEPLOY-PROM-SYNC.md) |
| W3 Prometheus 离线安装 | [`docs/deploy/DEPLOY-PROMETHEUS-K3S.md`](deploy/DEPLOY-PROMETHEUS-K3S.md) |
| 仓库 README | [`README.md`](../README.md) |
| LangGraph 集成 README | [`agents/langgraph-integration/README.md`](../agents/langgraph-integration/README.md) |
| Phase 1b 操作指南 | 桌面 `sentinel-x-k8s-mcp-phase1b-guide.md` |
| 桌面 Phase 系列 | `Desktop/Sentinel-X/` |
