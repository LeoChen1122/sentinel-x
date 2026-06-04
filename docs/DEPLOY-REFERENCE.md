# Sentinel-X 部署参考（canonical）

> 公共参数、环境变量、验证命令的 **唯一权威来源**。  
> 子文档（DEPLOY-SYNC-CRON、DEPLOY-PROM-SYNC 等）只保留差异步骤，链到本文。

---

## 生产默认参数

| 参数 | 默认值 | 来源 |
|------|--------|------|
| `SENTINEL_ROOT` | `/opt/sentinel-x` | `sentinel-x.env` |
| `CLUSTER_ID` | `k3s-prod` | 默认 / 人工 |
| `NAMESPACE` | `kube-system` | 默认 / 人工 |
| `LANGGRAPH_API_URL` | `http://127.0.0.1:2024` | 默认 |
| `LANGGRAPH_THREAD_ID` | `uuid5("default:{CLUSTER_ID}")` | **AUTO** 计算 |
| `MCP_K8S_CONTAINER` | docker 探测 | **AUTO** |
| `MCP_PROM_CONTAINER` | docker 探测 | **AUTO** |
| `PROMETHEUS_BASE_URL` | `http://host.docker.internal:{port}` | **AUTO** 探测 NodePort |
| Streamlit | `http://127.0.0.1:8501` | SSH 隧道 |

---

## Checkpoint 契约

LangGraph 使用 **`langgraph dev` 内存 checkpoint**（非 Postgres）。

1. `systemctl restart sentinel-langgraph` 后 **thread 图立即为空**。
2. **自动恢复**：
   - `ExecStartPost` → [`deploy/sentinel-langgraph-post-restart.sh`](../deploy/sentinel-langgraph-post-restart.sh) 触发 K8s（+ Prom）sync
   - 或等待 cron（≤5 分钟）
   - 或手工：`sudo /usr/local/bin/sentinel-sync-k8s.sh`
3. **验收**：`sudo bash deploy/verify-sentinel-x.sh` → `list_pods count >= 1`

**Phase 2（W5+ 后）**：评估 Postgres/SQLite 持久化 checkpoint — 见 [ROADMAP.md](ROADMAP.md) W8+。

---

## 环境变量索引

| 变量 | AUTO | 人工 | 写入位置 | 消费者 |
|------|------|------|----------|--------|
| `CLUSTER_ID` | | 可选 | `sentinel-x.env` | sync, query, UI |
| `NAMESPACE` | | 可选 | `sentinel-x.env` | sync, query, UI |
| `LANGGRAPH_THREAD_ID` | yes | 可覆盖 | master → 子 env | sync, query, UI |
| `MCP_K8S_CONTAINER` | yes | 可覆盖 | master → sync-k8s | sync-k8s.sh |
| `MCP_PROM_CONTAINER` | yes | 可覆盖 | master → sync-prom | sync-prom.sh |
| `PROMETHEUS_BASE_URL` | yes | 可覆盖 | master → mcp-servers/.env | MCP Prom |
| `LANGGRAPH_API_URL` | | 默认 | master | 全部 |
| LLM API keys | | **必须** | `langgraph-server/.env` | narrative LLM |

### 配置工作流

```bash
# 唯一人工编辑（多数用默认 + AUTO 即可）
sudo nano /etc/sentinel/sentinel-x.env

# 探测 + 生成全部子 env
sudo bash /opt/sentinel-x/deploy/sentinel-config-discover.sh --write
sudo bash /opt/sentinel-x/deploy/sentinel-config-apply.sh --with-prom-sync --with-ui

# 容器重建后刷新
sudo bash deploy/sentinel-config-discover.sh --write
sudo bash deploy/sentinel-config-apply.sh --discover --reload
```

**子 env 均为生成物**（勿手改）：`/etc/sentinel/sync-k8s.env`、`sync-prom.env`、`sentinel-ui.env`。

---

## 唯一验证命令

```bash
sudo bash /opt/sentinel-x/deploy/verify-sentinel-x.sh
```

LangGraph 刚重启、图可能为空时：

```bash
sudo bash /opt/sentinel-x/deploy/verify-sentinel-x.sh --after-restart
```

期望：

```text
[verify] OK: curl http://127.0.0.1:2024/ok
[verify] OK: MCP returned N pods
[verify] OK: list_pods count=N
[verify] OK: sentinel-langgraph active
[verify] All checks passed.
```

---

## 一键安装入口

见 [DEPLOY-ONE-SHOT.md](DEPLOY-ONE-SHOT.md)。

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [DEPLOY-ONE-SHOT.md](DEPLOY-ONE-SHOT.md) | 新机一键安装 |
| [DEPLOY-SERVER.md](DEPLOY-SERVER.md) | 总索引 |
| [ARCHITECTURE-REVIEW.md](ARCHITECTURE-REVIEW.md) | 架构评审 |
