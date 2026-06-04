# W1-4：MCP Kubeconfig 与 docker-compose 固化

> 公共参数与验证见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md)  
> 目标：MCP K8s 容器能通过挂载的 `~/.kube/config` **稳定访问宿主机 k3s API**。  
> 适用：`/opt/sentinel-x`，k3s 在宿主机，MCP 容器名如 `mcp-servers_mcp-k8s_1`。

---

## 问题说明

k3s 默认 kubeconfig（`/etc/rancher/k3s/k3s.yaml`）里 API server 多为：

```yaml
server: https://127.0.0.1:6443
```

`mcp-servers/docker-compose.yml` 把宿主机 `~/.kube` 只读挂到容器 `/root/.kube`。  
在容器内，`127.0.0.1` 指向 **容器自身**，不是宿主机 k3s → `k8s_get_pods` / sync 会连接失败。

**两种可行修复**（二选一即可）：

| 方式 | kubeconfig `server` | compose 要求 |
|------|---------------------|--------------|
| A. 宿主机 LAN IP | `https://192.168.x.x:6443` | 无额外要求 |
| B. `host.docker.internal` | `https://host.docker.internal:6443` | `extra_hosts: host.docker.internal:host-gateway`（仓库已加） |

---

## 架构

```text
[k3s API :6443 on host]
        ↑
   LAN IP 或 host.docker.internal
        ↑
~/.kube/config  (chmod 600)
        ↑ ro mount
[MCP mcp-k8s 容器 /root/.kube/config]
        ↑ docker exec (stdio MCP)
[mcp_k8s_sync_live.py / cron W1-3]
```

**与 W1-2 / W1-3 关系**：LangGraph systemd 与 cron sync 都假设 MCP 容器已能 list Pod；W1-4 应在首次 live sync 前或 kubeconfig 被重置后完成。

---

## 前置条件

```bash
# k3s 在跑
sudo systemctl is-active k3s || sudo systemctl is-active k3s-agent

# 宿主机 kubectl 正常（用 k3s 自带配置）
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get nodes

# MCP 目录
cd /opt/sentinel-x/mcp-servers
docker compose ps
```

---

## Step 1：生成宿主机 `~/.kube/config`

**若 `install-deploy-scripts.sh` 报 `pipefail` / `bash\r` 错误**，是 CRLF；先执行：

```bash
sudo sed -i 's/\r$//' /opt/sentinel-x/deploy/*.sh
```

或不用安装脚本，直接：

```bash
sudo install -m 755 /opt/sentinel-x/deploy/sync-kubeconfig-for-mcp.sh \
  /usr/local/bin/sentinel-sync-kubeconfig.sh
sudo sed -i 's/\r$//' /usr/local/bin/sentinel-sync-kubeconfig.sh
```

在服务器上（root 或部署用户，与 compose 挂载路径一致）：

```bash
sudo bash /opt/sentinel-x/deploy/install-deploy-scripts.sh
# 若仍失败，用上面 sed + install 单行方式

# 默认：从 k3s.yaml 复制到 root 的 ~/.kube/config，并把 127.0.0.1 换成检测到的 LAN IP
sudo KUBECONFIG_TARGET=/root/.kube/config /usr/local/bin/sentinel-sync-kubeconfig.sh

# 查看 server 行
grep server /root/.kube/config
sudo chmod 600 /root/.kube/config
```

**非 root 部署用户**（compose 默认挂 `~/.kube`）：

```bash
/usr/local/bin/sentinel-sync-kubeconfig.sh
grep server ~/.kube/config
chmod 600 ~/.kube/config
```

### 方式 B：使用 `host.docker.internal`

```bash
sudo KUBECONFIG_SERVER=host.docker.internal \
  KUBECONFIG_TARGET=/root/.kube/config \
  /usr/local/bin/sentinel-sync-kubeconfig.sh
```

需确保 `mcp-servers/docker-compose.yml` 中 `mcp-k8s` 含 `extra_hosts`（仓库模板已包含）。

### 环境变量（脚本）

| 变量 | 默认 | 说明 |
|------|------|------|
| `K3S_KUBECONFIG` | `/etc/rancher/k3s/k3s.yaml` | k3s 源文件 |
| `KUBECONFIG_TARGET` | `$HOME/.kube/config` | 写入目标 |
| `KUBECONFIG_SERVER` | `host-ip` | `host-ip` / `host.docker.internal` / `none` |

---

## Step 2：更新 compose 并重启 MCP

```bash
cd /opt/sentinel-x/mcp-servers

# 可选：自定义挂载目录（见 docker-compose 顶部注释）
# export KUBECONFIG_HOST=/root/.kube
# docker compose --env-file .env up -d mcp-k8s

docker compose build mcp-k8s
docker compose up -d mcp-k8s

docker ps --format '{{.Names}}' | grep mcp-k8s
```

`KUBECONFIG_HOST`：宿主机路径，挂载为容器内 `/root/.kube`（默认 `~/.kube`）。  
若用 root 的 config，可设 `KUBECONFIG_HOST=/root/.kube` 或在 `mcp-servers/.env` 中写一行。

---

## Step 3：容器内验证

```bash
MCP=$(docker ps --format '{{.Names}}' | grep mcp-k8s | head -1)
echo "MCP_CONTAINER=$MCP"

docker exec "$MCP" cat /root/.kube/config | grep server
docker exec "$MCP" kubectl get nodes
docker exec "$MCP" kubectl get pods -n kube-system --no-headers | head -5
```

期望：`kubectl get nodes` 成功，server 行 **不是** `https://127.0.0.1:6443`。

---

## Step 4：与 sync / cron 联调

```bash
export MCP_CONTAINER=mcp-servers_mcp-k8s_1   # 按 docker ps 修改
export CLUSTER_ID=k3s-prod
export NAMESPACE=kube-system
export LANGGRAPH_API_URL=http://127.0.0.1:2024

/opt/sentinel-x/.venv/bin/python \
  /opt/sentinel-x/agents/langgraph-integration/scripts/mcp_k8s_sync_live.py
```

成功后再确认 W1-3 cron（见 [DEPLOY-SYNC-CRON.md](DEPLOY-SYNC-CRON.md)）。

**W1-4 完成标准**：

- 容器内 `kubectl get pods -n kube-system` 成功
- 手工 `mcp_k8s_sync_live.py` 无 kubeconfig / connection 错误
- `~/.kube/config`（或 `KUBECONFIG_TARGET`）权限为 `600`

---

## 运维命令

| 操作 | 命令 |
|------|------|
| 重新同步 kubeconfig | `sudo /usr/local/bin/sentinel-sync-kubeconfig.sh` |
| 改用 host.docker.internal | `sudo KUBECONFIG_SERVER=host.docker.internal /usr/local/bin/sentinel-sync-kubeconfig.sh` |
| 重启 MCP | `cd /opt/sentinel-x/mcp-servers && docker compose restart mcp-k8s` |
| 查挂载 | `docker inspect "$MCP" --format '{{json .Mounts}}' \| jq` |

k3s 重装或证书轮换后，重新执行 sync 脚本并 `docker compose restart mcp-k8s`。

---

## 常见问题

### Connection refused / Unable to connect to the server

- 容器内 `grep server /root/.kube/config` 仍为 `127.0.0.1` → 重跑 Step 1
- 用了 LAN IP 但 k3s 只监听 `127.0.0.1`：检查 k3s 绑定或改用 `host.docker.internal` + `extra_hosts`
- 挂载目录不对：确认 `KUBECONFIG_HOST` 与写入的 `KUBECONFIG_TARGET` 一致

### `docker-compose up` 报 `KeyError: 'ContainerConfig'`

常见于 **docker-compose 1.29.x**（`docker-compose` 带连字符）在 **Recreating** 旧容器时与新版 Docker 不兼容。

**处理：先删旧容器再创建（不要依赖 recreate 路径）**

```bash
cd /opt/sentinel-x/mcp-servers

# 方式 1：手动删容器再起（推荐）
docker-compose stop mcp-k8s 2>/dev/null || true
docker rm -f mcp-servers_mcp-k8s_1 2>/dev/null || true
docker-compose up -d mcp-k8s

# 方式 2：若已安装 Compose V2 插件
docker compose up -d mcp-k8s
```

仍失败时：

```bash
docker-compose rm -sf mcp-k8s
docker-compose up -d --no-deps mcp-k8s
docker ps | grep mcp-k8s
```

**注意**：`docker-compose`（v1）与 `docker compose`（v2）不要混用同一项目时可交替，但建议长期改用 v2。

### `host.docker.internal` 无法解析

确认 compose 已拉取含 `extra_hosts` 的版本并重建容器：

```bash
cd /opt/sentinel-x/mcp-servers
grep -A2 extra_hosts docker-compose.yml
docker compose up -d --force-recreate mcp-k8s
```

### sync 仍报 MCP / docker exec 错误

与 [DEPLOY-SYNC-CRON.md](DEPLOY-SYNC-CRON.md) 一致：更新 `/etc/sentinel/sync-k8s.env` 中的 `MCP_CONTAINER`。

### `/usr/bin/env: 'bash\r': No such file or directory`

脚本从 Windows 上传后带 **CRLF** 换行。在服务器上修复：

```bash
sudo sed -i 's/\r$//' /usr/local/bin/sentinel-sync-kubeconfig.sh
sudo chmod +x /usr/local/bin/sentinel-sync-kubeconfig.sh
sudo /usr/local/bin/sentinel-sync-kubeconfig.sh
```

`.gitattributes` 已对 `deploy/*.sh` 强制 LF；仍建议上传后执行一次 `sed`。

### 权限过宽

```bash
chmod 600 ~/.kube/config
# 或
sudo chmod 600 /root/.kube/config
```

---

## 文件清单

| 文件 | 作用 |
|------|------|
| [`mcp-servers/docker-compose.yml`](../mcp-servers/docker-compose.yml) | `extra_hosts`、`KUBECONFIG_HOST` 挂载 |
| [`deploy/sync-kubeconfig-for-mcp.sh`](../deploy/sync-kubeconfig-for-mcp.sh) | 复制 k3s.yaml 并重写 server URL |
| [`docs/DEPLOY-SYNC-CRON.md`](DEPLOY-SYNC-CRON.md) | W1-3 cron（依赖本 kubeconfig） |
| [`docs/DEPLOY-LANGGRAPH-SYSTEMD.md`](DEPLOY-LANGGRAPH-SYSTEMD.md) | W1-2 LangGraph 常驻 |
