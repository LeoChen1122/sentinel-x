# Sentinel-X ?????canonical?

> ??? env ? [`sentinel-config-apply.sh`](../../deploy/config/sentinel-config-apply.sh) ? **`/etc/sentinel/sentinel-x.env`** ???  
> ????? **[DEPLOY-ONE-SHOT.md](DEPLOY-ONE-SHOT.md)**?

---

## ??????

| ?? | ?? | ?? |
|------|------|------|
| `SENTINEL_ROOT` | `/opt/sentinel-x` | `sentinel-x.env` |
| `CLUSTER_ID` | `k3s-prod` | ?? / ?? |
| `NAMESPACE` | `kube-system` | ?? / ?? |
| `LANGGRAPH_API_URL` | `http://127.0.0.1:2024` | ?? |
| `LANGGRAPH_THREAD_ID` | `uuid5("default:{CLUSTER_ID}")` | **AUTO** |

---

## Skills?W5?

| ?? | ?? | ?? |
|------|------|------|
| `SENTINEL_SKILLS_DIR` | `{SENTINEL_ROOT}/skills` | Markdown ??? |
| `SENTINEL_SKILLS_DB` | `{SENTINEL_SKILLS_DIR}/.index/skills.db` | SQLite FTS |
| `SENTINEL_SKILLS_RECORD` | `1` | `0` ?? record ?? |
| `SENTINEL_SKILLS_SEARCH_LIMIT` | `3` | retrieve ?? |

???`/etc/sentinel/sentinel-langgraph.env`?LangGraph systemd?

---

## Sandbox?W6?

| ?? | ?? | ?? |
|------|------|------|
| `SENTINEL_SANDBOX_ENABLED` | `1` | `0` ?????? |
| `SENTINEL_SANDBOX_NAMESPACE` | `sentinel-sandbox` | ???? kubectl ?? ns |
| `SENTINEL_SANDBOX_AUDIT_DIR` | `{SENTINEL_ROOT}/sandbox/audit` | ?? `audit-YYYY-MM.jsonl` |
| `SENTINEL_SANDBOX_IMAGE` | `sentinel-x-sandbox:latest` | `install --with-sandbox` ?? |
| `SENTINEL_SANDBOX_TIMEOUT_SEC` | `60` | ?????? |
| `SENTINEL_SANDBOX_MAX_REPLICAS` | `5` | scale_up ?? |
| `SENTINEL_SANDBOX_READY_SEC` | `30` | Ready ?? N ?? verified |
| `SENTINEL_EXECUTE_LIVE` | ??? | `1` = ?? K8s ??**???**?W8+? |

Fixture?`install-sentinel-x.sh --with-fixtures` ? `kubectl apply -f sandbox/fixtures/crash-loop-deployment.yaml`

---

## Patrol / API?W7?

| ?? | ?? | ?? |
|------|------|------|
| `SENTINEL_PATROL_ENABLED` | `1` | `0` ?? patrol |
| `SENTINEL_PATROL_COOLDOWN_SEC` | `3600` | ? Pod re-inspect ?? |
| `SENTINEL_PATROL_STATE_PATH` | `/var/lib/sentinel/inspect-patrol-state.json` | cooldown ?? |
| `SENTINEL_PATROL_DRY_RUN` | `true` | patrol ?? simulated |
| `SENTINEL_PATROL_LOG` | `/var/log/sentinel-patrol.log` | patrol ?? |
| `SENTINEL_API_TOKEN` | ? | API Bearer??=????? localhost? |
| `SENTINEL_API_HOST` | `127.0.0.1:8080` | FastAPI bind |

???`sync-k8s.env`?patrol??`sentinel-api.env`?API?

?? [DEPLOY-ALERT-INSPECT.md](DEPLOY-ALERT-INSPECT.md)

---

## Checkpoint ??

LangGraph ?? **?? checkpoint**????? sync ???????? [ROADMAP.md](../ROADMAP.md) W8+?

---

## ??

```bash
# W1?W4 ??
sudo bash /opt/sentinel-x/deploy/verify/verify-sentinel-x.sh

# W5?W7 ??
sudo bash /opt/sentinel-x/deploy/verify/verify-sentinel-x.sh --full
```

---

## ????

| ?? | ?? |
|------|------|
| [DEPLOY-ONE-SHOT.md](DEPLOY-ONE-SHOT.md) | ???? W1?W7 |
| [DEPLOY-SERVER.md](DEPLOY-SERVER.md) | ???? |
