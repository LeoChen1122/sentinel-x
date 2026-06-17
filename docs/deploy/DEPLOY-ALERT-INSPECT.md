# W7：告警入口 + 半自动 inspect 闭环

> 公共参数见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md)  
> 目标：从「人工 query / inspect demo」到 **事件驱动一次诊断**（cron 巡检或 Webhook → LangGraph inspect）。

---

## 架构

```text
[cron sentinel-inspect-patrol.sh]  ──┐
[POST /v1/inspect]                 ├──► trigger_inspect ──► LangGraph graph
[POST /v1/webhooks/alertmanager]   ──┘         │
                                               ▼
                                    diagnose → execute → sandbox → record_skill
```

**共享模块**：[`agents/langgraph-integration/src/trigger/`](../../agents/langgraph-integration/src/trigger/)

---

## 前置条件

- W1–W6 live 已通过（LangGraph systemd、K8s sync、inspect 链）
- `sentinel-langgraph` active；`curl http://127.0.0.1:2024/ok`
- 图中有目标 Pod 数据（cron sync 或手工 `sentinel-sync-k8s.sh`）

---

## Step 1 — 安装 patrol 脚本

```bash
sudo bash /opt/sentinel-x/deploy/install/install-deploy-scripts.sh
which sentinel-inspect-patrol.sh
```

---

## Step 2 — 手工 patrol（推荐首次验收）

```bash
source /opt/sentinel-x/.venv/bin/activate
set -a && source /etc/sentinel/sync-k8s.env && set +a
export LANGGRAPH_RUN_LIVE=1
export SENTINEL_PATROL_DRY_RUN=true

# 先 sync，再巡检
/usr/local/bin/sentinel-inspect-patrol.sh --sync-first
# 或直接：
python /opt/sentinel-x/agents/langgraph-integration/scripts/live/inspect_patrol_live.py \
  --sync-first --dry-run true
```

**期望**：

- 存在 CrashLoop / ImagePullBackOff Pod 时：`status: ok`，stderr 含 `issues=['CrashLoop']`
- 无候选：`exit 2`，`no_candidates` 或 `cooldown`
- 默认 `dry_run=true` → `execution.sandbox_pending=false`，`status=simulated`

指定 Pod（调试）：

```bash
python .../inspect_patrol_live.py --pod sentinel-crash-test --dry-run true
```

---

## Step 3 — cron 巡检（生产）

追加到 `/etc/cron.d/sentinel-sync`（K8s sync 每 5 分钟，patrol 滞后 3 分钟）：

```cron
5-59/5 * * * * root /usr/local/bin/sentinel-inspect-patrol.sh >>/var/log/sentinel-patrol.log 2>&1
```

日志：

```bash
tail -30 /var/log/sentinel-patrol.log
```

Cooldown 状态：`/var/lib/sentinel/inspect-patrol-state.json`

---

## Step 4 — 可选 FastAPI（Webhook）

### 4.1 安装

```bash
sudo bash /opt/sentinel-x/deploy/install/install-sentinel-x.sh --with-api
# 或已有栈：
sudo bash /opt/sentinel-x/deploy/config/sentinel-config-apply.sh --with-api --reload
```

### 4.2 验证

```bash
curl -s http://127.0.0.1:8080/health

curl -s -X POST http://127.0.0.1:8080/v1/inspect \
  -H "Content-Type: application/json" \
  -d '{"pod_name":"sentinel-crash-test","namespace":"kube-system","dry_run":true}'
```

SSH 隧道（本机调试）：`ssh -L 808 0:127.0.0.1:8080 root@<host>`

### 4.3 Alertmanager webhook 示例

```yaml
receivers:
  - name: sentinel-x
    webhook_configs:
      - url: http://127.0.0.1:8080/v1/webhooks/alertmanager
        send_resolved: false
```

告警 labels 需含 `pod`；`namespace` 可选（默认 `kube-system`）。

---

## Step 5 — E2E demo

```bash
export LANGGRAPH_RUN_LIVE=1
set -a && source /etc/sentinel/sync-k8s.env && set +a

python /opt/sentinel-x/agents/langgraph-integration/scripts/demo/alert_to_inspect_demo.py \
  --mode patrol --sync-first --dry-run true

# API 路径（需 sentinel-api active）：
python .../alert_to_inspect_demo.py --mode api --pod sentinel-crash-test --dry-run true
```

---

## W7 验收检查表

- [x] `sentinel-inspect-patrol.sh` 安装且可执行
- [x] CrashLoop Pod 触发 inspect，`issues` 含 `CrashLoop`（`crash-demo` @ `sentinel-sandbox`，2026-06-17 live）
- [x] 默认 `SENTINEL_PATROL_DRY_RUN=true`（无生产写）
- [x] cooldown：同 Pod 二次 patrol → `status: cooldown`（`inspect-patrol-state.json`）
- [ ] （可选）`POST /v1/inspect` 与 patrol 结果一致
- [ ] （可选）Alertmanager webhook 解析 `pod` label 并 trigger
- [ ] 查 / 判 / 试 / 记：stream 含 `diagnosis`、`execution`；`dry_run=false` 时含 `sandbox_result`

---

## 环境变量（W7）

| 变量 | 默认 | 说明 |
|------|------|------|
| `SENTINEL_PATROL_ENABLED` | `1` | `0` 禁用 patrol |
| `SENTINEL_PATROL_COOLDOWN_SEC` | `3600` | 同 Pod 最短 re-inspect 间隔 |
| `SENTINEL_PATROL_STATE_PATH` | `/var/lib/sentinel/inspect-patrol-state.json` | cooldown 状态 |
| `SENTINEL_PATROL_DRY_RUN` | `true` | patrol / webhook 默认 dry_run |
| `SENTINEL_PATROL_LOG` | `/var/log/sentinel-patrol.log` | patrol 日志 |
| `SENTINEL_API_TOKEN` | — | API Bearer（空=不鉴权，仅 localhost） |

---

## 故障速查

| 现象 | 处理 |
|------|------|
| `no_candidates` | 先 sync；确认 Pod status 为 CrashLoopBackOff 等 |
| `cooldown` | 正常；调 `SENTINEL_PATROL_COOLDOWN_SEC` 或删 state 文件 |
| API connection refused | `systemctl status sentinel-api` |
| inspect 无 issues | Pod 不在图中；检查 namespace / thread_id |

---

## 相关文件

| 文件 | 作用 |
|------|------|
| [`src/trigger/inspect_trigger.py`](../../agents/langgraph-integration/src/trigger/inspect_trigger.py) | 共享 inspect 触发 |
| [`src/trigger/patrol.py`](../../agents/langgraph-integration/src/trigger/patrol.py) | 候选 Pod 扫描 + cooldown |
| [`scripts/live/inspect_patrol_live.py`](../../agents/langgraph-integration/scripts/live/inspect_patrol_live.py) | Live patrol CLI |
| [`deploy/sync/sentinel-inspect-patrol.sh`](../../deploy/sync/sentinel-inspect-patrol.sh) | cron 入口 |
| [`apps/api/`](../../apps/api/) | FastAPI Webhook 薄层 |
