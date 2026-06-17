#!/usr/bin/env bash
# Sentinel-X one-shot server installer (offline-friendly: no GitHub).
# Run from scp'd repo on Linux as root:
#   sudo bash /opt/sentinel-x/deploy/install/install-sentinel-x.sh
#   sudo bash .../install/install-sentinel-x.sh --with-ui --with-prometheus
#
set -euo pipefail

ROOT="${SENTINEL_ROOT:-/opt/sentinel-x}"
# shellcheck source=../config/lib/paths.sh
. "${ROOT}/deploy/config/lib/paths.sh"
ENV_MASTER="${SENTINEL_X_ENV:-/etc/sentinel/sentinel-x.env}"

WITH_UI=0
WITH_API=0
WITH_PROMETHEUS=0
WITH_PROM_SYNC=0
WITH_SANDBOX=0
WITH_FIXTURES=0
WITH_PATROL=1
SKIP_SYNC=0
SKIP_MCP=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: install-sentinel-x.sh [options]

  --with-ui              Enable sentinel-ui systemd
  --with-api             Enable sentinel-api systemd (W7 webhook)
  --with-prometheus      Run dist/kube-prometheus-offline install (bundle required)
  --with-prom-sync       Install sync-prom env + optional cron hint
  --with-sandbox         Build sentinel-x-sandbox Docker image (W6)
  --with-fixtures        Apply crash-demo fixture + busybox offline import (implies --with-sandbox)
  --no-patrol            Skip patrol cron line (default: patrol enabled in cron template)
  --skip-sync            Skip first K8s sync
  --skip-mcp             Skip docker-compose MCP (already running)
  --env-file PATH        Master env (default: /etc/sentinel/sentinel-x.env)
  --dry-run              Print steps only
  -h, --help             This help

Prerequisites: k3s (or kubectl + kubeconfig), docker, python3, helm (if --with-prometheus)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-ui) WITH_UI=1 ;;
    --with-api) WITH_API=1 ;;
    --with-prometheus) WITH_PROMETHEUS=1 ;;
    --with-prom-sync) WITH_PROM_SYNC=1 ;;
    --with-sandbox) WITH_SANDBOX=1 ;;
    --with-fixtures) WITH_FIXTURES=1; WITH_SANDBOX=1 ;;
    --no-patrol) WITH_PATROL=0 ;;
    --skip-sync) SKIP_SYNC=1 ;;
    --skip-mcp) SKIP_MCP=1 ;;
    --env-file) ENV_MASTER="$2"; shift ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

log() { echo "[install-sentinel-x] $*"; }
die() { echo "[install-sentinel-x] ERROR: $*" >&2; exit 1; }

# shellcheck source=../config/lib/config-common.sh
. "${DEPLOY_CONFIG}/lib/config-common.sh"

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY: $*"
  else
    "$@"
  fi
}

strip_crlf_dir() {
  local dir="$1"
  [[ -d "$dir" ]] || return 0
  find "$dir" -name '*.sh' -exec sed -i 's/\r$//' {} + 2>/dev/null || true
  find "$dir" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
}

# First existing path (Windows scp/tar often drops +x; invoke via bash).
resolve_deploy_script() {
  local label="$1"
  shift
  local p
  for p in "$@"; do
    if [[ -f "$p" ]]; then
      echo "$p"
      return 0
    fi
  done
  die "missing ${label} (checked: $*)"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing: $1"
}

docker_compose() {
  config_docker_compose
}

compute_thread_id() {
  config_compute_thread_id "${SENTINEL_ROOT:-$ROOT}" "$1" "${2:-}"
}

detect_mcp_container() {
  config_detect_mcp_container "$1"
}

kubectl_install() {
  local kc="${K3S_KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
  if [[ -f "$kc" ]]; then
    kubectl --kubeconfig="$kc" "$@"
  else
    kubectl "$@"
  fi
}

install_sandbox_image() {
  local sandbox_dir="${SENTINEL_ROOT}/sandbox"
  [[ -d "$sandbox_dir" ]] || die "sandbox dir missing: $sandbox_dir"
  local kubectl_bin
  kubectl_bin="$(command -v kubectl || true)"
  [[ -n "$kubectl_bin" ]] || die "--with-sandbox requires kubectl in PATH"
  log "copying kubectl into sandbox/"
  run cp "$kubectl_bin" "${sandbox_dir}/kubectl"
  run chmod +x "${sandbox_dir}/kubectl"
  run mkdir -p "${sandbox_dir}/audit"
  log "building sentinel-x-sandbox:latest"
  run docker build -t "${SENTINEL_SANDBOX_IMAGE:-sentinel-x-sandbox:latest}" "$sandbox_dir"
}

import_busybox_for_fixtures() {
  local mirror="${SENTINEL_BUSYBOX_IMAGE:-docker.m.daocloud.io/library/busybox:1.36}"
  local target="${SENTINEL_BUSYBOX_K3S_TAG:-docker.io/library/busybox:1.36}"
  log "importing busybox for fixtures: $mirror"
  if ! run docker pull "$mirror"; then
    log "WARN: busybox pull failed — fixture may ImagePullBackOff"
    return 0
  fi
  local tar="/tmp/sentinel-busybox.tar"
  run docker save "$mirror" -o "$tar"
  if command -v k3s >/dev/null 2>&1; then
    run k3s ctr images import "$tar"
    run k3s ctr images tag "$mirror" "$target" 2>/dev/null || true
  else
    log "WARN: k3s not in PATH — skip ctr import"
  fi
  run rm -f "$tar"
}

install_fixtures() {
  local fixture="${SENTINEL_ROOT}/sandbox/fixtures/crash-loop-deployment.yaml"
  [[ -f "$fixture" ]] || die "fixture missing: $fixture"
  import_busybox_for_fixtures
  log "applying sandbox fixtures"
  run kubectl_install apply -f "$fixture"
  log "waiting for crash-demo pod (may stay CrashLoopBackOff — expected)"
  kubectl_install wait --for=condition=Ready pod -l app=crash-demo -n sentinel-sandbox --timeout=30s 2>/dev/null || \
    log "WARN: crash-demo not Ready (CrashLoop is expected for W6 demo)"
}

# --- Preflight ---
[[ "$(id -u)" -eq 0 ]] || die "run as root (sudo)"
[[ -d "$ROOT/agents/langgraph-integration" ]] || die "repo not found at SENTINEL_ROOT=$ROOT"

log "ROOT=$ROOT"
strip_crlf_dir "$SENTINEL_DEPLOY_ROOT"

require_cmd docker
require_cmd python3
if [[ "$SKIP_MCP" -eq 0 ]]; then
  require_cmd kubectl || log "WARN: kubectl not in PATH (k3s may still provide /etc/rancher/k3s/k3s.yaml)"
fi

# --- Master env ---
mkdir -p /etc/sentinel
if [[ ! -f "$ENV_MASTER" ]]; then
  if [[ -f "${DEPLOY_CONFIG}/sentinel-x.env.example" ]]; then
    install -m 600 "${DEPLOY_CONFIG}/sentinel-x.env.example" "$ENV_MASTER"
    sed -i 's/\r$//' "$ENV_MASTER"
    log "created $ENV_MASTER from example"
  else
    die "missing $ENV_MASTER and sentinel-x.env.example"
  fi
else
  sed -i 's/\r$//' "$ENV_MASTER"
  log "using existing $ENV_MASTER"
fi

# shellcheck disable=SC1090
set -a
source <(sed 's/\r$//' "$ENV_MASTER")
set +a

SENTINEL_ROOT="${SENTINEL_ROOT:-$ROOT}"
CLUSTER_ID="${CLUSTER_ID:-k3s-prod}"
NAMESPACE="${NAMESPACE:-kube-system}"
LANGGRAPH_API_URL="${LANGGRAPH_API_URL:-http://127.0.0.1:2024}"
K3S_KUBECONFIG="${K3S_KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
KUBECONFIG_TARGET="${KUBECONFIG_TARGET:-/root/.kube/config}"
KUBECONFIG_SERVER="${KUBECONFIG_SERVER:-host-ip}"
PROMETHEUS_BASE_URL="${PROMETHEUS_BASE_URL:-http://host.docker.internal:30909}"

# --- Python venv ---
if [[ ! -x "${SENTINEL_ROOT}/.venv/bin/python" ]]; then
  log "creating venv at ${SENTINEL_ROOT}/.venv"
  run python3 -m venv "${SENTINEL_ROOT}/.venv"
fi
VENV_PY="${SENTINEL_ROOT}/.venv/bin/python"
run "$VENV_PY" -m pip install -q --upgrade pip
run "$VENV_PY" -m pip install -q -U "langgraph-cli[inmem]"
run "$VENV_PY" -m pip install -q -r "${SENTINEL_ROOT}/agents/langgraph-server/requirements.txt"
run "$VENV_PY" -m pip install -q -r "${SENTINEL_ROOT}/agents/langgraph-integration/requirements.txt"
if [[ "$WITH_UI" -eq 1 ]]; then
  run "$VENV_PY" -m pip install -q -r "${SENTINEL_ROOT}/apps/ui/requirements.txt"
fi
if [[ "$WITH_API" -eq 1 ]]; then
  run "$VENV_PY" -m pip install -q -r "${SENTINEL_ROOT}/apps/api/requirements.txt"
fi

# thread_id
if [[ -z "${LANGGRAPH_THREAD_ID:-}" ]]; then
  LANGGRAPH_THREAD_ID="$(compute_thread_id "$CLUSTER_ID" "${TENANT_ID:-}")"
  log "LANGGRAPH_THREAD_ID=$LANGGRAPH_THREAD_ID (from CLUSTER_ID=$CLUSTER_ID)"
fi

# --- Deploy scripts to /usr/local/bin ---
INSTALL_DEPLOY_SCRIPTS="$(resolve_deploy_script install-deploy-scripts.sh \
  "${DEPLOY_INSTALL}/install-deploy-scripts.sh" \
  "${SENTINEL_DEPLOY_ROOT}/install-deploy-scripts.sh")"
run bash "$INSTALL_DEPLOY_SCRIPTS"

# --- Kubeconfig for MCP ---
if [[ -f "${DEPLOY_SYNC}/sync-kubeconfig-for-mcp.sh" ]]; then
  run env K3S_KUBECONFIG="$K3S_KUBECONFIG" KUBECONFIG_TARGET="$KUBECONFIG_TARGET" \
    KUBECONFIG_SERVER="$KUBECONFIG_SERVER" \
    bash "${DEPLOY_SYNC}/sync-kubeconfig-for-mcp.sh"
fi

# --- Optional Prometheus stack ---
if [[ "$WITH_PROMETHEUS" -eq 1 ]]; then
  BUNDLE="${SENTINEL_ROOT}/dist/kube-prometheus-offline"
  if [[ -f "${BUNDLE}/install-kube-prometheus-offline.sh" ]]; then
    sed -i 's/\r$//' "${BUNDLE}/install-kube-prometheus-offline.sh" 2>/dev/null || true
    run env SENTINEL_ROOT="$SENTINEL_ROOT" bash "${BUNDLE}/install-kube-prometheus-offline.sh"
  else
    die "--with-prometheus requires ${BUNDLE}/ (offline bundle)"
  fi
fi

# --- MCP .env + compose ---
MCP_COMPOSE="${SENTINEL_ROOT}/mcp-servers/compose"
MCP_ENV="${MCP_COMPOSE}/.env"
if [[ ! -f "$MCP_ENV" ]] && [[ -f "${MCP_COMPOSE}/.env.example" ]]; then
  run cp "${MCP_COMPOSE}/.env.example" "$MCP_ENV"
fi
if [[ -f "$MCP_ENV" ]]; then
  run sed -i 's/\r$//' "$MCP_ENV"
  if grep -q '^PROMETHEUS_BASE_URL=' "$MCP_ENV" 2>/dev/null; then
    run sed -i "s|^PROMETHEUS_BASE_URL=.*|PROMETHEUS_BASE_URL=${PROMETHEUS_BASE_URL}|" "$MCP_ENV"
  else
    echo "PROMETHEUS_BASE_URL=${PROMETHEUS_BASE_URL}" >>"$MCP_ENV"
  fi
fi

if [[ "$SKIP_MCP" -eq 0 ]]; then
  DC="$(docker_compose)"
  MCP_DIR="${SENTINEL_ROOT}/mcp-servers/compose"
  # docker-compose 1.29 recreate workaround
  for svc in mcp-k8s mcp-prometheus; do
    cid="$(docker ps -aq -f "name=${svc}" 2>/dev/null | head -1 || true)"
    [[ -n "$cid" ]] && run docker rm -f "$cid" 2>/dev/null || true
  done
  log "starting MCP containers in $MCP_DIR"
  run bash -c "cd '$MCP_DIR' && $DC build mcp-k8s mcp-prometheus"
  run bash -c "cd '$MCP_DIR' && unset PROMETHEUS_BASE_URL && $DC up -d mcp-k8s mcp-prometheus"
fi

MCP_K8S_CONTAINER="${MCP_K8S_CONTAINER:-$(detect_mcp_container sentinel-x-mcp-k8s:latest)}"
MCP_PROM_CONTAINER="${MCP_PROM_CONTAINER:-$(detect_mcp_container sentinel-x-mcp-prometheus:latest)}"
[[ -n "$MCP_K8S_CONTAINER" ]] || die "MCP K8s container not found; check docker ps"
log "MCP_K8S_CONTAINER=$MCP_K8S_CONTAINER"
log "MCP_PROM_CONTAINER=${MCP_PROM_CONTAINER:-<none>}"

# --- Discover + apply child env files ---
APPLY_ARGS=(--discover)
[[ "$WITH_UI" -eq 1 ]] && APPLY_ARGS+=(--with-ui)
[[ "$WITH_API" -eq 1 ]] && APPLY_ARGS+=(--with-api)
[[ "$WITH_PROM_SYNC" -eq 1 ]] && APPLY_ARGS+=(--with-prom-sync)
run bash "${DEPLOY_CONFIG}/sentinel-config-discover.sh" --write --env-file "$ENV_MASTER"
run bash "${DEPLOY_CONFIG}/sentinel-config-apply.sh" "${APPLY_ARGS[@]}" --env-file "$ENV_MASTER"

# Recreate MCP prom so env_file .env wins over any stale container env (AUTO from early source).
if [[ "$SKIP_MCP" -eq 0 ]]; then
  DC="$(docker_compose)"
  MCP_DIR="${SENTINEL_ROOT}/mcp-servers/compose"
  run bash -c "cd '$MCP_DIR' && unset PROMETHEUS_BASE_URL && $DC up -d --force-recreate mcp-prometheus"
fi

# shellcheck disable=SC1090
set -a
source <(grep -v '^\s*#' "$ENV_MASTER" | grep -v '^\s*$' || true)
source <(grep -v '^\s*#' /etc/sentinel/sync-k8s.env | grep -v '^\s*$' || true)
set +a

# --- LangGraph .env minimal ---
LG_ENV="${SENTINEL_ROOT}/agents/langgraph-server/.env"
if [[ ! -f "$LG_ENV" ]]; then
  printf 'LANGGRAPH_API_URL=%s\n' "$LANGGRAPH_API_URL" >"$LG_ENV"
  chmod 600 "$LG_ENV"
fi

# --- systemd ---
run cp "${DEPLOY_SYSTEMD}/sentinel-langgraph.service" /etc/systemd/system/sentinel-langgraph.service
run sed -i "s|/opt/sentinel-x|${SENTINEL_ROOT}|g" /etc/systemd/system/sentinel-langgraph.service
run chmod +x "${DEPLOY_SYSTEMD}/sentinel-langgraph-post-restart.sh" 2>/dev/null || true
run chmod +x "${SENTINEL_DEPLOY_ROOT}/sentinel-langgraph-post-restart.sh" 2>/dev/null || true
run systemctl daemon-reload
run systemctl enable sentinel-langgraph.service
run systemctl restart sentinel-langgraph.service

if [[ "$WITH_UI" -eq 1 ]]; then
  run cp "${DEPLOY_SYSTEMD}/sentinel-ui.service" /etc/systemd/system/sentinel-ui.service
  run sed -i "s|/opt/sentinel-x|${SENTINEL_ROOT}|g" /etc/systemd/system/sentinel-ui.service
  run systemctl daemon-reload
  run systemctl enable sentinel-ui.service
  run systemctl restart sentinel-ui.service
fi

if [[ "$WITH_API" -eq 1 ]]; then
  run cp "${DEPLOY_SYSTEMD}/sentinel-api.service" /etc/systemd/system/sentinel-api.service
  run sed -i "s|/opt/sentinel-x|${SENTINEL_ROOT}|g" /etc/systemd/system/sentinel-api.service
  run systemctl daemon-reload
  run systemctl enable sentinel-api.service
  run systemctl restart sentinel-api.service
fi

# --- cron template ---
if [[ -f "${DEPLOY_SYNC}/cron-sentinel-sync.example" ]] && [[ ! -f /etc/cron.d/sentinel-sync ]]; then
  run cp "${DEPLOY_SYNC}/cron-sentinel-sync.example" /etc/cron.d/sentinel-sync
  if [[ "$WITH_PATROL" -eq 0 ]]; then
    run sed -i '/sentinel-inspect-patrol/d' /etc/cron.d/sentinel-sync
  fi
  run chmod 644 /etc/cron.d/sentinel-sync
  run sed -i 's/\r$//' /etc/cron.d/sentinel-sync
  log "installed /etc/cron.d/sentinel-sync (K8s sync every 5 min; patrol=$WITH_PATROL)"
fi

# --- Sandbox image + fixtures (W6) ---
if [[ "$WITH_SANDBOX" -eq 1 ]]; then
  install_sandbox_image
fi
if [[ "$WITH_FIXTURES" -eq 1 ]]; then
  install_fixtures
fi

# --- Wait for LangGraph ---
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf --connect-timeout 2 "${LANGGRAPH_API_URL%/}/ok" >/dev/null 2>&1; then
    log "LangGraph OK at $LANGGRAPH_API_URL"
    break
  fi
  sleep 2
  [[ "$i" -eq 10 ]] && die "LangGraph not reachable at $LANGGRAPH_API_URL"
done

# --- First sync ---
if [[ "$SKIP_SYNC" -eq 0 ]]; then
  log "running first K8s sync..."
  run env SENTINEL_SYNC_ENV=/etc/sentinel/sync-k8s.env /usr/local/bin/sentinel-sync-k8s.sh || \
    log "WARN: first sync failed (check MCP kubeconfig and k3s)"
  if [[ "$WITH_PROM_SYNC" -eq 1 ]] && [[ -f /etc/sentinel/sync-prom.env ]]; then
    log "running first Prom metrics sync..."
    run env SENTINEL_PROM_SYNC_ENV=/etc/sentinel/sync-prom.env /usr/local/bin/sentinel-sync-prom.sh || \
      log "WARN: prom sync failed (Prometheus reachable?)"
  fi
  if [[ "$WITH_FIXTURES" -eq 1 ]]; then
    log "syncing sentinel-sandbox (crash-demo fixture) into graph..."
    run env SENTINEL_SYNC_ENV=/etc/sentinel/sync-k8s.env NAMESPACE=sentinel-sandbox \
      /usr/local/bin/sentinel-sync-k8s.sh || \
      log "WARN: sentinel-sandbox sync failed"
  fi
fi

# --- Summary ---
log "=========================================="
log "Sentinel-X install finished"
log "  SENTINEL_ROOT=$SENTINEL_ROOT"
log "  LANGGRAPH_THREAD_ID=$LANGGRAPH_THREAD_ID"
log "  MCP_K8S=$MCP_K8S_CONTAINER"
log "=========================================="
cat <<EOF

Next steps:
  1) Verify:  sudo bash ${DEPLOY_VERIFY}/verify-sentinel-x.sh
  2) Full W5-W7: sudo bash ${DEPLOY_VERIFY}/verify-sentinel-x.sh --full
  2) Logs:    journalctl -u sentinel-langgraph -f
  3) Sync:    tail -f ${SENTINEL_SYNC_LOG:-/var/log/sentinel-sync.log}
  4) Query:   export LANGGRAPH_THREAD_ID=$LANGGRAPH_THREAD_ID
  5) Docs:    ${SENTINEL_ROOT}/docs/deploy/DEPLOY-ONE-SHOT.md

Optional Prom cron (after K8s sync):
  */10 * * * * root /usr/local/bin/sentinel-sync-prom.sh

UI SSH tunnel:
  ssh -L 8501:127.0.0.1:8501 root@<host>

EOF
