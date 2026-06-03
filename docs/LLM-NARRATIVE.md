# LLM 叙事（Qwen / DashScope）

LLM 在 **LangGraph `narrate` 节点**内调用，环境变量必须配置在 **`agents/langgraph-server/.env`**，并 **重启 `langgraph dev`**。

Inspect 客户端 shell 里的 `DASHSCOPE_API_KEY` **不会**自动传给服务端。

---

## 1. 配置 langgraph-server/.env

```bash
SENTINEL_LLM_ENABLED=1
DASHSCOPE_API_KEY=sk-your-key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
SENTINEL_LLM_MODEL=qwen3.6-plus
SENTINEL_LLM_ENABLE_THINKING=0
SENTINEL_LLM_TIMEOUT_SEC=90
```

仅 ASCII 行；Windows 开发机勿写中文注释（GBK 解码问题）。

---

## 2. 重启 langgraph dev

```bash
cd agents/langgraph-server
langgraph dev --host 127.0.0.1 --port 2024
```

---

## 3. 服务器网络自检

```bash
curl -sS -o /dev/null -w "%{http_code}\n" --connect-timeout 5 \
  https://dashscope.aliyuncs.com/compatible-mode/v1/models

cd agents/langgraph-integration
export SENTINEL_LLM_ENABLED=1 DASHSCOPE_API_KEY=sk-... \
  OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
python scripts/qwen_dashscope_smoke.py
```

smoke 通过后再跑 inspect。

---

## 4. Live inspect + LLM

```bash
export LANGGRAPH_RUN_LIVE=1
export LANGGRAPH_API_URL=http://127.0.0.1:2024

python scripts/inspect_langgraph_live_demo.py \
  --thread-only \
  --llm \
  --cluster-id k3s-prod \
  --namespace kube-system \
  --pod-name coredns-6648f7576f-kg9bh \
  --thread-id 5ad00ee0-6f4d-5cd6-a021-99469a86e4e1
```

- `--thread-only`：不灌 mock 图，用已 sync 的 thread 数据（推荐 live 场景）
- 首次 LLM 可能等待 **最多 `SENTINEL_LLM_TIMEOUT_SEC` 秒**，勿过早 Ctrl+C
- 成功：`narrative_source=llm`；失败回退 `template` 并带 `llm_error`

---

## 5. 卡住 / 超时排查

| 现象 | 处理 |
|------|------|
| 长时间无输出 | 看 **langgraph dev 终端** 日志；等满 timeout |
| `llm_error` connection timeout | 服务器出网/DNS；代理/firewall |
| 仍是 `template`、无 error | 服务端未配 key 或未重启 dev |
| `base_url_configured: false`（client） | 正常；服务端需设 `OPENAI_BASE_URL` |

---

## 6. 相关代码

- LLM 调用：`agents/langgraph-integration/src/agent/llm.py`
- 图节点：`agents/langgraph-server/src/graph.py` → `narrate`
- 触发：`payload.inspect.use_llm=true` 或 `--llm`
