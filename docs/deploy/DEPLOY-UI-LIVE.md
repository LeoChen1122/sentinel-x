# W4：Streamlit UI 服务器部署与验收

> 公共参数与验证见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md)  
> 目标：在 **sentinel-x 服务器** 上运行 Streamlit，通过 SSH 隧道在浏览器查看 **live Pod 列表**、**Top CPU** 与 **Inspect** 结果。  
> 依赖：**W1**（LangGraph systemd + K8s cron sync）；**W3** 可选（CPU/内存列）；**W2** 可选（Inspect 有诊断数据）。

---

## 架构

```text
[浏览器 @ 本机] ── SSH -L 8501 ──► [Streamlit :8501 @ 服务器]
                                          │
                                          ▼ query_sentinel / stream_sentinel_run
                                 [LangGraph :2024, thread checkpoint]
                                          ▲
                                 [cron K8s sync + 可选 Prom sync]
```

UI **不直接**访问 k3s 或 Prometheus；所有数据来自 LangGraph thread（与 CLI query / inspect 相同）。

---

## 前置条件

| 项 | 验收 |
|----|------|
| W1 LangGraph | `sudo systemctl is-active sentinel-langgraph` → `active` |
| W1 LangGraph HTTP | `curl -sf http://127.0.0.1:2024/ok` |
| W1 K8s sync | `tail -5 /var/log/sentinel-sync.log` 含 `OK sync finished`；或手工 sync 成功 |
| thread 有 Pod | 见 Step 1 一行 query，`count` ≥ 1 |
| Python venv | `/opt/sentinel-x/.venv` 已存在 |
| （可选 W3）Prom sync | `top_pods_by_cpu` 有 `cpu_cores` |

相关文档：[DEPLOY-SERVER.md](DEPLOY-SERVER.md)、[DEPLOY-LANGGRAPH-SYSTEMD.md](DEPLOY-LANGGRAPH-SYSTEMD.md)、[DEPLOY-SYNC-CRON.md](DEPLOY-SYNC-CRON.md)

---

## Step 0：本机上传 W4 代码（服务器无 GitHub）

在 **Windows 本机** PowerShell（按实际 IP 修改）：

```powershell
$HOST = "root@120.77.176.17"
$BASE = "C:\sentinel-x"

# W4 UI
scp -r "$BASE\apps\ui" "${HOST}:/opt/sentinel-x/apps/"

# 若 langgraph-integration 尚未同步过 W3，建议整包 src
scp -r "$BASE\agents\langgraph-integration\src" "${HOST}:/opt/sentinel-x/agents/langgraph-integration/"

# 可选：部署模板与文档
scp "$BASE\deploy\sentinel-ui.service" "${HOST}:/opt/sentinel-x/deploy/"
scp "$BASE\deploy\sentinel-ui.env.example" "${HOST}:/opt/sentinel-x/deploy/"
scp "$BASE\docs\DEPLOY-UI-LIVE.md" "${HOST}:/opt/sentinel-x/docs/"
```

服务器上去 CRLF（若从 Windows scp）：

```bash
find /opt/sentinel-x/apps/ui -type f -exec sed -i 's/\r$//' {} + 2>/dev/null || true
sed -i 's/\r$//' /opt/sentinel-x/deploy/sentinel-ui.env.example 2>/dev/null || true
```

确认文件存在：

```bash
ls -la /opt/sentinel-x/apps/ui/app.py
```

---

## Step 1：安装 Python 依赖

```bash
source /opt/sentinel-x/.venv/bin/activate

pip install -r /opt/sentinel-x/apps/ui/requirements.txt
pip install -r /opt/sentinel-x/agents/langgraph-integration/requirements.txt

# 验证
python -c "import streamlit; print('streamlit', streamlit.__version__)"
```

---

## Step 2：确认 LangGraph 与 thread 有数据

```bash
sudo bash /opt/sentinel-x/deploy/verify/verify-sentinel-x.sh
# 若 count=0：sudo /usr/local/bin/sentinel-sync-k8s.sh
```

**（可选 W3）** 补 CPU/内存列：`sudo /usr/local/bin/sentinel-sync-prom.sh`

---

## Step 3：启动 Streamlit（手工，推荐首次验收）

在服务器上 **前台** 运行（便于看日志）：

```bash
source /opt/sentinel-x/.venv/bin/activate
set -a && source /etc/sentinel/sentinel-ui.env && set +a

streamlit run /opt/sentinel-x/apps/ui/app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --browser.gatherUsageStats false
```

保持该终端不关。期望输出含：

```text
Local URL: http://127.0.0.1:8501
```

---

## Step 4：本机 SSH 隧道 + 浏览器

在 **Windows 本机** 新开 PowerShell（替换 IP；若 host key 变更见 DEPLOY-SERVER 运维说明）：

```powershell
ssh -L 8501:127.0.0.1:8501 root@120.77.176.17
```

保持 SSH 连接，浏览器打开：

```text
http://127.0.0.1:8501
```

侧边栏可改 `LANGGRAPH_API_URL`、`THREAD_ID`、`CLUSTER_ID`、`NAMESPACE`（无需重启 Streamlit）。

---

## Step 5：（可选）systemd 常驻 UI

适合长期演示；仍只监听 `127.0.0.1`，外网访问靠 SSH 隧道。

```bash
sudo cp /opt/sentinel-x/deploy/sentinel-ui.service /etc/systemd/system/
sudo bash /opt/sentinel-x/deploy/config/sentinel-config-apply.sh --with-ui

sudo systemctl daemon-reload
sudo systemctl enable --now sentinel-ui
sudo systemctl status sentinel-ui

# 日志
sudo journalctl -u sentinel-ui -f
```

停止手工 streamlit 进程后再 enable systemd，避免 8501 端口冲突。

---

## Step 6：UI 验收清单（W4 完成标准）

| 页签 | 操作 | 期望 |
|------|------|------|
| 连接状态 | 打开首页 | 无红色 LangGraph 不可达警告 |
| **Pods** | 刷新 / 进入页签 | 表格 ≥1 行，含 `name`、`phase` |
| **Top CPU** | 进入页签 | 有排序列表；W3 后 `cpu_cores` 非空 |
| **Inspect** | 选 Pod（如 `coredns-...`）→ Run inspect | expander 中 diagnosis / narrative / execution 有 JSON |
| 侧边栏 | 改 `NAMESPACE` 为错误值 | 列表空或报错，改回 `kube-system` 恢复 |

Inspect 与 CLI 一致：需 `LANGGRAPH_RUN_LIVE=1`，且 thread 内已有该 Pod 的 Event（W1 sync）。

---

## 故障排查

| 现象 | 处理 |
|------|------|
| 页面警告「Set LANGGRAPH_RUN_LIVE=1」 | 启动 streamlit 前 `export LANGGRAPH_RUN_LIVE=1`；systemd 检查 `/etc/sentinel/sentinel-ui.env` |
| LangGraph unreachable | `sudo systemctl start sentinel-langgraph`；`curl http://127.0.0.1:2024/ok` |
| Pods 表为空 | 图被清空（LangGraph 重启）→ `sudo /usr/local/bin/sentinel-sync-k8s.sh`；确认 sidebar `THREAD_ID` 与 sync 一致 |
| 无 cpu_cores 列 | 跑 W3 `mcp_prom_sync_live.py` |
| `Address already in use :8501` | `ss -lntp \| grep 8501`；停掉旧 streamlit 或改 port |
| SSH 隧道连不上 UI | 确认服务器 streamlit 在跑；隧道命令 `-L 8501:127.0.0.1:8501` |
| Inspect 超时 | LangGraph 内 LLM 慢会回退 template；见 [DEPLOY-INSPECT-LIVE.md](DEPLOY-INSPECT-LIVE.md) |
| ModuleNotFoundError | 确认 `agents/langgraph-integration/src` 已 scp；`pip install -r .../langgraph-integration/requirements.txt` |

---

## 与 W1–W3 的关系

| 周次 | UI 依赖 |
|------|---------|
| W1 | LangGraph + K8s sync → **Pods 页签** |
| W2 | inspect 链 → **Inspect 页签** |
| W3 | Prom sync → **cpu_cores / memory 列、Top CPU 页签** |

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [DEPLOY-SERVER.md](DEPLOY-SERVER.md) | 总索引与验证清单 |
| [apps/ui/README.md](../apps/ui/README.md) | UI 简要说明 |
| [ROADMAP.md](ROADMAP.md) | W4 里程碑 |
