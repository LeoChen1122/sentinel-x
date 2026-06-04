# W2：Live Inspect + 诊断 E2E 部署与验收

> 公共参数与验证见 [DEPLOY-REFERENCE.md](DEPLOY-REFERENCE.md)  
> 目标：在 **真实 k3s 集群** 上，对已 sync 的 LangGraph thread 跑通  
> `ingest → gather → diagnose → narrate → execute → query` 中的 inspect 链（gather/diagnosis/narrative/execution）。  
> 依赖：**W1**（k3s、MCP、LangGraph systemd、cron sync、thread 有 live 图数据）。

---

## 架构

```text
[cron / 手工 mcp_k8s_sync_live.py]
        ↓ entities + edges
[langgraph dev :2024, thread checkpoint]
        ↓ payload.inspect + --thread-only
[inspect_langgraph_live_demo.py]
        ↓ stream_sentinel_run
[graph: ingest → gather → diagnose → narrate → execute → query]
        ↓
gather / diagnosis / narrative / execution（脚本打印后 4 项中的 3 项 + narrative 摘要）
```

**与 mock 的区别**：live 验收应使用 **`--thread-only`**，只发 `{"inspect": {...}}`，不附带 `dual_cluster_rich_batch()` 的 mock 实体；gather 从 thread 里已 sync 的 Pod/Event 查询。

**启用 live 的方式**：设置环境变量 **`LANGGRAPH_RUN_LIVE=1`**（脚本 **没有** `--live` 参数）。

---

## 前置条件（W1 清单）

在服务器上逐项确认：

| 项 | 验收命令 / 期望 |
|----|----------------|
| k3s | `sudo systemctl is-active k3s` → `active` |
| MCP | `docker ps --filter name=mcp-k8s` → Up |
| kubeconfig | 见 [DEPLOY-MCP-KUBECONFIG.md](DEPLOY-MCP-KUBECONFIG.md)，容器内 `kubectl get pods -n kube-system` 成功 |
| LangGraph | `sudo systemctl is-active sentinel-langgraph` → `active`；`curl -s http://127.0.0.1:2024/ok` |
| cron sync | 见 [DEPLOY-SYNC-CRON.md](DEPLOY-SYNC-CRON.md)；`tail -5 /var/log/sentinel-sync.log` 含 `OK sync finished` |
| 手工 sync | 见下文 Step 0；`entities` > 0 |
| query | `sudo bash deploy/verify-sentinel-x.sh` → `list_pods count >= 1` |

相关文档：

- [DEPLOY-LANGGRAPH-SYSTEMD.md](DEPLOY-LANGGRAPH-SYSTEMD.md) — W1-2  
- [DEPLOY-SYNC-CRON.md](DEPLOY-SYNC-CRON.md) — W1-3  
- [DEPLOY-MCP-KUBECONFIG.md](DEPLOY-MCP-KUBECONFIG.md) — W1-4  

---

## Step 0：环境与连通性

```bash
source /opt/sentinel-x/.venv/bin/activate
cd /opt/sentinel-x/agents/langgraph-integration

set -a && source /etc/sentinel/sync-k8s.env && set +a
export LANGGRAPH_RUN_LIVE=1
```

脚本会自动把 `agents/langgraph-integration/src` 加入 `sys.path`，**一般无需** 手工 `export PYTHONPATH`。若从其他目录调用 Python 模块失败，可显式：

```bash
export SENTINEL_INTEGRATION_SRC=/opt/sentinel-x/agents/langgraph-integration/src
export PYTHONPATH="${SENTINEL_INTEGRATION_SRC}${PYTHONPATH:+:$PYTHONPATH}"
```

**连通性自检**（mock ingest + crash-pod，不依赖 cluster sync）：

```bash
python scripts/langgraph_live_verify.py
```

期望全部 `[OK]`，最后一行提示可跑 inspect demo。

**确认 thread 有 live 数据**：

```bash
sudo bash /opt/sentinel-x/deploy/verify-sentinel-x.sh
kubectl get pods -n kube-system --no-headers | wc -l
```

两处的 Pod 数量应接近（cron 增量时 `events` 可能为 0，但 Pod 实体应在图中）。

**解析目标 Pod 全名**（Path A 用）：

```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns -o jsonpath='{.items[0].metadata.name}{"\n"}'
# 示例：coredns-6648f7576f-kg9bh
```

---

## Path A：健康 / 系统 Pod（coredns）

**目的**：验证 live gather + 规则诊断 + 模板叙事 + **dry-run execution**；对仅有 Warning 类事件的 Pod，issues 常为 `WarningEvents`。

### A.1 执行 inspect

将 `<coredns-pod>` 换成上一步得到的名称：

```bash
cd /opt/sentinel-x/agents/langgraph-integration
export LANGGRAPH_RUN_LIVE=1
export LANGGRAPH_API_URL=http://127.0.0.1:2024

python scripts/inspect_langgraph_live_demo.py \
  --thread-only \
  --cluster-id k3s-prod \
  --namespace kube-system \
  --pod-name coredns-6648f7576f-kg9bh \
  --thread-id "$LANGGRAPH_THREAD_ID" \
  --dry-run true
```

### A.2 期望输出

| 字段 | 典型值 |
|------|--------|
| `payload_mode` | `thread_only` |
| `diagnosis.issues` | `["WarningEvents"]`（有 Warning Event 时），或 **空**（无事件、Pod Running） |
| `diagnosis.recommended_actions` | `["review_events"]`（与 WarningEvents 配对） |
| `diagnosis.diagnosis_source` | `rules_v1` |
| `execution.execution_source` | `registry_v1` |
| `execution.dry_run` | `true` |
| `execution.actions_taken[].action` | `review_events`（有推荐动作时） |
| `execution.actions_taken[].status` | `simulated` |
| `narrative_source` | `template`（未开 LLM） |
| 进程退出码 | **0**（issues 非空且 actions 有记录时） |

**说明**：

- 若 Pod **完全健康**（无 Warning Event、非 CrashLoop），`diagnosis.issues` 可能为空，脚本会打印 `WARN: no diagnosis issues` 并以 **exit 1** 结束——这表示「规则未命中」，不一定是 LangGraph 故障。W2 完整验收请继续做 **Path B**。
- 已在服务器上跑通示例：`WarningEvents` → `review_events`，`narrative_source=template`，**exit 0**。

---

## Path B：CrashLoop 测试 Pod + sync + inspect

**目的**：验收 **W2-3** execution dry-run：`CrashLoop` → `restart_pod`（模拟，不写 K8s API）。

### B.1 部署测试 Pod（kube-system，与 cron namespace 一致）

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: sentinel-crash-test
  namespace: kube-system
  labels:
    app: sentinel-crash-test
spec:
  restartPolicy: Always
  containers:
  - name: crash
    image: invalid.example/nonexistent:never
EOF

kubectl wait -n kube-system --for=condition=Ready pod/sentinel-crash-test --timeout=30s 2>/dev/null || true
kubectl get pod -n kube-system sentinel-crash-test
```

期望 STATUS 为 `CrashLoopBackOff` 或 `ImagePullBackOff`（随后 Event 含 BackOff 时规则也会判 `CrashLoop`）。

### B.2 同步到 LangGraph

```bash
export MCP_CONTAINER=mcp-servers_mcp-k8s_1
export CLUSTER_ID=k3s-prod
export NAMESPACE=kube-system
export LANGGRAPH_API_URL=http://127.0.0.1:2024

/opt/sentinel-x/.venv/bin/python \
  /opt/sentinel-x/agents/langgraph-integration/scripts/mcp_k8s_sync_live.py
```

或：

```bash
sudo /usr/local/bin/sentinel-sync-k8s.sh
tail -5 /var/log/sentinel-sync.log
```

### B.3 执行 inspect

```bash
cd /opt/sentinel-x/agents/langgraph-integration
export LANGGRAPH_RUN_LIVE=1
export LANGGRAPH_API_URL=http://127.0.0.1:2024

python scripts/inspect_langgraph_live_demo.py \
  --thread-only \
  --cluster-id k3s-prod \
  --namespace kube-system \
  --pod-name sentinel-crash-test \
  --thread-id "$LANGGRAPH_THREAD_ID" \
  --dry-run true
```

### B.4 期望输出（W2-3 完成标准）

| 字段 | 期望 |
|------|------|
| `diagnosis.issues` | 含 **`CrashLoop`** |
| `diagnosis.recommended_actions` | 含 **`restart_pod`** |
| `diagnosis.severity` | `critical` |
| `execution.actions_taken` | 至少一条 `action: restart_pod`，`status: simulated` |
| `execution.dry_run` | `true`（默认；未设 `SENTINEL_EXECUTE_LIVE=1`） |
| 退出码 | **0**，末尾 `OK: inspect LangGraph live demo complete` |

### B.5 清理（可选）

```bash
kubectl delete pod -n kube-system sentinel-crash-test --ignore-not-found
# 再跑一次 sync，图中移除该 Pod
sudo /usr/local/bin/sentinel-sync-k8s.sh
```

若测试 Pod 建在 **其他 namespace**，须临时修改 `/etc/sentinel/sync-k8s.env` 的 `NAMESPACE` 或增加 cron 条目，否则图中没有该 Pod。

---

## `--thread-only` 与 mock ingest

| 模式 | payload | 适用场景 |
|------|---------|----------|
| **默认（无 `--thread-only`）** | `dual_cluster_rich_batch()` + `inspect` | 本地/CI：mock 图里含 `crash-pod` CrashLoop，不依赖服务器 sync |
| **`--thread-only`** | 仅 `{"inspect": {...}}` | **服务器 live**：用 cron/sync 写入 thread 的真实 Pod/Event |

live 服务器 **必须** `--thread-only`，否则 ingest 会合并 mock 实体，gather 可能查到错误 Pod 或混杂数据。

`--dry-run true`（默认）：execute 节点只走 **模拟** handler；即使传 `--dry-run false`，在未设置 `SENTINEL_EXECUTE_LIVE=1` 时也不会调用真实 K8s API。

---

## 可选：LLM 叙事（W2-4）

LLM 在 **langgraph-server 进程**内执行，配置写在 `agents/langgraph-server/.env`，修改后需重启 systemd：

```bash
sudo nano /opt/sentinel-x/agents/langgraph-server/.env
```

```bash
SENTINEL_LLM_ENABLED=1
DASHSCOPE_API_KEY=sk-your-key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
SENTINEL_LLM_MODEL=qwen3.6-plus
SENTINEL_LLM_ENABLE_THINKING=0
SENTINEL_LLM_TIMEOUT_SEC=90
```

```bash
sudo systemctl restart sentinel-langgraph
sudo systemctl is-active sentinel-langgraph
```

Inspect 时加 **`--llm`**（等价 `inspect.use_llm=true`）：

```bash
python scripts/inspect_langgraph_live_demo.py \
  --thread-only \
  --llm \
  --cluster-id k3s-prod \
  --namespace kube-system \
  --pod-name <coredns-pod> \
  --thread-id "$LANGGRAPH_THREAD_ID"
```

成功：`narrative_source=llm`；失败回退 `template` 且可能有 `llm_error`。详见 [LLM-NARRATIVE.md](LLM-NARRATIVE.md)。

---

## 验收检查表（W2 完成标准）

在任一路径（建议 Path B 必做）确认：

- [ ] `langgraph_live_verify.py` 全部 OK  
- [ ] `payload_mode=thread_only`  
- [ ] **`diagnosis`**：`issues`、`recommended_actions`、`diagnosis_source=rules_v1` 符合场景  
- [ ] **`execution`**：`execution_source=registry_v1`，`dry_run=true`，`actions_taken` 与推荐动作一致且 `status=simulated`  
- [ ] **`narrative`**：有 `summary`；`narrative_source` 为 `template` 或（可选）`llm`  
- [ ] **gather**（调试时可看 stream 或加打印）：`pod_status.found=true`，`events_for_pod` / `inspections_for_pod` 有结构  
- [ ] 脚本 **exit 0**（Path B CrashLoop 场景）  
- [ ] 未设置 `SENTINEL_EXECUTE_LIVE=1`（无 live 写集群）

**ROADMAP W2 勾选**：W2-1 目标 Pod、W2-2 inspect live、W2-3 dry-run execution、W2-4（可选）LLM、W2-5 本文档。

---

## 运维命令

| 操作 | 命令 |
|------|------|
| 连通性验证 | `python scripts/langgraph_live_verify.py` |
| inspect（live thread） | `LANGGRAPH_RUN_LIVE=1 python scripts/inspect_langgraph_live_demo.py --thread-only ...` |
| 立即 sync | `sudo /usr/local/bin/sentinel-sync-k8s.sh` |
| 重启 LangGraph | `sudo systemctl restart sentinel-langgraph` |
| 查 LangGraph 日志 | `sudo journalctl -u sentinel-langgraph -n 50 --no-pager` |
| list_pods | `python scripts/query_demo.py --live`（需 `LANGGRAPH_RUN_LIVE=1`） |

---

## 常见问题

### `Set LANGGRAPH_RUN_LIVE=1`

未 export 该变量。不要寻找 `--live` 参数；正确写法：

```bash
export LANGGRAPH_RUN_LIVE=1
export LANGGRAPH_API_URL=http://127.0.0.1:2024
```

### `LangGraph request failed` / connection refused

```bash
sudo systemctl status sentinel-langgraph
curl -s http://127.0.0.1:2024/ok
```

见 [DEPLOY-LANGGRAPH-SYSTEMD.md](DEPLOY-LANGGRAPH-SYSTEMD.md)。

### `WARN: no diagnosis issues`（exit 1）

- Pod 在图中 **不存在** 或 **名字错误**：`kubectl get pod -n kube-system` 与 `--pod-name` 完全一致。  
- **未 sync**：先跑 `mcp_k8s_sync_live.py` 或 cron。  
- Pod 真正健康：改测 Path B `sentinel-crash-test`，或选有 Warning Event 的 coredns。  
- 用了 mock 路径：live 必须加 **`--thread-only`**。

### `pod_status.found` 为 false / gather 空

- `cluster_id` / `namespace` 与 sync 不一致（应为 `k3s-prod` + `kube-system`）。  
- **thread_id 错误**：必须与 sync 使用的 checkpoint 一致（上表 UUID）。  
- LangGraph **重启后** thread 内存清空：跑一次 sync 再 inspect。

### `execution policy error` / `ok: false`

检查 `diagnosis` 是否完整；`recommended_actions` 是否为空。Policy 拒绝时会写在 `execution.error`。

### Path B 无 `CrashLoop`

- 等待 Pod 进入 `CrashLoopBackOff`：`kubectl describe pod -n kube-system sentinel-crash-test`。  
- sync 后再 inspect；确认 `events_for_pod` 在 gather 中有 BackOff 相关 Event。  
- 确认 inspect 的 namespace 与 Pod 一致。

### LLM 仍为 `template`

- `.env` 在 **langgraph-server** 目录，且 **systemd 已 restart**。  
- 客户端 shell 的 key **不会**传给服务端。  
- 见 [LLM-NARRATIVE.md](LLM-NARRATIVE.md) 网络 smoke。

### 与 W1 相同：CRLF / MCP / cron

- `bash\r`：`sed -i 's/\r$//'` 相关脚本。  
- MCP kubeconfig： [DEPLOY-MCP-KUBECONFIG.md](DEPLOY-MCP-KUBECONFIG.md)。  
- cron 不跑： [DEPLOY-SYNC-CRON.md](DEPLOY-SYNC-CRON.md)。

---

## 文件清单

| 文件 | 作用 |
|------|------|
| [`agents/langgraph-integration/scripts/inspect_langgraph_live_demo.py`](../agents/langgraph-integration/scripts/inspect_langgraph_live_demo.py) | W2 主验收脚本 |
| [`agents/langgraph-integration/scripts/langgraph_live_verify.py`](../agents/langgraph-integration/scripts/langgraph_live_verify.py) | 连通性 + mock inspect 自检 |
| [`agents/langgraph-server/src/graph.py`](../agents/langgraph-server/src/graph.py) | inspect 图节点顺序 |
| [`agents/langgraph-integration/src/agent/diagnose.py`](../agents/langgraph-integration/src/agent/diagnose.py) | 规则诊断（CrashLoop / WarningEvents） |
| [`docs/DEPLOY-LANGGRAPH-SYSTEMD.md`](DEPLOY-LANGGRAPH-SYSTEMD.md) | W1-2 |
| [`docs/DEPLOY-SYNC-CRON.md`](DEPLOY-SYNC-CRON.md) | W1-3 |
| [`docs/DEPLOY-MCP-KUBECONFIG.md`](DEPLOY-MCP-KUBECONFIG.md) | W1-4 |
| [`docs/LLM-NARRATIVE.md`](LLM-NARRATIVE.md) | W2-4 LLM |
| [`docs/ROADMAP.md`](ROADMAP.md) | 总纲 W2 |

---

## 相关 ROADMAP 条目

- **W2-1**：Path A（coredns）或 Path B（`sentinel-crash-test`）  
- **W2-2**：`LANGGRAPH_RUN_LIVE=1` + `--thread-only` inspect  
- **W2-3**：Path B `restart_pod` simulated dry-run  
- **W2-4**：可选 `--llm`  
- **W2-5**：本文档 + 周总结回链
