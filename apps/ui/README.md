# Sentinel-X Streamlit UI (W4)

Minimal browser UI for live pod list, top CPU, and inspect results against a LangGraph thread checkpoint.

**服务器完整步骤** → **[docs/DEPLOY-UI-LIVE.md](../../docs/DEPLOY-UI-LIVE.md)**

## Prerequisites

- LangGraph server running (`sentinel-langgraph.service`)
- K8s sync has populated the thread ([DEPLOY-SERVER.md](../../docs/DEPLOY-SERVER.md))
- Optional: Prom sync for CPU/memory columns (W3)

## Local run

From repo root:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r apps/ui/requirements.txt
pip install -r agents/langgraph-integration/requirements.txt

export LANGGRAPH_RUN_LIVE=1
export LANGGRAPH_API_URL=http://127.0.0.1:2024
export LANGGRAPH_THREAD_ID=5ad00ee0-6f4d-5cd6-a021-99469a86e4e1
export CLUSTER_ID=k3s-prod
export NAMESPACE=kube-system

streamlit run apps/ui/app.py
```

Open http://localhost:8501

## Server run (summary)

See [DEPLOY-UI-LIVE.md](../../docs/DEPLOY-UI-LIVE.md) for scp, deps, acceptance.

```bash
source /opt/sentinel-x/.venv/bin/activate
export LANGGRAPH_RUN_LIVE=1
export LANGGRAPH_API_URL=http://127.0.0.1:2024
streamlit run /opt/sentinel-x/apps/ui/app.py --server.address 127.0.0.1 --server.port 8501
```

From laptop: `ssh -L 8501:127.0.0.1:8501 root@<server>` → http://127.0.0.1:8501

Optional systemd: `deploy/sentinel-ui.service` + `/etc/sentinel/sentinel-ui.env`

Sidebar fields override env defaults without restarting.

## Offline

If LangGraph is down or `LANGGRAPH_RUN_LIVE` is unset, the page shows a warning instead of failing silently.
