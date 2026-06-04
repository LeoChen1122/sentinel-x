# Sentinel-X 一键部署（新机开箱）

> **P0 入口**：在新 Linux 服务器上，用 **一条命令** 复现 W1–W4 已验收栈（MCP + LangGraph + cron sync + 可选 UI/Prom）。  
> **不依赖 GitHub**：请在本机打包后 `scp` 到服务器（见下文）。

---

## 1. 前置条件（installer 不安装 k3s）

| 项 | 要求 |
|----|------|
| OS | Linux x86_64（与现网验收一致） |
| k3s | 已安装且 `kubectl get nodes` 正常；kubeconfig 默认 `/etc/rancher/k3s/k3s.yaml` |
| Docker | 可运行 `docker ps` |
| Python | 3.12+（`python3 --version`） |
| 权限 | root 或 `sudo` |
| 磁盘 | `/opt/sentinel-x` 建议 ≥ 2GB（含 venv；含 Prom 离线包时更大） |

k3s 离线安装见桌面 phase1b 指南或既有 airgap 文档；本脚本 **只检查 kubeconfig 是否存在**，不拉取 k3s 安装包。

---

## 2. 本机准备（无 GitHub 的服务器）

### 2.1 拷贝仓库

```bash
# 本机（有 Git 的环境）
cd /path/to/sentinel-x
# 可选：去掉 .git 减小体积
tar czf sentinel-x.tgz --exclude='.git' --exclude='**/__pycache__' .

scp sentinel-x.tgz root@<新服务器>:/tmp/
ssh root@<新服务器>
mkdir -p /opt/sentinel-x
tar xzf /tmp/sentinel-x.tgz -C /opt/sentinel-x --strip-components=0
# 若 tar 顶层为 sentinel-x/ 目录，则确保代码在 /opt/sentinel-x
```

### 2.2 行尾（Windows 上传必做）

```bash
find /opt/sentinel-x/deploy -name '*.sh' -exec sed -i 's/\r$//' {} +
```

### 2.3 可选：Prometheus 离线包

若需要 W3 指标（`top_pods_by_cpu`），在本机先准备 `dist/kube-prometheus-offline/`（见 [DEPLOY-PROMETHEUS-K3S.md](DEPLOY-PROMETHEUS-K3S.md)），与仓库一并 scp。

---

## 3. 一键安装

### 3.1 编辑主配置（推荐）

```bash
sudo mkdir -p /etc/sentinel
sudo cp /opt/sentinel-x/deploy/sentinel-x.env.example /etc/sentinel/sentinel-x.env
sudo nano /etc/sentinel/sentinel-x.env
# 至少确认: CLUSTER_ID, NAMESPACE, PROMETHEUS_BASE_URL（若已装 Prom）
sudo sed -i 's/\r$//' /etc/sentinel/sentinel-x.env
```

### 3.2 执行安装脚本

**最小栈**（K8s MCP + LangGraph + cron + 首次 sync）：

```bash
cd /opt/sentinel-x
sudo bash deploy/install-sentinel-x.sh
```

**常用选项**：

```bash
# + Streamlit UI systemd
sudo bash deploy/install-sentinel-x.sh --with-ui

# + 离线 kube-prometheus（需 dist/kube-prometheus-offline/）
sudo bash deploy/install-sentinel-x.sh --with-prometheus --with-prom-sync

# 仅重装 LangGraph/MCP，跳过首次 sync
sudo bash deploy/install-sentinel-x.sh --skip-sync
```

安装过程会：

1. 创建 `/opt/sentinel-x/.venv` 并安装 pip 依赖  
2. `install-deploy-scripts.sh` → `/usr/local/bin/sentinel-sync-*.sh`  
3. `sentinel-sync-kubeconfig.sh` → `~/.kube/config`（改写 server 为宿主机 IP）  
4. `docker-compose` 启动 `mcp-k8s`、`mcp-prometheus`（必要时先 `docker rm` 规避 1.29 bug）  
5. `sentinel-config-discover.sh --write` + `sentinel-config-apply.sh` → 生成全部 `/etc/sentinel/*.env`  
6. 启用 `sentinel-langgraph.service`  
7. 安装 `/etc/cron.d/sentinel-sync`（每 5 分钟 K8s sync）  
8. 等待 `curl http://127.0.0.1:2024/ok` 并执行首次 sync  

---

## 4. 验证

```bash
sudo bash /opt/sentinel-x/deploy/verify-sentinel-x.sh
```

或手工：

```bash
curl -s http://127.0.0.1:2024/ok
tail -20 /var/log/sentinel-sync.log
systemctl status sentinel-langgraph
```

`LANGGRAPH_THREAD_ID` 由 discover + apply 从 `CLUSTER_ID` 计算。详见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md)。

---

## 5. 安装后访问

| 服务 | 地址 | 外网访问 |
|------|------|----------|
| LangGraph API | `http://127.0.0.1:2024` | `ssh -L 2024:127.0.0.1:2024 root@<host>` |
| Streamlit UI | `http://127.0.0.1:8501` | `ssh -L 8501:127.0.0.1:8501 root@<host>` |

Inspect / Prom / UI 细节仍见专题文档：

- [DEPLOY-INSPECT-LIVE.md](DEPLOY-INSPECT-LIVE.md)
- [DEPLOY-PROM-SYNC.md](DEPLOY-PROM-SYNC.md)
- [DEPLOY-UI-LIVE.md](DEPLOY-UI-LIVE.md)

---

## 6. 运维契约（必读）

见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md) **Checkpoint 契约** 与 **环境变量索引**。容器重建后：

```bash
sudo bash deploy/sentinel-config-discover.sh --write
sudo bash deploy/sentinel-config-apply.sh --reload
```

---

## 7. 故障速查

| 现象 | 处理 |
|------|------|
| `ContainerConfig` compose 错误 | 脚本已 `docker rm`；仍失败则 `cd mcp-servers && docker-compose rm -sf mcp-k8s && docker-compose up -d mcp-k8s` |
| MCP 0 pods | 检查 `~/.kube/config` server 是否为宿主机 IP；重跑 `sentinel-sync-kubeconfig.sh` |
| LangGraph 起不来 | `journalctl -u sentinel-langgraph -n 50`；确认 venv 中 `langgraph --version` |
| Prom sync 失败 | 先 `curl http://127.0.0.1:30909/-/ready`；`mcp-servers/.env` 中 `PROMETHEUS_BASE_URL` |

---

## 8. 相关文档

| 文档 | 说明 |
|------|------|
| [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md) | canonical 参数、checkpoint、env |
| [DEPLOY-SERVER.md](DEPLOY-SERVER.md) | 分步部署总索引 |
| [ARCHITECTURE-REVIEW.md](ARCHITECTURE-REVIEW.md) | 架构评审与 P0/P1 建议 |
| [deploy/README.md](../deploy/README.md) | systemd / cron 文件表 |
