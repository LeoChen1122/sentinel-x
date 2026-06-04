# Deploy templates (Sentinel-X server)

**P0 one-shot:** [docs/DEPLOY-ONE-SHOT.md](../docs/DEPLOY-ONE-SHOT.md) — `sudo bash deploy/install-sentinel-x.sh`  
**Canonical reference:** [docs/DEPLOY-REFERENCE.md](../docs/DEPLOY-REFERENCE.md) — params, env index, verify  
**Master index:** [docs/DEPLOY-SERVER.md](../docs/DEPLOY-SERVER.md) — full server setup order (k3s → MCP → LangGraph → sync → Prom → UI).

| File | Install |
|------|---------|
| [`install-sentinel-x.sh`](install-sentinel-x.sh) | `sudo bash deploy/install-sentinel-x.sh` (venv, MCP, systemd, cron, first sync) |
| [`sentinel-config-discover.sh`](sentinel-config-discover.sh) | `sudo bash deploy/sentinel-config-discover.sh [--write]` |
| [`sentinel-config-apply.sh`](sentinel-config-apply.sh) | `sudo bash deploy/sentinel-config-apply.sh [--discover] [--reload]` |
| [`lib/config-common.sh`](lib/config-common.sh) | sourced by discover/apply (do not run directly) |
| [`sentinel-langgraph-post-restart.sh`](sentinel-langgraph-post-restart.sh) | `ExecStartPost` in sentinel-langgraph.service |
| [`verify-sentinel-x.sh`](verify-sentinel-x.sh) | `sudo bash deploy/verify-sentinel-x.sh [--after-restart]` |
| [`sentinel-x.env.example`](sentinel-x.env.example) | master env → `/etc/sentinel/sentinel-x.env` |
| [`sentinel-langgraph.service`](sentinel-langgraph.service) | `sudo cp deploy/sentinel-langgraph.service /etc/systemd/system/` |
| [`sync-k8s.sh`](sync-k8s.sh) | `sudo install -m 755 deploy/sync-k8s.sh /usr/local/bin/sentinel-sync-k8s.sh` |
| [`sync-k8s.env.example`](sync-k8s.env.example) | **generated** by apply → `/etc/sentinel/sync-k8s.env` |
| [`cron-sentinel-sync.example`](cron-sentinel-sync.example) | `sudo cp deploy/cron-sentinel-sync.example /etc/cron.d/sentinel-sync` |
| [`sync-kubeconfig-for-mcp.sh`](sync-kubeconfig-for-mcp.sh) | `sudo install -m 755 … /usr/local/bin/sentinel-sync-kubeconfig.sh` + `sed -i 's/\r$//'` |
| [`sync-prom.sh`](sync-prom.sh) | `sudo install -m 755 deploy/sync-prom.sh /usr/local/bin/sentinel-sync-prom.sh` |
| [`sync-prom.env.example`](sync-prom.env.example) | **generated** by apply → `/etc/sentinel/sync-prom.env` |
| [`sentinel-ui.service`](sentinel-ui.service) | `sudo cp deploy/sentinel-ui.service /etc/systemd/system/` |
| [`sentinel-ui.env.example`](sentinel-ui.env.example) | **generated** by apply → `/etc/sentinel/sentinel-ui.env` |
| [`kube-prometheus-values-minimal.yaml`](kube-prometheus-values-minimal.yaml) | values for offline kube-prometheus-stack (NodePort 30909) |
| [`install-kube-prometheus-offline.sh`](install-kube-prometheus-offline.sh) | **canonical** server install script (`dist/` copy only) |
| [`install-deploy-scripts.sh`](install-deploy-scripts.sh) | `sudo bash deploy/install-deploy-scripts.sh` (install all + strip CRLF) |

| Doc | Topic |
|-----|-------|
| [`docs/DEPLOY-REFERENCE.md`](../docs/DEPLOY-REFERENCE.md) | **canonical** params, checkpoint, env, verify |
| [`docs/DEPLOY-SERVER.md`](../docs/DEPLOY-SERVER.md) | **W4** Master deploy index |
| [`docs/ARCHITECTURE-REVIEW.md`](../docs/ARCHITECTURE-REVIEW.md) | Architecture review |
| [`docs/DEPLOY-LANGGRAPH-SYSTEMD.md`](../docs/DEPLOY-LANGGRAPH-SYSTEMD.md) | W1-2 LangGraph systemd |
| [`docs/DEPLOY-SYNC-CRON.md`](../docs/DEPLOY-SYNC-CRON.md) | W1-3 cron incremental sync |
| [`docs/DEPLOY-MCP-KUBECONFIG.md`](../docs/DEPLOY-MCP-KUBECONFIG.md) | W1-4 MCP kubeconfig + compose |
| [`docs/DEPLOY-INSPECT-LIVE.md`](../docs/DEPLOY-INSPECT-LIVE.md) | W2 Live inspect + diagnosis E2E |
| [`docs/DEPLOY-PROMETHEUS-K3S.md`](../docs/DEPLOY-PROMETHEUS-K3S.md) | W3 前置：离线 kube-prometheus-stack |
| [`docs/DEPLOY-PROM-SYNC.md`](../docs/DEPLOY-PROM-SYNC.md) | W3 Prometheus metrics → LangGraph |
| [`docs/DEPLOY-UI-LIVE.md`](../docs/DEPLOY-UI-LIVE.md) | W4 Streamlit UI 服务器部署 |
