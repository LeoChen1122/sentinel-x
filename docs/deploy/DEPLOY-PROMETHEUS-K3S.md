# W3 前置：k3s 离线安装 Prometheus（kube-prometheus-stack）

> 目标：在 **无法访问 GitHub** 的 `sentinel-x` 服务器上，通过本机下载 Helm Chart 包上传，安装集群内 Prometheus，并暴露 **NodePort 30909** 供 MCP 容器查询。  
> 完成后继续 [DEPLOY-PROM-SYNC.md](DEPLOY-PROM-SYNC.md) 的 W3 metrics sync。

---

## 架构

```text
[本机 Windows，可上网]
  helm pull 或 helm-charts-main.zip 打包
        ↓ scp
[sentinel-x 服务器 /opt/sentinel-x/dist/kube-prometheus-offline]
  helm install kube-prometheus-stack
        ↓ NodePort 30909
[宿主机 127.0.0.1:30909] ← host.docker.internal:30909 ← [mcp-prometheus MCP]
        ↓ PromQL
[mcp_prom_sync_live.py → LangGraph]
```

**说明**：`mcp-prometheus` 只是 PromQL **客户端**，不是 Prometheus 服务器。必须先有 `:9090`（或 NodePort）上的 Prometheus 实例。

---

## 前置条件

| 项 | 检查 |
|----|------|
| k3s | `kubectl get nodes` |
| Helm 3（服务器） | `helm version` — 若无，见下文「离线安装 Helm」 |
| 本机 Helm 3（打包用） | `helm version` |
| 资源 | 单节点建议 ≥ 2Gi 可分配内存给 monitoring |

---

## 方式 A（推荐）：本机 `helm pull` 打离线包

本机有网即可，**不必**下载整个 `helm-charts-main.zip`（`helm pull` 会自动带上 chart 依赖）。

### A1. 本机 Windows（PowerShell）

```powershell
cd C:\sentinel-x\deploy\prometheus
.\prepare-kube-prometheus-offline.ps1
# 输出目录: C:\sentinel-x\dist\kube-prometheus-offline\
```

脚本会：

1. `helm repo add prometheus-community …`
2. `helm pull prometheus-community/kube-prometheus-stack --untar`
3. 复制 `deploy/kube-prometheus-values-minimal.yaml` 与 `install-kube-prometheus-offline.sh`

### A2. 上传到服务器

```powershell
scp -r C:\sentinel-x\dist\kube-prometheus-offline root@sentinel-x:/opt/sentinel-x/dist/
```

上传后去 CRLF：

```bash
find /opt/sentinel-x/dist/kube-prometheus-offline -name '*.sh' -exec sed -i 's/\r$//' {} +
```

### A3. 服务器安装

```bash
cd /opt/sentinel-x/dist/kube-prometheus-offline
sudo bash install-kube-prometheus-offline.sh
```

期望：

- `Prometheus ready at http://127.0.0.1:30909`
- 写入 `mcp-servers/compose/.env`：`PROMETHEUS_BASE_URL=http://host.docker.internal:30909`
- 重建 `mcp-prometheus` 容器

---

## 方式 B：使用 `helm-charts-main.zip`（你已下载的 monorepo）

若只有 GitHub 上的 `helm-charts-main.zip`（prometheus-community/helm-charts 整包），需在本机 **先打包成 local helm repo**，再上传（服务器上 `helm dependency update` 仍需联网，不可直接用 zip）。

### B1. 本机 PowerShell

```powershell
cd C:\sentinel-x\deploy\prometheus
.\prepare-kube-prometheus-offline.ps1 -FromZip C:\Downloads\helm-charts-main.zip
```

会生成：

```text
dist/kube-prometheus-offline/
  helm-local-repo/          # 所有 charts 的 .tgz + index.yaml
  kube-prometheus-values-minimal.yaml
  install-kube-prometheus-offline.sh
  OFFLINE.txt
```

### B2. 上传 + 安装

与方式 A 相同：

```bash
cd /opt/sentinel-x/dist/kube-prometheus-offline
sed -i 's/\r$//' install-kube-prometheus-offline.sh
sudo bash install-kube-prometheus-offline.sh
```

安装脚本检测到 `helm-local-repo/index.yaml` 时，使用 `file://` 离线 repo 安装。

---

## 离线安装 Helm 3（服务器无 GitHub）

在本机浏览器下载（示例 amd64 Linux）：

- https://get.helm.sh/helm-v3.16.3-linux-amd64.tar.gz

上传并安装：

```bash
tar xzf helm-v3.16.3-linux-amd64.tar.gz
sudo install -m 755 linux-amd64/helm /usr/local/bin/helm
helm version
```

---

## 安装参数说明

[`deploy/kube-prometheus-values-minimal.yaml`](../deploy/kube-prometheus-values-minimal.yaml) 为单节点 k3s 精简配置：

| 项 | 值 |
|----|-----|
| Grafana | 关闭 |
| Alertmanager | 关闭 |
| Prometheus NodePort | **30909** |
| retention | 7d |

自定义：

```bash
export KUBE_PROM_NODE_PORT=30909
export KUBE_PROM_VALUES=/path/to/values.yaml
sudo -E bash install-kube-prometheus-offline.sh
```

---

## 验收

```bash
# 1. Pod
kubectl get pods -n monitoring

# 2. 宿主机 Prometheus
curl -sf http://127.0.0.1:30909/-/ready && echo OK

# 3. container 指标（W3 默认 PromQL 依赖）
curl -sf 'http://127.0.0.1:30909/api/v1/query?query=container_cpu_usage_seconds_total' | head -c 400

# 4. MCP 容器
PROM=$(docker ps --format '{{.Names}}' | grep mcp-prometheus | head -1)
docker exec -i "$PROM" printenv PROMETHEUS_BASE_URL
# 应为 http://host.docker.internal:30909（不是 localhost:9090）

docker exec -i "$PROM" curl -sf http://host.docker.internal:30909/-/ready && echo OK

# 5. prom_query
docker exec -i "$PROM" bash -lc 'cd /app/src && python - <<PY
import json
from tools.prom_query import prom_query
q = "sum(rate(container_cpu_usage_seconds_total{container!=\"\",pod!=\"\"}[5m])) by (pod, namespace)"
print(json.dumps(prom_query(q), indent=2)[:800])
PY'
```

`results` 非空 → 继续 [DEPLOY-PROM-SYNC.md](DEPLOY-PROM-SYNC.md) Step 1。

---

## 故障排查

| 现象 | 处理 |
|------|------|
| `helm: command not found` | 本机下载 helm tarball 安装（见上） |
| Pod Pending / OOM | `kubectl describe pod -n monitoring`；减小 requests 或加内存 |
| `30909` 无响应 | `kubectl get svc -n monitoring \| grep prometheus`；确认 NodePort |
| MCP `Connection refused` | `PROMETHEUS_BASE_URL` 仍是 `localhost:9090` → 改 `.env` 重建容器 |
| MCP 连不上 `host.docker.internal` | `docker-compose.yml` 需 `extra_hosts: host.docker.internal:host-gateway` |
| `container_cpu` series 为 0 | 等 2–5 分钟 scrape；`kubectl get pods -n monitoring \| grep node-exporter` |
| 升级 chart | 同目录再跑 `install-kube-prometheus-offline.sh`（检测到 release 会 `helm upgrade`） |

---

## 卸载（可选）

```bash
helm uninstall kube-prom -n monitoring
kubectl delete namespace monitoring   # 会删 CRD 相关资源，慎用
```

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [DEPLOY-PROM-SYNC.md](DEPLOY-PROM-SYNC.md) | W3 metrics → LangGraph |
| [DEPLOY-MCP-KUBECONFIG.md](DEPLOY-MCP-KUBECONFIG.md) | MCP 网络 / kubeconfig |
| [ROADMAP.md](ROADMAP.md) | W3 里程碑 |
