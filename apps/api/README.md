# Sentinel-X API (W7)

FastAPI thin layer: receive alerts or manual POST → trigger LangGraph inspect.

## Run (dev)

```bash
source /opt/sentinel-x/.venv/bin/activate
pip install -r apps/api/requirements.txt
set -a && source /etc/sentinel/sentinel-api.env && set +a
export PYTHONPATH="/opt/sentinel-x/agents/langgraph-integration/src:/opt/sentinel-x/apps/api/src"
cd /opt/sentinel-x/apps/api
uvicorn main:app --host 127.0.0.1 --port 8080 --app-dir src
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| POST | `/v1/inspect` | Manual inspect trigger |
| POST | `/v1/webhooks/alertmanager` | Alertmanager webhook v4 |

## Example

```bash
curl -s -X POST http://127.0.0.1:8080/v1/inspect \
  -H "Content-Type: application/json" \
  -d '{"pod_name":"crash-demo-xxx","namespace":"sentinel-sandbox","dry_run":true}'
```

See [docs/deploy/DEPLOY-ALERT-INSPECT.md](../../docs/deploy/DEPLOY-ALERT-INSPECT.md).
