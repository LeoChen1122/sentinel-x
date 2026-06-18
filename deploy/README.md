# Deploy templates (Sentinel-X server)

**P0 one-shot:** [docs/deploy/DEPLOY-ONE-SHOT.md](../docs/deploy/DEPLOY-ONE-SHOT.md) — `sudo bash deploy/install/install-sentinel-x.sh`  
**Canonical reference:** [docs/deploy/DEPLOY-REFERENCE.md](../docs/deploy/DEPLOY-REFERENCE.md)  
**Master index:** [docs/deploy/DEPLOY-SERVER.md](../docs/deploy/DEPLOY-SERVER.md)

## Layout

```text
deploy/
├── README.md
├── install/                           # one-shot installer
├── config/                            # SSOT env + discover/apply
├── sync/                              # cron sync scripts
├── systemd/                           # unit files + post-restart hook
├── prometheus/                        # kube-prometheus offline install
└── verify/                            # post-install smoke tests
```

---

## install/

| File | Usage |
|------|-------|
| [`install/install-sentinel-x.sh`](install/install-sentinel-x.sh) | `sudo bash deploy/install/install-sentinel-x.sh [--with-ui --with-api --with-sandbox --with-fixtures]` |
| [`install/install-deploy-scripts.sh`](install/install-deploy-scripts.sh) | `sudo bash deploy/install/install-deploy-scripts.sh` |
| [`install/reset-sentinel-x.sh`](install/reset-sentinel-x.sh) | `sudo bash deploy/install/reset-sentinel-x.sh [--yes]` — wipe Sentinel-X, keep k3s |

## config/

| File | Usage |
|------|-------|
| [`config/sentinel-config-discover.sh`](config/sentinel-config-discover.sh) | `sudo bash deploy/config/sentinel-config-discover.sh [--write]` |
| [`config/sentinel-config-apply.sh`](config/sentinel-config-apply.sh) | `sudo bash deploy/config/sentinel-config-apply.sh [--discover] [--reload]` |
| [`config/sentinel-x.env.example`](config/sentinel-x.env.example) | master env → `/etc/sentinel/sentinel-x.env` |
| [`config/sync-k8s.env.example`](config/sync-k8s.env.example) | **generated** → `/etc/sentinel/sync-k8s.env` |
| [`config/sync-prom.env.example`](config/sync-prom.env.example) | **generated** → `/etc/sentinel/sync-prom.env` |
| [`config/sentinel-ui.env.example`](config/sentinel-ui.env.example) | **generated** → `/etc/sentinel/sentinel-ui.env` |
| [`config/lib/config-common.sh`](config/lib/config-common.sh) | shared helpers (sourced) |
| [`config/lib/paths.sh`](config/lib/paths.sh) | deploy subdir paths (sourced) |

## sync/

| File | Installed to |
|------|--------------|
| [`sync/sync-k8s.sh`](sync/sync-k8s.sh) | `/usr/local/bin/sentinel-sync-k8s.sh` |
| [`sync/sync-prom.sh`](sync/sync-prom.sh) | `/usr/local/bin/sentinel-sync-prom.sh` |
| [`sync/sync-kubeconfig-for-mcp.sh`](sync/sync-kubeconfig-for-mcp.sh) | `/usr/local/bin/sentinel-sync-kubeconfig.sh` |
| [`sync/sentinel-inspect-patrol.sh`](sync/sentinel-inspect-patrol.sh) | `/usr/local/bin/sentinel-inspect-patrol.sh` |
| [`sync/cron-sentinel-sync.example`](sync/cron-sentinel-sync.example) | `/etc/cron.d/sentinel-sync` (K8s sync + patrol) |

## systemd/

| File | Usage |
|------|-------|
| [`systemd/sentinel-langgraph.service`](systemd/sentinel-langgraph.service) | `sudo cp deploy/systemd/sentinel-langgraph.service /etc/systemd/system/` |
| [`systemd/sentinel-ui.service`](systemd/sentinel-ui.service) | optional UI unit |
| [`systemd/sentinel-langgraph-post-restart.sh`](systemd/sentinel-langgraph-post-restart.sh) | `ExecStartPost` hook |

## prometheus/

| File | Usage |
|------|-------|
| [`prometheus/install-kube-prometheus-offline.sh`](prometheus/install-kube-prometheus-offline.sh) | **canonical** (dist/ is copy-only) |
| [`prometheus/kube-prometheus-values-minimal.yaml`](prometheus/kube-prometheus-values-minimal.yaml) | NodePort 30909 values |
| [`prometheus/sentinel-alertmanager-receiver.example.yaml`](prometheus/sentinel-alertmanager-receiver.example.yaml) | Alertmanager → Sentinel webhook (Helm values) |
| [`prometheus/sentinel-crashloop-prometheusrule.example.yaml`](prometheus/sentinel-crashloop-prometheusrule.example.yaml) | CrashLoopBackOff PrometheusRule |
| [`prometheus/prepare-kube-prometheus-offline.ps1`](prometheus/prepare-kube-prometheus-offline.ps1) | Windows offline bundle prep |

## verify/

| File | Usage |
|------|-------|
| [`verify/verify-sentinel-x.sh`](verify/verify-sentinel-x.sh) | `sudo bash deploy/verify/verify-sentinel-x.sh [--full] [--after-restart]` |

---

## Upgrade from wrapper layout

After scp of the new repo (servers that used root-level wrapper scripts):

```bash
find /opt/sentinel-x/deploy -name '*.sh' -exec sed -i 's/\r$//' {} +
sudo bash /opt/sentinel-x/deploy/install/install-deploy-scripts.sh
sudo cp /opt/sentinel-x/deploy/systemd/sentinel-langgraph.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart sentinel-langgraph
sudo bash /opt/sentinel-x/deploy/verify/verify-sentinel-x.sh --after-restart
```

If MCP compose moved to `mcp-servers/compose/`, run `docker compose up -d` from that directory.

---

## Docs

| Doc | Topic |
|-----|-------|
| [DEPLOY-REFERENCE.md](../docs/deploy/DEPLOY-REFERENCE.md) | canonical params, checkpoint, env |
| [DEPLOY-ONE-SHOT.md](../docs/deploy/DEPLOY-ONE-SHOT.md) | one-command install |
| [DEPLOY-SERVER.md](../docs/deploy/DEPLOY-SERVER.md) | step-by-step index |
