# GitHub Issues — Project Backlog Import / Issue 看板导入

Create each row as **New issue**, then drag to the Project column.  
每一行在 GitHub **New issue** 创建，再拖入看板对应列。

**Labels | 建议标签:** `enhancement` · `ops` · `agent` · `sandbox` · `docs`

---

## Done | 已完成

Move to **Done** column, then **Close issue**.  
拖入 **Done** 列后 **Close issue**（历史已完成，共 8 条）。

| Title | 中文 | Body (paste as issue description) | 正文（中文参考） |
|-------|------|-----------------------------------|------------------|
| W1–W2 K8s MCP + LangGraph sync | K8s MCP 与 LangGraph 同步 | Live sync, list_pods — see [W22](../weekly/2026-W22.md) | 生产 sync、list_pods — [W22](../weekly/2026-W22.md) |
| W3 Prometheus MCP + metrics | Prometheus MCP 与指标 | top_pods_by_cpu live — [W23](../weekly/2026-W23.md) | 指标进图 — [W23](../weekly/2026-W23.md) |
| W4 Streamlit UI | Streamlit 界面 | :8501 minimal dashboard | 最小仪表盘 :8501 |
| W5 Skills FTS | Skills 全文检索 | skills/ + retrieve_skills node | skills/ + retrieve_skills 节点 |
| W6 Sandbox dry-run | 沙箱预演 | Docker executor, sentinel-sandbox only | Docker 执行器，仅 sentinel-sandbox |
| W7 Patrol + inspect trigger | 巡检与 inspect 触发 | cron patrol, cooldown — [W26](../weekly/2026-W26.md) | cron 巡检 + cooldown — [W26](../weekly/2026-W26.md) |
| P0 one-shot install | P0 一键部署 | install-sentinel-x.sh + verify --full — [W25](../weekly/2026-W25.md) | 一键安装 + verify — [W25](../weekly/2026-W25.md) |
| POST /v1/inspect live | API inspect 上线 | API inspect + Bearer token — [DEPLOY-ALERT-INSPECT](../deploy/DEPLOY-ALERT-INSPECT.md) | Bearer 鉴权 + live curl |

---

## Doing | 进行中

Keep **Open** in **Doing** (max 2–3).  
保持 **Open**，拖入 **Doing**（建议 2–3 项）。

| Title | 中文 | Body | 正文（中文参考） |
|-------|------|------|------------------|
| Alertmanager webhook live | Alertmanager Webhook 上线 | Wire Prom alert → `/v1/webhooks/alertmanager` → trigger_inspect; doc DEPLOY-ALERTMANAGER-WEBHOOK | Prom 告警 → webhook → trigger_inspect |
| SQLite LangGraph checkpoint | SQLite 检查点持久化 | SqliteSaver in graph.py; acceptance: same thread inspect context after restart | graph.py 接 SqliteSaver；restart 后同 thread 上下文可恢复 |

---

## Backlog | 待办

Drag to **Backlog**, keep **Open**.  
拖入 **Backlog**，保持 **Open**（共 12 条）。

| Title | 中文 | Body | 正文（中文参考） |
|-------|------|------|------------------|
| Sandbox Runtime hardening | 沙箱运行时加固 | gVisor or stronger isolation; expand policy tests | gVisor 或更强隔离；扩展策略测试 |
| Skills E2E | Skills 端到端测试 | End-to-end: diagnose → record_skill → FTS retrieve on second inspect | 诊断 → 记 Skill → 二次 inspect 检索 |
| Alert Auto Close production | 生产环境自动闭环 | `SENTINEL_EXECUTE_LIVE=1` gated writes beyond sandbox | 沙箱外生产写，显式门控 |
| Knowledge Base backend | 知识库后端 | Chroma / embedding backend alongside FTS | Chroma / embedding 与 FTS 并存 |
| Agent Memory | Agent 长期记忆 | Long-horizon memory across threads / tenants | 跨 thread / 租户记忆 |
| Multi Cluster live | 多集群 live | `configs/clusters.yaml` + per-cluster thread routing | 多集群配置与 thread 路由 |
| Slack Integration | Slack 集成 | Notify on inspect complete / sandbox result | inspect / 沙箱结果通知 |
| Grafana Dashboard | Grafana 仪表盘 | Sentinel-X ops dashboard for patrol + graph health | 巡检与图健康仪表盘 |
| pip install -e packaging | 可编辑安装打包 | pyproject.toml; reduce sys.path hacks | pyproject.toml；减少 sys.path |
| Root docker-compose.yml | 根目录 compose | Unified local dev compose at repo root | 统一本地开发 compose |
| LLM narrative default | LLM 叙事默认开启 | DashScope / OpenAI with timeout fallback | DashScope / OpenAI + 超时回退 |
| Demo GIF / screenshots | Demo 截图/GIF | docs/assets/demo for README | README Demo 区素材 |

---

## Review | 评审（可选列）

For PRs awaiting review — link PR in issue body.  
PR 待 review 时使用 — 正文贴 PR 链接。

Example | 示例: `feat(api): extend verify --full for webhook smoke test`

---

## Bulk create tips | 批量创建技巧

1. **Backlog** first — fastest way to fill the board / 先建 Backlog，看板最快丰满  
2. **Done** items → close immediately / Done 项立即关闭  
3. **Doing** → max 2–3 for a focused “active project” signal / Doing 不超过 2–3 项  
4. See bilingual guide: [README.md](README.md)
