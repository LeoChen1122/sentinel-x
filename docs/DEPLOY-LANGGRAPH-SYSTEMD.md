# W1-2：LangGraph systemd 常驻部署

> 目标：`langgraph dev` 在服务器上 **开机自启、崩溃自动拉起**，监听 `127.0.0.1:2024`。  
> 适用路径：`/opt/sentinel-x`（与当前 `sentinel-x` 服务器一致）。

---

## 架构说明

```text
systemd (sentinel-langgraph.service)
  → /opt/sentinel-x/.venv/bin/langgraph dev
  → WorkingDirectory: agents/langgraph-server
  → 加载 agents/langgraph-server/.env
  → 图 id: sentinel (langgraph.json)
  → 集成代码: agents/langgraph-integration/src (graph.py 内 sys.path)
```

**注意**：

- `langgraph dev` 使用 **内存 checkpoint**；进程重启后 thread 图状态会丢，需靠 **cron sync**（W1-3）重建。
- API 只绑 `127.0.0.1`，外网访问请用 SSH 隧道：  
  `ssh -L 2024:127.0.0.1:2024 root@sentinel-x`

---

## 前置条件检查

在服务器上逐项执行：

```bash
# 1) Python 与 venv
/opt/sentinel-x/.venv/bin/python --version    # 需要 3.12+
/opt/sentinel-x/.venv/bin/langgraph --version

# 2) 依赖（缺则安装）
source /opt/sentinel-x/.venv/bin/activate
pip install -U "langgraph-cli[inmem]"
pip install -r /opt/sentinel-x/agents/langgraph-server/requirements.txt
pip install -r /opt/sentinel-x/agents/langgraph-integration/requirements.txt

# 3) 图能手工启动（先验证再 systemd）
cd /opt/sentinel-x/agents/langgraph-server
langgraph dev --host 127.0.0.1 --port 2024 --no-browser
# 另开终端：
curl -s http://127.0.0.1:2024/ok
# 手工进程 Ctrl+C 停掉后再装 systemd
```

若 `langgraph --version` 报错，先装 CLI 再往下。

---

## Step 1：准备 `.env`

编辑（**仅 ASCII 行**，避免编码问题）：

```bash
nano /opt/sentinel-x/agents/langgraph-server/.env
```

**最小示例**：

```bash
LANGGRAPH_API_URL=http://127.0.0.1:2024

# 可选 LLM（narrate 节点在 *本进程* 内读这些变量）
# SENTINEL_LLM_ENABLED=1
# DASHSCOPE_API_KEY=sk-xxx
# OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# SENTINEL_LLM_MODEL=qwen3.6-plus
# SENTINEL_LLM_ENABLE_THINKING=0
# SENTINEL_LLM_TIMEOUT_SEC=90

# 可选 LangSmith
# LANGSMITH_API_KEY=lsv2_xxx
# LANGSMITH_TRACING=true
```

权限：

```bash
chmod 600 /opt/sentinel-x/agents/langgraph-server/.env
```

**勿将真实 key 提交 git。**

---

## Step 2：安装 systemd unit

仓库内模板：[`deploy/sentinel-langgraph.service`](../deploy/sentinel-langgraph.service)

```bash
# 若从本机 scp 了仓库，或 git pull 后：
sudo cp /opt/sentinel-x/deploy/sentinel-langgraph.service /etc/systemd/system/sentinel-langgraph.service

# 若路径不是 /opt/sentinel-x，编辑 unit 内所有路径后再 cp：
# sudo nano /etc/systemd/system/sentinel-langgraph.service

sudo systemctl daemon-reload
```

---

## Step 3：启动并设为开机自启

```bash
sudo systemctl enable sentinel-langgraph
sudo systemctl start sentinel-langgraph
sudo systemctl status sentinel-langgraph --no-pager
```

期望：`Active: active (running)`。

---

## Step 4：验收

```bash
# HTTP 健康
curl -s http://127.0.0.1:2024/ok

# 日志（启动约 10–30s 内应看到 Uvicorn / Application startup）
sudo journalctl -u sentinel-langgraph -n 50 --no-pager

# SDK 连通（integration 目录）
source /opt/sentinel-x/.venv/bin/activate
export LANGGRAPH_API_URL=http://127.0.0.1:2024
export LANGGRAPH_RUN_LIVE=1
cd /opt/sentinel-x/agents/langgraph-integration
python scripts/langgraph_live_verify.py
```

**若已有 sync 数据**，再验 query：

```bash
export PYTHONPATH=/opt/sentinel-x/agents/langgraph-integration/src
export LANGGRAPH_THREAD_ID=5ad00ee0-6f4d-5cd6-a021-99469a86e4e1

python -c "
from clients.langgraph_client import query_sentinel
print(query_sentinel('list_pods', thread_id='$LANGGRAPH_THREAD_ID',
      cluster_id='k3s-prod', namespace='kube-system'))
"
```

重启后 thread 可能为空 → 需再跑 `mcp_k8s_sync_live.py`（W1-3 cron 会处理）。

---

## Step 5：日常运维命令

```bash
# 状态
sudo systemctl status sentinel-langgraph

# 重启（改 .env 后必做）
sudo systemctl restart sentinel-langgraph

# 停止
sudo systemctl stop sentinel-langgraph

# 实时日志
sudo journalctl -u sentinel-langgraph -f

# 最近 200 行
sudo journalctl -u sentinel-langgraph -n 200 --no-pager
```

---

## 常见问题

### 1. `failed to run` / exit code 1

```bash
sudo journalctl -u sentinel-langgraph -n 80 --no-pager
```

常见原因：

| 日志关键词 | 处理 |
|------------|------|
| `langgraph: command not found` | 确认 `ExecStart` 指向 `/opt/sentinel-x/.venv/bin/langgraph` |
| `ModuleNotFoundError` | `pip install -r` 两个 requirements；integration 路径由 graph.py 注入 |
| `Address already in use` | 旧的手动 `langgraph dev` 还在跑：`pkill -f "langgraph dev"` 后 restart |
| `.env` UnicodeDecodeError | `.env` 改 ASCII-only |
| Python 版本不符 | `langgraph.json` 声明 3.13；3.12 一般可用，不行则升级 venv |

### 2. 端口被占用

```bash
ss -tlnp | grep 2024
# 杀掉占用进程后再 start
sudo systemctl restart sentinel-langgraph
```

### 3. 改了 LLM key 不生效

LLM 在 **langgraph 进程**读 `.env`：

```bash
sudo systemctl restart sentinel-langgraph
```

### 4. 重启后 list_pods 为空

dev 模式 checkpoint 在内存 → **正常**。执行：

```bash
python /opt/sentinel-x/agents/langgraph-integration/scripts/mcp_k8s_sync_live.py
```

并配置 W1-3 cron。

### 5. 与手动 `langgraph dev` 冲突

**只保留一种**：启用 systemd 后不要再开第二个 dev 进程。

---

## 与 W1-3 / W1-4 的关系

| 项 | 说明 |
|----|------|
| W1-3 cron sync | LangGraph 重启后靠 sync 恢复图数据 |
| W1-4 MCP kubeconfig | 与 LangGraph 无关，但 sync 依赖 MCP |
| 顺序建议 | **W1-2 systemd → W1-3 cron → 24h 观察** |

---

## 卸载 / 回滚

```bash
sudo systemctl stop sentinel-langgraph
sudo systemctl disable sentinel-langgraph
sudo rm /etc/systemd/system/sentinel-langgraph.service
sudo systemctl daemon-reload
# 改回手工：cd agents/langgraph-server && langgraph dev ...
```

---

## 文件清单

| 文件 | 作用 |
|------|------|
| [`deploy/sentinel-langgraph.service`](../deploy/sentinel-langgraph.service) | systemd unit 模板 |
| `agents/langgraph-server/.env` | 进程环境（LLM / LangSmith） |
| `agents/langgraph-server/langgraph.json` | 图注册 `sentinel` |
| [`docs/LLM-NARRATIVE.md`](LLM-NARRATIVE.md) | LLM 配置说明 |

**W1-2 完成标准**：`systemctl is-enabled sentinel-langgraph` 为 `enabled`；重启机器后 `curl http://127.0.0.1:2024/ok` 仍成功。
