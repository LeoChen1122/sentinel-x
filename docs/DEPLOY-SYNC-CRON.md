# W1-3：Cron 增量 Sync 部署

> 公共参数与验证见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md)  
> 目标：每 **5 分钟** 从 MCP 拉取 K8s Pod/Event，**增量**写入 LangGraph。  
> 依赖：**W1-2** `sentinel-langgraph.service` 已运行。

---

## 架构

```text
cron (every 5 min)
  → deploy/sync-k8s.sh
  → mcp_k8s_sync_live.py (--incremental 默认 true)
  → docker exec → MCP → k3s API
  → sync_pods_and_events_resilient → langgraph :2024
  → 指纹状态: /var/lib/sentinel/sync-state/
  → 日志: /var/log/sentinel-sync.log
```

**增量含义**：未变化的 entity 跳过推送（`LANGGRAPH_SYNC_INCREMENTAL=1` + `LANGGRAPH_SYNC_STATE_PATH` 持久化指纹）。

LangGraph **重启后 thread 内存清空**时，cron 或 `ExecStartPost` hook 会 **重建图**（见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md) Checkpoint 契约）。

---

## 前置条件

```bash
# LangGraph 服务在跑
sudo systemctl is-active sentinel-langgraph

# MCP 容器在跑
docker ps --filter name=mcp-k8s

# 手工 sync 曾成功
export MCP_CONTAINER=mcp-servers_mcp-k8s_1
export CLUSTER_ID=k3s-prod
export NAMESPACE=kube-system
export LANGGRAPH_API_URL=http://127.0.0.1:2024
/opt/sentinel-x/.venv/bin/python \
  /opt/sentinel-x/agents/langgraph-integration/scripts/mcp_k8s_sync_live.py
```

---

## Step 1：安装脚本与环境文件

```bash
sudo mkdir -p /etc/sentinel /var/lib/sentinel /var/log
sudo bash /opt/sentinel-x/deploy/install-deploy-scripts.sh

# 生成 sync-k8s.env（来自 master sentinel-x.env）
sudo bash /opt/sentinel-x/deploy/sentinel-config-discover.sh --write
sudo bash /opt/sentinel-x/deploy/sentinel-config-apply.sh
```

`MCP_CONTAINER`、`LANGGRAPH_THREAD_ID` 等由 discover + apply 写入 `/etc/sentinel/sync-k8s.env`，无需手填。容器重建后：

```bash
sudo bash deploy/sentinel-config-discover.sh --write
sudo bash deploy/sentinel-config-apply.sh --reload
```

---

## Step 2：手工试跑 wrapper

```bash
sudo /usr/local/bin/sentinel-sync-k8s.sh
tail -20 /var/log/sentinel-sync.log
```

期望日志含：

```text
START sync cluster=k3s-prod ...
sync ok: chunks=... entities=... skipped=...
OK sync finished
```

第二次运行 `skipped=` 应 **大于 0**（增量生效）。

---

## Step 3：安装 crontab

### 方式 A：root crontab（推荐 Phase 1）

```bash
sudo crontab -e
```

追加一行：

```cron
*/5 * * * * /usr/local/bin/sentinel-sync-k8s.sh >/dev/null 2>&1
```

### 方式 B：/etc/cron.d（便于 git 管理副本）

仓库示例 [`deploy/cron-sentinel-sync.example`](../deploy/cron-sentinel-sync.example)：

```bash
sudo cp /opt/sentinel-x/deploy/cron-sentinel-sync.example /etc/cron.d/sentinel-sync
sudo chmod 644 /etc/cron.d/sentinel-sync
```

内容：

```cron
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
*/5 * * * * root /usr/local/bin/sentinel-sync-k8s.sh >/dev/null 2>&1
```

验证 crontab 已加载：

```bash
cat /etc/cron.d/sentinel-sync
cat -A /etc/cron.d/sentinel-sync    # job 行尾必须是 $ 不是 ^M$
sudo grep sentinel /var/log/syslog | tail -10
```

**cron.d 必检**：

- 权限 `644`（不要 `755`）
- 文件末尾有空行
- **无 CRLF**（Windows 上传会导致 cron 静默忽略任务）

```bash
sudo sed -i 's/\r$//' /etc/cron.d/sentinel-sync
sudo chmod 644 /etc/cron.d/sentinel-sync
sudo systemctl reload cron 2>/dev/null || sudo systemctl restart cron
```

若仍不触发，用 root crontab（更直观）：

```bash
sudo crontab -e
# */5 * * * * /usr/local/bin/sentinel-sync-k8s.sh >/dev/null 2>&1
sudo crontab -l
```

---

## Step 4：验收（15–30 分钟）

```bash
# 1) 等 5–10 分钟看日志是否自动追加
tail -f /var/log/sentinel-sync.log

# 2) 统一验证（list_pods count 与 kubectl 对照）
sudo bash /opt/sentinel-x/deploy/verify-sentinel-x.sh

# 3) 增量状态目录
ls -la /var/lib/sentinel/sync-state/
```

**W1-3 完成标准**：

- 24h 内 `/var/log/sentinel-sync.log` 无连续 ERROR
- `list_pods` count 与 kubectl 一致
- 第二次起常见 `skipped>0`

---

## Step 5：与 LangGraph 重启联动

见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md) Checkpoint 契约。快速验证：

```bash
sudo systemctl restart sentinel-langgraph
sleep 30
sudo bash /opt/sentinel-x/deploy/verify-sentinel-x.sh --after-restart
```

---

## 运维命令

| 操作 | 命令 |
|------|------|
| 立即 sync | `sudo /usr/local/bin/sentinel-sync-k8s.sh` |
| 看日志 | `tail -f /var/log/sentinel-sync.log` |
| 改 namespace/容器 | `sudo bash deploy/sentinel-config-discover.sh --write && deploy/sentinel-config-apply.sh` |
| 暂停 cron | `sudo crontab -e` 注释行，或 `sudo rm /etc/cron.d/sentinel-sync` |
| 清增量指纹（强制全量） | `sudo rm -rf /var/lib/sentinel/sync-state/*` |

---

## 常见问题

### sync exit code=1 / docker exec failed

- MCP 容器名变了：`docker ps` 更新 `MCP_CONTAINER`
- MCP kubeconfig 仍指 `127.0.0.1`：见 [W1-4 DEPLOY-MCP-KUBECONFIG.md](DEPLOY-MCP-KUBECONFIG.md)，重跑 `sentinel-sync-kubeconfig.sh` 后 `docker compose restart mcp-k8s`

### `/usr/bin/env: 'bash\r': No such file or directory`

脚本从 Windows 上传后带 **CRLF** 换行。在服务器上修复：

```bash
sudo sed -i 's/\r$//' /usr/local/bin/sentinel-sync-k8s.sh
sudo sed -i 's/\r$//' /etc/sentinel/sync-k8s.env

sudo chmod +x /usr/local/bin/sentinel-sync-k8s.sh
sudo /usr/local/bin/sentinel-sync-k8s.sh
```

新版 `sync-k8s.sh` 也会在加载 env 时自动去掉 `\r`；仍建议对 env 文件执行一次 `sed` 彻底清理。

### LangGraph not reachable

```bash
sudo systemctl status sentinel-langgraph
sudo systemctl start sentinel-langgraph
```

### SKIP another sync is running

上次 sync 超过 5 分钟未完成；检查 MCP/API 是否卡住，必要时删 lock：

```bash
sudo rm -f /var/run/sentinel-sync.lock
```

### skipped 始终为 0

确认 env 中：

```bash
grep LANGGRAPH_SYNC /etc/sentinel/sync-k8s.env
# LANGGRAPH_SYNC_STATE_PATH=/var/lib/sentinel/sync-state
# LANGGRAPH_SYNC_INCREMENTAL=1
```

且该目录可写。

### cron 已配置但日志 10+ 分钟不变

手工 sync 正常、仅 cron 不跑时：

```bash
cat -A /etc/cron.d/sentinel-sync
sudo sed -i 's/\r$//' /etc/cron.d/sentinel-sync
sudo chmod 644 /etc/cron.d/sentinel-sync
sudo grep sentinel /var/log/syslog | tail -20
```

仍无记录则改用 root crontab：

```bash
echo '*/5 * * * * /usr/local/bin/sentinel-sync-k8s.sh >/dev/null 2>&1' | sudo crontab -
sudo crontab -l
```

调试时可改为每分钟并单独日志：

```bash
* * * * * /usr/local/bin/sentinel-sync-k8s.sh >> /var/log/sentinel-sync-cron.log 2>&1
```

### 多 namespace

Phase 1 脚本 **一次一个 namespace**。要 sync 多个 ns：

- 多条 cron（不同 env 文件），或
- 后续扩展 wrapper 循环 `NAMESPACE=default kube-system`

---

## 文件清单

| 文件 | 作用 |
|------|------|
| [`deploy/sync-k8s.sh`](../deploy/sync-k8s.sh) | cron 入口脚本 |
| [`deploy/sync-k8s.env.example`](../deploy/sync-k8s.env.example) | 环境变量模板 → `/etc/sentinel/sync-k8s.env` |
| [`deploy/cron-sentinel-sync.example`](../deploy/cron-sentinel-sync.example) | `/etc/cron.d/` 示例 |
| [`docs/DEPLOY-LANGGRAPH-SYSTEMD.md`](DEPLOY-LANGGRAPH-SYSTEMD.md) | W1-2 LangGraph 常驻 |
| [`docs/DEPLOY-MCP-KUBECONFIG.md`](DEPLOY-MCP-KUBECONFIG.md) | W1-4 MCP kubeconfig |

---

## 卸载

```bash
sudo crontab -e   # 删除 cron 行
# 或
sudo rm -f /etc/cron.d/sentinel-sync
sudo rm -f /usr/local/bin/sentinel-sync-k8s.sh /etc/sentinel/sync-k8s.env
```
