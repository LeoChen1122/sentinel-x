# Sentinel-X 服务器部署总览

> **P0 新机入口（推荐）**：[DEPLOY-ONE-SHOT.md](DEPLOY-ONE-SHOT.md) — `sudo bash deploy/install-sentinel-x.sh` 一键安装。  
> **公共参数与验证**：[DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md)  
> **W4 分步索引**：从零复现 Phase 1b–1c（k3s → MCP → LangGraph → sync → 可选 Prom → UI）。  
> 适用路径：`/opt/sentinel-x`（与生产服务器一致）。

---

## 架构

```text
                    ┌─────────────────────────────────────────┐
                    │              k3s API (:6443)             │
                    └───────────────┬─────────────────────────┘
                                    │ kubeconfig
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
   [MCP-K8s container]      [MCP-Prom container]      [Prometheus NodePort :30909]
          │ docker exec              │ docker exec              ▲
          │ mcp_k8s_sync_live        │ mcp_prom_sync_live       │ host.docker.internal
          └────────────┬─────────────┴────────────┬─────────────┘
                       ▼                          │
              [LangGraph dev :2024]  ◄── systemd sentinel-langgraph
                       │
         query / inspect / top_pods_by_cpu / pod_metrics
                       │
              [Streamlit UI :8501]  (W4, optional)
```

**数据流**：MCP 拉取 K8s/Prom → sync 脚本写入 LangGraph thread checkpoint → query/inspect 读同一线程。

**Live 关键参数**：见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md) 生产默认参数表（`CLUSTER_ID`、`LANGGRAPH_THREAD_ID` 等由 `sentinel-config-apply.sh` 生成）。

---

## 前置条件

| 项 | 要求 |
|----|------|
| OS | Linux（已验证 k3s 单节点） |
| k3s | 控制面可用；`KUBECONFIG=/etc/rancher/k3s/k3s.yaml` |
| Docker | MCP compose 运行 |
| Python | 3.12+；venv 在 `/opt/sentinel-x/.venv` |
| 网络 | 服务器可能 **无法访问 GitHub** → 本机 `scp` 或离线包 |
| 行尾 | Windows 上传脚本后执行 `sed -i 's/\r$//' <file>` |

```bash
# 本机上传（示例）
scp -r sentinel-x root@<server>:/opt/sentinel-x
# 服务器上统一去 CRLF
find /opt/sentinel-x/deploy -name '*.sh' -exec sed -i 's/\r$//' {} +
```

---

## 推荐安装顺序

**新机优先**：执行 [DEPLOY-ONE-SHOT.md](DEPLOY-ONE-SHOT.md) 中的 `install-sentinel-x.sh`，再按需打开下表分步文档排障。

按序号执行；每步对应独立文档。

| 步骤 | 内容 | 文档 |
|------|------|------|
| 0 | 一键安装（可选代替 2–4） | **[DEPLOY-ONE-SHOT.md](DEPLOY-ONE-SHOT.md)** |
| 0b | 代码与 venv（手工路径） | 本文「代码布局」 |
| 1 | k3s 控制面（离线 airgap 若需） | 桌面 phase1b 指南 / 服务器既有 k3s |
| 2 | MCP kubeconfig + compose | [DEPLOY-MCP-KUBECONFIG.md](DEPLOY-MCP-KUBECONFIG.md) |
| 3 | LangGraph systemd 常驻 | [DEPLOY-LANGGRAPH-SYSTEMD.md](DEPLOY-LANGGRAPH-SYSTEMD.md) |
| 4 | K8s 增量 sync（cron） | [DEPLOY-SYNC-CRON.md](DEPLOY-SYNC-CRON.md) |
| 5 | （可选 W3）Prometheus 离线安装 | [DEPLOY-PROMETHEUS-K3S.md](DEPLOY-PROMETHEUS-K3S.md) |
| 6 | （可选 W3）Prom metrics sync | [DEPLOY-PROM-SYNC.md](DEPLOY-PROM-SYNC.md) |
| 7 | Live inspect 验收 | [DEPLOY-INSPECT-LIVE.md](DEPLOY-INSPECT-LIVE.md) |
| 8 | （W4）Streamlit UI | **[DEPLOY-UI-LIVE.md](DEPLOY-UI-LIVE.md)**（scp、SSH 隧道、验收） |

**deploy 脚本模板**：[`deploy/README.md`](../deploy/README.md)（systemd unit、cron、sync shell）。

---

## 代码布局（服务器）

```text
/opt/sentinel-x/
├── agents/
│   ├── langgraph-integration/   # sync, query, MCP clients
│   └── langgraph-server/        # langgraph dev 工作目录
├── mcp-servers/                 # docker-compose MCP
├── deploy/                      # systemd + cron 模板
├── apps/ui/                     # Streamlit (W4)
└── docs/DEPLOY-*.md
```

```bash
source /opt/sentinel-x/.venv/bin/activate
pip install -r /opt/sentinel-x/agents/langgraph-server/requirements.txt
pip install -r /opt/sentinel-x/agents/langgraph-integration/requirements.txt
pip install -U "langgraph-cli[inmem]"
```

---

## 快速验证清单

完成 W1 后应全部通过：

```bash
sudo bash /opt/sentinel-x/deploy/verify-sentinel-x.sh
tail -20 /var/log/sentinel-sync.log
```

W3 追加（Prom）：`curl -s http://127.0.0.1:30909/-/ready`；`sudo /usr/local/bin/sentinel-sync-prom.sh`

W4 UI：见 [DEPLOY-UI-LIVE.md](DEPLOY-UI-LIVE.md)

---

## 运维注意

- **Checkpoint 契约**：见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md)（重启后图空 → post-restart hook / cron sync）。
- **只绑 127.0.0.1**：外网用 SSH 隧道访问 API / UI。
- **thread_id**：由 `sentinel-config-apply.sh` 从 `CLUSTER_ID` 统一生成；sync / query / UI 共用。
- **Inspect live**：`LANGGRAPH_RUN_LIVE=1` + `--thread-only`（见 DEPLOY-INSPECT-LIVE）。

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md) | **canonical** 参数、env、验证 |
| [DEPLOY-ONE-SHOT.md](DEPLOY-ONE-SHOT.md) | **P0** 一键安装与验证 |
| [ARCHITECTURE-REVIEW.md](ARCHITECTURE-REVIEW.md) | 架构评审与技术债 |
| [DEPLOY-LANGGRAPH-SYSTEMD.md](DEPLOY-LANGGRAPH-SYSTEMD.md) | W1-2 LangGraph 开机自启 |
| [DEPLOY-SYNC-CRON.md](DEPLOY-SYNC-CRON.md) | W1-3 K8s 每 5 分钟增量 sync |
| [DEPLOY-MCP-KUBECONFIG.md](DEPLOY-MCP-KUBECONFIG.md) | W1-4 MCP 容器 kubeconfig |
| [DEPLOY-INSPECT-LIVE.md](DEPLOY-INSPECT-LIVE.md) | W2 gather → diagnose → execute E2E |
| [DEPLOY-PROMETHEUS-K3S.md](DEPLOY-PROMETHEUS-K3S.md) | W3 前置：离线 kube-prometheus |
| [DEPLOY-PROM-SYNC.md](DEPLOY-PROM-SYNC.md) | W3 Prom 指标 enrichment |
| [DEPLOY-UI-LIVE.md](DEPLOY-UI-LIVE.md) | W4 Streamlit UI 服务器部署 |
| [ROADMAP.md](ROADMAP.md) | 周计划与进度 |
| [apps/ui/README.md](../apps/ui/README.md) | Streamlit 简要说明 |
