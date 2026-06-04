# W3：Prometheus 指标进图（Phase 1c）

> 公共参数与验证见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md)  
> 目标：从 Prometheus MCP 拉取 Pod **CPU / 内存** 指标，** enrichment** 写入 LangGraph 图内 Pod 属性；查询可回答「哪个 Pod CPU 最高」。  
> 依赖：**W1** LangGraph systemd + K8s cron sync 已跑通；**集群内 Prometheus 已安装**且 MCP 容器可达（见 [DEPLOY-PROMETHEUS-K3S.md](DEPLOY-PROMETHEUS-K3S.md)）。

---

## 架构

```text
cron (optional, after k8s sync)
  → deploy/sync-prom.sh
  → mcp_prom_sync_live.py
  → docker exec → mcp-prometheus → PromQL → Prometheus (NodePort :30909)
  → docker exec → mcp-k8s → Pod 列表（与 K8s sync 同源）
  → adapter/metrics: pods + cpu_cores / memory_bytes
  → sync_pod_metrics_resilient → langgraph :2024（同一 cluster thread）
  → 查询: top_pods_by_cpu / pod_metrics
```

**与 K8s sync 关系**：Prom sync **不替代** K8s sync；它用 K8s MCP 拿 Pod 名单，用 Prom 拿指标，合并后推送 **Pod entity 更新**（增量指纹含 `cpu_cores` / `memory_bytes`）。

LangGraph 重启后图清空时，先靠 **W1-3 K8s cron** 重建 Pod/Event，再跑 Prom sync 补指标。

---

## 前置条件

| 项 | 检查命令 |
|----|----------|
| W1 LangGraph | `sudo systemctl is-active sentinel-langgraph` |
| W1 K8s MCP | `docker ps --filter name=mcp-k8s` |
| K8s sync 曾成功 | 见 [DEPLOY-SYNC-CRON.md](DEPLOY-SYNC-CRON.md) |
| **Prometheus 已部署** | 见 **[DEPLOY-PROMETHEUS-K3S.md](DEPLOY-PROMETHEUS-K3S.md)**（离线 helm pull / helm-charts zip） |
| Prometheus 宿主机 | `curl -sf http://127.0.0.1:30909/-/ready`（kube-prometheus NodePort；若用 9090 则改端口） |
| cAdvisor / container 指标 | `curl 'http://127.0.0.1:30909/api/v1/query?query=container_cpu_usage_seconds_total'` 有 series |
| MCP `PROMETHEUS_BASE_URL` | `docker exec … printenv` 应为 `http://host.docker.internal:30909`，**不是** `localhost:9090` |

---

## Step 0：启动 mcp-prometheus 容器

在仓库 `mcp-servers/` 目录（与 k8s MCP 相同 compose）：

```bash
cd /opt/sentinel-x/mcp-servers

# 若尚未 build
docker-compose build mcp-prometheus

# 启动（与 mcp-k8s 并列）
docker-compose up -d mcp-prometheus

docker ps --format '{{.Names}}' | grep prometheus
# 例: mcp-servers_mcp-prometheus_1
```

compose 默认（可被 `mcp-servers/.env` 覆盖；kube-prometheus 离线安装后应为 **30909**）：

```yaml
PROMETHEUS_BASE_URL: http://host.docker.internal:30909
```

若尚未部署 Prometheus，先完成 [DEPLOY-PROMETHEUS-K3S.md](DEPLOY-PROMETHEUS-K3S.md)。

**容器内验证 Prometheus 可达**：

```bash
PROM=mcp-servers_mcp-prometheus_1   # 换成 docker ps 名字

docker exec -i "$PROM" bash -lc 'cd /app/src && python - <<PY
import json
from tools.prom_query import prom_query
q = "sum(rate(container_cpu_usage_seconds_total{container!=\"\",pod!=\"\"}[5m])) by (pod, namespace)"
print(json.dumps(prom_query(q), indent=2)[:800])
PY'
```

期望：`result_type: vector`，`results` 非空（有 Pod 在跑且 metrics-server/cAdvisor 有数据）。

若 `results: []`：检查 Prometheus 是否 scrape 到 k3s 节点 cAdvisor；或调整 PromQL（见文末）。

---

## Step 1：本机 / 服务器手工 sync

```bash
source /etc/sentinel/sync-prom.env 2>/dev/null || true
# 或: sudo bash deploy/sentinel-config-apply.sh --with-prom-sync

sudo /usr/local/bin/sentinel-sync-prom.sh
# 或:
# python /opt/sentinel-x/agents/langgraph-integration/scripts/mcp_prom_sync_live.py
```

期望输出：

```text
k8s_source=docker:mcp-servers_mcp-k8s_1
prom_source=docker:mcp-servers_mcp-prometheus_1
mcp pods=7 prom_cpu_series=... prom_mem_series=...
sync ok: chunks=... entities=... skipped=...
Query with: LANGGRAPH_THREAD_ID=...
  top_pods_by_cpu / pod_metrics
```

**说明**：`prom_cpu_series` 可能大于 `pods`（Prom 按 label 返回多 series）；adapter 只 enrichment **当前 namespace 且 K8s 列出的 Pod**。

---

## Step 2：查询验收

先确保 K8s sync + Prom sync 都跑过，再：

```bash
sudo bash /opt/sentinel-x/deploy/verify-sentinel-x.sh
# top_pods_by_cpu / pod_metrics — 见 agents/langgraph-integration/scripts/query_demo.py --live
```

**W3 完成标准**：`top_pods_by_cpu` 返回带 `cpu_cores` 的 Pod 列表，且第一名与 Prom UI 趋势一致（不必精确到小数点后多位）。

### 2b 仅 Prom MCP 验证（不进图）

```bash
docker exec -i mcp-servers_mcp-prometheus_1 bash -lc 'cd /app/src && python - <<PY
from tools.prom_query import prom_query
for label, q in [
    ("cpu", "sum(rate(container_cpu_usage_seconds_total{container!=\"\",pod!=\"\"}[5m])) by (pod, namespace)"),
    ("mem", "sum(container_memory_working_set_bytes{container!=\"\",pod!=\"\"}) by (pod, namespace)"),
]:
    r = prom_query(q)
    print(label, "series=", len(r.get("results") or []))
PY'
```

---

## Step 3：安装 cron wrapper（可选）

Prom 指标变化比 Pod spec 快，可与 K8s sync **错开**或 **串在同一 cron**（先 K8s 再 Prom）。

```bash
sudo mkdir -p /etc/sentinel /var/log

sudo install -m 755 /opt/sentinel-x/deploy/sync-prom.sh /usr/local/bin/sentinel-sync-prom.sh
sudo install -m 600 /opt/sentinel-x/deploy/sync-prom.env.example /etc/sentinel/sync-prom.env

# Windows scp 上传后必做
sudo sed -i 's/\r$//' /usr/local/bin/sentinel-sync-prom.sh /etc/sentinel/sync-prom.env

sudo nano /etc/sentinel/sync-prom.env
```

**必改**：

```bash
MCP_K8S_CONTAINER=mcp-servers_mcp-k8s_1
MCP_PROM_CONTAINER=mcp-servers_mcp-prometheus_1
CLUSTER_ID=k3s-prod
NAMESPACE=kube-system
```

手工试跑：

```bash
sudo /usr/local/bin/sentinel-sync-prom.sh
tail -30 /var/log/sentinel-prom-sync.log
```

Crontab 示例（K8s sync 后 2 分钟跑 Prom，每 5 分钟一轮）：

```cron
*/5 * * * * /usr/local/bin/sentinel-sync-k8s.sh >/dev/null 2>&1
2-59/5 * * * * /usr/local/bin/sentinel-sync-prom.sh >/dev/null 2>&1
```

---

## Step 4：离线 snapshot（无 docker exec 调试）

```bash
# 在 prom 容器内导出
docker exec -i mcp-servers_mcp-prometheus_1 bash -lc 'cd /app/src && python - <<PY
import json, os
from tools.prom_query import prom_query
cpu = os.environ.get("SENTINEL_PROM_CPU_PROMQL") or "sum(rate(container_cpu_usage_seconds_total{container!=\"\",pod!=\"\"}[5m])) by (pod, namespace)"
mem = os.environ.get("SENTINEL_PROM_MEMORY_PROMQL") or "sum(container_memory_working_set_bytes{container!=\"\",pod!=\"\"}) by (pod, namespace)"
print(json.dumps({"cpu": prom_query(cpu), "memory": prom_query(mem)}))
PY' | sudo tee /var/lib/sentinel/prom_mcp_snapshot.json >/dev/null

python scripts/mcp_prom_sync_live.py \
  --snapshot /var/lib/sentinel/prom_mcp_snapshot.json \
  --k8s-snapshot /var/lib/sentinel/k8s_mcp_snapshot.json \
  --cluster-id k3s-prod --namespace kube-system
```

---

## 故障排查

| 现象 | 处理 |
|------|------|
| `docker exec Prom MCP fetch failed` | 容器名错；或 `bash\r` CRLF — 仓库脚本已 LF；`sed -i 's/\r$//'` |
| `PrometheusConnectionError` / refused | 未装 Prometheus 或 URL 错；见 [DEPLOY-PROMETHEUS-K3S.md](DEPLOY-PROMETHEUS-K3S.md)；容器内 `curl host.docker.internal:30909/-/ready` |
| `0 cpu and 0 memory series` | Prom 可达但无 container 指标；等 scrape 或查 node-exporter |
| sync ok 但 query 无 `cpu_cores` | 未跑 Prom sync；或 Pod 名/namespace 与 Prom label 不匹配 |
| `MCP returned 0 pods` | 先跑 K8s sync；检查 `NAMESPACE` |
| 增量 `skipped` 全满但指标旧 | 删 partition state 或 `LANGGRAPH_SYNC_INCREMENTAL=0` 跑一次 |

**CRLF**：与 [DEPLOY-SYNC-CRON.md](DEPLOY-SYNC-CRON.md) 相同，scp 后 `sed -i 's/\r$//'`。

**stdin docker exec**：`mcp_prom.py` 使用 `docker exec -i ... python -` + heredoc script，避免服务器 `-lc 'python -c ...'` 引号/CRLF 问题（对齐 `mcp_k8s.py`）。

---

## 默认 PromQL

| 指标 | PromQL |
|------|--------|
| CPU（核） | `sum(rate(container_cpu_usage_seconds_total{container!="",pod!=""}[5m])) by (pod, namespace)` |
| 内存（字节） | `sum(container_memory_working_set_bytes{container!="",pod!=""}) by (pod, namespace)` |

环境变量覆盖：`SENTINEL_PROM_CPU_PROMQL`、`SENTINEL_PROM_MEMORY_PROMQL`（写入 `sync-prom.env` 或 export）。

k3s 若 metric 名不同，在 Prometheus UI **Graph** 页搜索 `container_cpu` / `container_memory` 后改 PromQL。

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [DEPLOY-PROMETHEUS-K3S.md](DEPLOY-PROMETHEUS-K3S.md) | **前置**：离线安装 kube-prometheus-stack |
| [ROADMAP.md](ROADMAP.md) | W3 Phase 1c 总纲 |
| [DEPLOY-SYNC-CRON.md](DEPLOY-SYNC-CRON.md) | W1 K8s 增量 sync |
| [DEPLOY-MCP-KUBECONFIG.md](DEPLOY-MCP-KUBECONFIG.md) | MCP kubeconfig |
| `agents/langgraph-integration/src/clients/mcp_prom.py` | docker fetch |
| `agents/langgraph-integration/scripts/mcp_prom_sync_live.py` | 入口脚本 |
