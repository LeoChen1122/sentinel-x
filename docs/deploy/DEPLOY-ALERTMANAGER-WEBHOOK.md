# W8：Alertmanager webhook → Sentinel-X inspect

> 公共参数见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md)  
> 目标：Prometheus / Alertmanager 告警（或手工 JSON）经 **`POST /v1/webhooks/alertmanager`** 触发与 patrol 相同的 `trigger_inspect` 链。  
> 前置：[DEPLOY-ALERT-INSPECT.md](DEPLOY-ALERT-INSPECT.md)（W7 patrol + API）、`sentinel-api` active。

---

## 架构

```text
[PrometheusRule SentinelPodCrashLoop]  (可选)
        ↓ firing
[Alertmanager receiver sentinel-x]     (可选)
        ↓ POST JSON
[POST /v1/webhooks/alertmanager]  ──► trigger_inspect ──► LangGraph graph
        ↑
[手工 curl 样本]  ────────────────────┘   (主验收，不依赖 Prom)
```

**实现**：[`apps/api/src/routes/webhooks.py`](../../apps/api/src/routes/webhooks.py) — 解析 `alerts[].labels.pod`（及可选 `namespace`），默认 `dry_run` 与 patrol 一致（`SENTINEL_PATROL_DRY_RUN`）。

**部署资产**（repo 内）：

| 文件 | 作用 |
|------|------|
| [`deploy/prometheus/sentinel-alertmanager-receiver.example.yaml`](../../deploy/prometheus/sentinel-alertmanager-receiver.example.yaml) | Helm values：启用 Alertmanager + `sentinel-x` webhook receiver |
| [`deploy/prometheus/sentinel-crashloop-prometheusrule.example.yaml`](../../deploy/prometheus/sentinel-crashloop-prometheusrule.example.yaml) | `PrometheusRule`：CrashLoopBackOff → `pod` / `namespace` labels |

---

## 前置条件

| 项 | 检查 |
|----|------|
| LangGraph | `curl -sf http://127.0.0.1:2024/ok` |
| sentinel-api | `systemctl is-active sentinel-api`；`curl -sf http://127.0.0.1:8080/health` |
| 图中有 Pod 数据 | 近期 cron sync 或 `sentinel-sync-k8s.sh` |
| crash-demo fixture | `kubectl get pods -n sentinel-sandbox -l app=crash-demo` → CrashLoopBackOff |
| （可选 Prom） | kube-prometheus 已装；见 [DEPLOY-PROMETHEUS-K3S.md](DEPLOY-PROMETHEUS-K3S.md) |

安装 API（若尚未启用）：

```bash
sudo bash /opt/sentinel-x/deploy/config/sentinel-config-apply.sh --with-api --reload
```

---

## Step 1 — 手工 webhook 验收（主路径，无需 Prom）

在 **服务器本机** 执行（与 patrol 使用相同 env）：

```bash
source /opt/sentinel-x/.venv/bin/activate
set -a && source /etc/sentinel/sync-k8s.env && set +a
export LANGGRAPH_RUN_LIVE=1

# 当前 crash-demo Pod 名（随 ReplicaSet 变化）
POD=$(kubectl get pods -n sentinel-sandbox -l app=crash-demo \
  -o jsonpath='{.items[0].metadata.name}')
echo "pod=${POD}"

# 可选：与 patrol 对齐，先 sync
/usr/local/bin/sentinel-sync-k8s.sh

# Bearer：若 /etc/sentinel/sentinel-api.env 配置了 SENTINEL_API_TOKEN
AUTH=()
if [[ -f /etc/sentinel/sentinel-api.env ]]; then
  set -a && source /etc/sentinel/sentinel-api.env && set +a
  if [[ -n "${SENTINEL_API_TOKEN:-}" ]]; then
    AUTH=(-H "Authorization: Bearer ${SENTINEL_API_TOKEN}")
  fi
fi

curl -s -X POST http://127.0.0.1:8080/v1/webhooks/alertmanager \
  -H "Content-Type: application/json" \
  "${AUTH[@]}" \
  -d "{
    \"status\": \"firing\",
    \"alerts\": [{
      \"status\": \"firing\",
      \"labels\": {
        \"alertname\": \"PodCrashLooping\",
        \"pod\": \"${POD}\",
        \"namespace\": \"sentinel-sandbox\"
      }
    }]
  }" | python3 -m json.tool
```

**期望**：

- JSON 含 `"ok": true`（或至少 `"issues"` 含 `"CrashLoop"`，与 `POST /v1/inspect` / patrol 一致）
- `"alert": {"alertname": "PodCrashLooping", ...}`
- `journalctl -u sentinel-api -n 30 --no-pager` 可见 inspect 请求

**对照**（同 Pod、同 thread）：

```bash
curl -s -X POST http://127.0.0.1:8080/v1/inspect \
  -H "Content-Type: application/json" \
  "${AUTH[@]}" \
  -d "{\"pod_name\":\"${POD}\",\"namespace\":\"sentinel-sandbox\",\"dry_run\":true}" \
  | python3 -m json.tool
```

---

## Step 2 — （可选）启用 Alertmanager + receiver

默认 [`kube-prometheus-values-minimal.yaml`](../../deploy/prometheus/kube-prometheus-values-minimal.yaml) **关闭** Alertmanager。合并示例 receiver：

```bash
cd /opt/sentinel-x/dist/kube-prometheus-offline   # 或 deploy/prometheus 旁路 values

# 1) 确认 Alertmanager 能访问 host 上的 :8080（见下文「网络」）
# 2) 编辑 sentinel-alertmanager-receiver.example.yaml 中 webhook URL（如需 host IP）
# 3) helm upgrade，合并 minimal + receiver 两份 values

export KUBE_PROM_VALUES="/opt/sentinel-x/deploy/prometheus/kube-prometheus-values-minimal.yaml"
export KUBE_PROM_EXTRA="/opt/sentinel-x/deploy/prometheus/sentinel-alertmanager-receiver.example.yaml"

helm upgrade kube-prom kube-prometheus-stack \
  --repo file://./helm-local-repo \
  -n monitoring \
  -f "${KUBE_PROM_VALUES}" \
  -f "${KUBE_PROM_EXTRA}" \
  --wait --timeout 15m
```

若使用 [`install-kube-prometheus-offline.sh`](../../deploy/prometheus/install-kube-prometheus-offline.sh)，可一次性指定：

```bash
export KUBE_PROM_VALUES="/opt/sentinel-x/deploy/prometheus/kube-prometheus-values-minimal.yaml"
# 手工合并 receiver 到临时文件，或 helm upgrade 追加 -f receiver
sudo -E bash /opt/sentinel-x/deploy/prometheus/install-kube-prometheus-offline.sh
```

**网络（Alertmanager pod → host API）**：

| 场景 | webhook URL |
|------|-------------|
| 手工 curl（host） | `http://127.0.0.1:8080/v1/webhooks/alertmanager` |
| Alertmanager + `hostNetwork: true`（单节点 k3s 推荐） | 同上 |
| Alertmanager 在 pod 网络 | `http://<节点可达 IP>:8080/v1/webhooks/alertmanager`（如 k3s `host.k3s.internal` 或 `ip route \| awk '/default/{print $3}'`） |

`sentinel-api` 仅绑定 `127.0.0.1:8080` 时，节点 IP 方式需确认 systemd unit 是否监听 `0.0.0.0` 或通过 `hostNetwork` 让 AM 使用 host 网络栈。单节点最简单：**在 receiver values 中启用 `alertmanager.hostNetwork: true`**。

**Bearer 鉴权**：若设置了 `SENTINEL_API_TOKEN`，在 receiver YAML 的 `webhook_configs[].http_config.authorization` 填入相同 token（见示例文件注释）。

---

## Step 3 — （可选）PrometheusRule + kube-state-metrics

`SentinelPodCrashLoop` 依赖 `kube_pod_container_status_waiting_reason`（**kube-state-metrics**）。minimal values 默认 `kube-state-metrics.enabled: false`。

启用 KSM 并应用规则：

```bash
# 临时 values 片段（或与 receiver 一并 helm -f）
cat >/tmp/sentinel-kube-state-metrics.yaml <<'EOF'
kube-state-metrics:
  enabled: true
EOF

helm upgrade kube-prom kube-prometheus-stack \
  --repo file://./helm-local-repo \
  -n monitoring \
  -f /opt/sentinel-x/deploy/prometheus/kube-prometheus-values-minimal.yaml \
  -f /opt/sentinel-x/deploy/prometheus/sentinel-alertmanager-receiver.example.yaml \
  -f /tmp/sentinel-kube-state-metrics.yaml \
  --wait --timeout 15m

kubectl apply -f /opt/sentinel-x/deploy/prometheus/sentinel-crashloop-prometheusrule.example.yaml
```

验证规则与指标：

```bash
# 规则已加载
kubectl get prometheusrule -n monitoring sentinel-crashloop

# 指标存在（需 KSM）
curl -sf 'http://127.0.0.1:30909/api/v1/query?query=kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"}' \
  | python3 -m json.tool | head -40
```

`crash-demo` 持续 CrashLoop 约 **2m+** 后，`SentinelPodCrashLoop` 应 firing；Alertmanager UI / 日志可见向 Sentinel webhook POST。查 API：

```bash
journalctl -u sentinel-api -f
```

---

## 验收检查表

- [ ] 手工 curl（Step 1）返回 `issues` 含 `CrashLoop`（或 `ok=true`）
- [ ] 与 `POST /v1/inspect` 同 Pod 结果一致
- [ ] `journalctl -u sentinel-api` 可追溯 webhook 触发的 inspect
- [ ] （可选）Alertmanager receiver 配置已 merge；AM 能 POST 到 API
- [ ] （可选）`SentinelPodCrashLoop` firing → 自动 trigger

---

## 故障速查

| 现象 | 处理 |
|------|------|
| `422 no alerts in payload` | JSON 需含非空 `alerts` 数组 |
| `422 alert labels must include pod` | `labels.pod` 缺失 |
| `401` / `403` | 设置 `Authorization: Bearer $SENTINEL_API_TOKEN` |
| `ok=false` / 无 issues | 先 `sentinel-sync-k8s.sh`；确认 Pod 在图中；`curl http://127.0.0.1:2024/ok` |
| AM webhook 连接 refused | URL 用了 pod 内 `127.0.0.1` → 改 host IP 或 `hostNetwork: true` |
| 规则不 firing | 启用 KSM；等 `for: 2m`；查 Prom targets |
| 规则未被 Prometheus 选中 | `metadata.labels.release` 与 Helm release 名一致（默认 `kube-prom`） |

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [DEPLOY-ALERT-INSPECT.md](DEPLOY-ALERT-INSPECT.md) | W7 patrol + API 总览 |
| [DEPLOY-PROMETHEUS-K3S.md](DEPLOY-PROMETHEUS-K3S.md) | 离线 kube-prometheus 安装 |
| [DEPLOY-ONE-SHOT.md](DEPLOY-ONE-SHOT.md) | 全栈安装与验收矩阵 |
