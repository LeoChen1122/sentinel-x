# Sentinel-X ?????canonical?

> ??????????????? **??????**?  
> ????DEPLOY-SYNC-CRON?DEPLOY-PROM-SYNC ???????????????

---

## ??????

| ?? | ??? | ?? |
|------|--------|------|
| `SENTINEL_ROOT` | `/opt/sentinel-x` | `sentinel-x.env` |
| `CLUSTER_ID` | `k3s-prod` | ?? / ?? |
| `NAMESPACE` | `kube-system` | ?? / ?? |
| `LANGGRAPH_API_URL` | `http://127.0.0.1:2024` | ?? |
| `LANGGRAPH_THREAD_ID` | `uuid5("default:{CLUSTER_ID}")` | **AUTO** ?? |
| `MCP_K8S_CONTAINER` | docker ?? | **AUTO** |
| `MCP_PROM_CONTAINER` | docker ?? | **AUTO** |
| `PROMETHEUS_BASE_URL` | `http://host.docker.internal:{port}` | **AUTO** ?? NodePort |
| Streamlit | `http://127.0.0.1:8501` | SSH ?? |

---

## Skills ???W5?

| ?? | ?? | ?? |
|------|------|------|
| `SENTINEL_SKILLS_DIR` | `{SENTINEL_ROOT}/skills` | Markdown ????? |
| `SENTINEL_SKILLS_DB` | `{SENTINEL_SKILLS_DIR}/.index/skills.db` | SQLite FTS ?? |
| `SENTINEL_SKILLS_RECORD` | `1` | `0` ?? inspect ????? |
| `SENTINEL_SKILLS_SEARCH_LIMIT` | `3` | ?????? |

?? [`skills/README.md`](../../skills/README.md)?

---

## Checkpoint ??

LangGraph ?? **`langgraph dev` ?? checkpoint**?? Postgres??

1. `systemctl restart sentinel-langgraph` ? **thread ?????**?
2. **????**?
   - `ExecStartPost` ? [`deploy/systemd/sentinel-langgraph-post-restart.sh`](../deploy/systemd/sentinel-langgraph-post-restart.sh) ?? K8s?+ Prom?sync
   - ??? cron??5 ???
   - ????`sudo /usr/local/bin/sentinel-sync-k8s.sh`
3. **??**?`sudo bash deploy/verify/verify-sentinel-x.sh` ? `list_pods count >= 1`

**Phase 2?W5+ ??**??? Postgres/SQLite ??? checkpoint ? ? [ROADMAP.md](../ROADMAP.md) W8+?

---

## ??????

| ?? | AUTO | ?? | ???? | ??? |
|------|------|------|----------|--------|
| `CLUSTER_ID` | | ?? | `sentinel-x.env` | sync, query, UI |
| `NAMESPACE` | | ?? | `sentinel-x.env` | sync, query, UI |
| `LANGGRAPH_THREAD_ID` | yes | ??? | master ? ? env | sync, query, UI |
| `MCP_K8S_CONTAINER` | yes | ??? | master ? sync-k8s | sync-k8s.sh |
| `MCP_PROM_CONTAINER` | yes | ??? | master ? sync-prom | sync-prom.sh |
| `PROMETHEUS_BASE_URL` | yes | ??? | master ? mcp-servers/compose/.env | MCP Prom |
| `LANGGRAPH_API_URL` | | ?? | master | ?? |
| LLM API keys | | **??** | `langgraph-server/.env` | narrative LLM |

### ?????

```bash
# ???????????? + AUTO ???
sudo nano /etc/sentinel/sentinel-x.env

# ?? + ????? env
sudo bash /opt/sentinel-x/deploy/config/sentinel-config-discover.sh --write
sudo bash /opt/sentinel-x/deploy/config/sentinel-config-apply.sh --with-prom-sync --with-ui

# ???????
sudo bash deploy/config/sentinel-config-discover.sh --write
sudo bash deploy/config/sentinel-config-apply.sh --discover --reload
```

**? env ?????**??????`/etc/sentinel/sync-k8s.env`?`sync-prom.env`?`sentinel-ui.env`?

---

## ??????

```bash
sudo bash /opt/sentinel-x/deploy/verify/verify-sentinel-x.sh
```

LangGraph ???????????

```bash
sudo bash /opt/sentinel-x/deploy/verify/verify-sentinel-x.sh --after-restart
```

???

```text
[verify] OK: curl http://127.0.0.1:2024/ok
[verify] OK: MCP returned N pods
[verify] OK: list_pods count=N
[verify] OK: sentinel-langgraph active
[verify] All checks passed.
```

---

## ??????

? [DEPLOY-ONE-SHOT.md](DEPLOY-ONE-SHOT.md)?

---

## ????

| ?? | ?? |
|------|------|
| [DEPLOY-ONE-SHOT.md](DEPLOY-ONE-SHOT.md) | ?????? |
| [DEPLOY-SERVER.md](DEPLOY-SERVER.md) | ??? |
| [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) | ???? |
