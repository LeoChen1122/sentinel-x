# GitHub Issues — Project Backlog Import

Create each item as a **New issue**, then drag to the Project column indicated.

Labels suggested: `enhancement`, `ops`, `agent`, `sandbox`, `docs`.

---

## Done (move to Done column — historical)

| Title | Body summary |
|-------|----------------|
| W1–W2 K8s MCP + LangGraph sync | Live sync, list_pods — see [W22](../weekly/2026-W22.md) |
| W3 Prometheus MCP + metrics | top_pods_by_cpu live — [W23](../weekly/2026-W23.md) |
| W4 Streamlit UI | :8501 minimal dashboard |
| W5 Skills FTS | skills/ + retrieve_skills node |
| W6 Sandbox dry-run | Docker executor, sentinel-sandbox only |
| W7 Patrol + inspect trigger | cron patrol, cooldown — [W26](../weekly/2026-W26.md) |
| P0 one-shot install | install-sentinel-x.sh + verify --full — [W25](../weekly/2026-W25.md) |
| POST /v1/inspect live | API inspect + Bearer token — DEPLOY-ALERT-INSPECT |

---

## Doing

| Title | Body |
|-------|------|
| Alertmanager webhook live | Wire Prom alert → `/v1/webhooks/alertmanager` → trigger_inspect; doc DEPLOY-ALERTMANAGER-WEBHOOK |
| SQLite LangGraph checkpoint | SqliteSaver in graph.py; acceptance: same thread inspect context after restart |

---

## Backlog

| Title | Body |
|-------|------|
| Sandbox Runtime hardening | gVisor or stronger isolation; expand policy tests |
| Skills E2E | End-to-end test: diagnose → record_skill → FTS retrieve on second inspect |
| Alert Auto Close production | `SENTINEL_EXECUTE_LIVE=1` gated writes beyond sandbox |
| Knowledge Base backend | Chroma / embedding backend access alongside FTS |
| Agent Memory | Long-horizon memory across threads / tenants |
| Multi Cluster live | `configs/clusters.yaml` + per-cluster thread routing |
| Slack Integration | Notify on inspect complete / sandbox result |
| Grafana Dashboard | Sentinel-X ops dashboard for patrol + graph health |
| pip install -e packaging | pyproject.toml; reduce sys.path hacks |
| Root docker-compose.yml | Unified local dev compose at repo root |
| LLM narrative default | DashScope / OpenAI with timeout fallback |
| Demo GIF / screenshots | docs/assets/demo for README |

---

## Review (optional column)

Use for PRs awaiting review — link PR in issue body.

Example: `feat(api): extend verify --full for webhook smoke test`

---

## Bulk create tip

1. Create issues from **Backlog** table first (fastest impact on board counts)
2. Mark **Done** items closed immediately so board shows velocity
3. Pin **Doing** items (max 2–3) for credible "active project" signal
