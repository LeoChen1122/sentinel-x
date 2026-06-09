# Sentinel-X ?????canonical?

> ??????????????? **??????**?

---

## ??????

| ?? | ??? | ?? |
|------|--------|------|
| `SENTINEL_ROOT` | `/opt/sentinel-x` | `sentinel-x.env` |
| `CLUSTER_ID` | `k3s-prod` | ?? / ?? |
| `NAMESPACE` | `kube-system` | ?? / ?? |
| `LANGGRAPH_API_URL` | `http://127.0.0.1:2024` | ?? |
| `LANGGRAPH_THREAD_ID` | `uuid5("default:{CLUSTER_ID}")` | **AUTO** |

---

## Skills ???W5?

| ?? | ?? | ?? |
|------|------|------|
| `SENTINEL_SKILLS_DIR` | `{SENTINEL_ROOT}/skills` | Markdown ????? |
| `SENTINEL_SKILLS_DB` | `{SENTINEL_SKILLS_DIR}/.index/skills.db` | SQLite FTS |
| `SENTINEL_SKILLS_RECORD` | `1` | `0` ?????? |
| `SENTINEL_SKILLS_SEARCH_LIMIT` | `3` | ???? |

---

## Sandbox ???W6 / W6.1?

| ?? | ?? | ?? |
|------|------|------|
| `SENTINEL_SANDBOX_ENABLED` | `1` | `0` ?????? |
| `SENTINEL_SANDBOX_NAMESPACE` | `sentinel-sandbox` | ???? kubectl ??? ns |
| `SENTINEL_SANDBOX_AUDIT_DIR` | `{SENTINEL_ROOT}/sandbox/audit` | ?? `audit-YYYY-MM.jsonl` |
| `SENTINEL_SANDBOX_IMAGE` | `sentinel-x-sandbox:latest` | `docker build sandbox/` |
| `SENTINEL_SANDBOX_TIMEOUT_SEC` | `60` | ?????? |
| `SENTINEL_SANDBOX_MAX_REPLICAS` | `5` | scale_up ???? Deployment? |
| `SENTINEL_SANDBOX_READY_SEC` | `30` | Ready ?? N ?? `verified` |
| `SENTINEL_SANDBOX_VERIFY_POLL_SEC` | `5` | ?????? |
| `SENTINEL_SANDBOX_VERIFY_TIMEOUT_SEC` | `120` | ????? |
| `SENTINEL_SANDBOX_PAYLOAD_TRUNCATE` | `4096` | payload ? stdout/stderr ?? |
| `SENTINEL_EXECUTE_LIVE` | ??? | `1` = ??? K8s?**???**?W8+? |

Fixture?`kubectl apply -f sandbox/fixtures/crash-loop-deployment.yaml`  
?? [`sandbox/README.md`](../../sandbox/README.md)?

---

## Checkpoint ??

LangGraph ?? **?? checkpoint**????? sync ??????? [ROADMAP.md](../ROADMAP.md) W8+?

---

## ????

```bash
sudo bash /opt/sentinel-x/deploy/verify/verify-sentinel-x.sh
```

---

## ????

| ?? | ?? |
|------|------|
| [DEPLOY-ONE-SHOT.md](DEPLOY-ONE-SHOT.md) | ???? |
| [DEPLOY-SERVER.md](DEPLOY-SERVER.md) | ??? |
