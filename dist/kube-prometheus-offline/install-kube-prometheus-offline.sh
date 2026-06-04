#!/bin/bash
# DO NOT EDIT — copy from deploy/install-kube-prometheus-offline.sh via prepare-kube-prometheus-offline.ps1
# Install kube-prometheus-stack on k3s without GitHub access.
# Run from bundle dir prepared by scripts/prepare-kube-prometheus-offline.ps1 (or manual helm pull).
#
#   cd /opt/sentinel-x/dist/kube-prometheus-offline
#   sudo bash install-kube-prometheus-offline.sh
#
set -eu

RELEASE="${KUBE_PROM_RELEASE:-kube-prom}"
NAMESPACE="${KUBE_PROM_NAMESPACE:-monitoring}"
ROOT="${SENTINEL_ROOT:-/opt/sentinel-x}"
BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CHART_DIR="${KUBE_PROM_CHART_DIR:-${BUNDLE_DIR}/kube-prometheus-stack}"
VALUES="${KUBE_PROM_VALUES:-${BUNDLE_DIR}/kube-prometheus-values-minimal.yaml}"
OFFLINE_REPO="${HELM_OFFLINE_REPO:-${BUNDLE_DIR}/helm-local-repo}"
NODE_PORT="${KUBE_PROM_NODE_PORT:-30909}"
MCP_ENV="${ROOT}/mcp-servers/.env"

log() { echo "[install-kube-prometheus] $*"; }
die() { echo "[install-kube-prometheus] ERROR: $*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1 (install helm 3 + kubectl)"
}

resolve_chart() {
  if [[ -f "${CHART_DIR}/Chart.yaml" ]]; then
    log "using chart dir: ${CHART_DIR}"
    return 0
  fi
  if [[ -d "${OFFLINE_REPO}" ]] && [[ -f "${OFFLINE_REPO}/index.yaml" ]]; then
    log "using offline repo: ${OFFLINE_REPO}"
    CHART_REF="kube-prometheus-stack"
    return 0
  fi
  die "no chart found. Expected ${CHART_DIR}/Chart.yaml or ${OFFLINE_REPO}/index.yaml"
}

install_or_upgrade() {
  local extra=()
  if helm status "${RELEASE}" -n "${NAMESPACE}" >/dev/null 2>&1; then
    extra+=(upgrade)
    log "upgrading release ${RELEASE}"
  else
    extra+=(install)
    log "installing release ${RELEASE}"
  fi

  if [[ -n "${CHART_REF:-}" ]]; then
    helm "${extra[@]}" "${RELEASE}" "${CHART_REF}" \
      --repo "file://${OFFLINE_REPO}" \
      -n "${NAMESPACE}" --create-namespace \
      -f "${VALUES}" \
      --wait --timeout 15m
  else
    helm "${extra[@]}" "${RELEASE}" "${CHART_DIR}" \
      -n "${NAMESPACE}" --create-namespace \
      -f "${VALUES}" \
      --wait --timeout 15m
  fi
}

wait_prometheus_ready() {
  log "waiting for prometheus pod..."
  kubectl -n "${NAMESPACE}" wait --for=condition=Ready pod \
    -l app.kubernetes.io/name=prometheus \
    --timeout=600s 2>/dev/null || true
}

verify_nodeport() {
  local url="http://127.0.0.1:${NODE_PORT}/-/ready"
  for i in $(seq 1 30); do
    if curl -sf "${url}" >/dev/null; then
      log "Prometheus ready at ${url}"
      return 0
    fi
    sleep 5
  done
  die "Prometheus not reachable at ${url}. Check: kubectl get pods,svc -n ${NAMESPACE}"
}

verify_container_metrics() {
  local q="container_cpu_usage_seconds_total"
  local n
  n="$(curl -sf "http://127.0.0.1:${NODE_PORT}/api/v1/query?query=${q}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(len(d.get('data',{}).get('result',[]) or []))
" 2>/dev/null || echo 0)"
  log "container_cpu_usage_seconds_total series count: ${n}"
  if [[ "${n}" == "0" ]]; then
    log "WARN: no container_cpu series yet — wait 2-5 min for scrape or check node-exporter/cAdvisor"
  fi
}

configure_mcp_prometheus_url() {
  local url="http://host.docker.internal:${NODE_PORT}"
  mkdir -p "$(dirname "${MCP_ENV}")"
  if [[ -f "${MCP_ENV}" ]] && grep -q '^PROMETHEUS_BASE_URL=' "${MCP_ENV}"; then
    sed -i "s|^PROMETHEUS_BASE_URL=.*|PROMETHEUS_BASE_URL=${url}|" "${MCP_ENV}"
  else
    echo "PROMETHEUS_BASE_URL=${url}" >> "${MCP_ENV}"
  fi
  log "wrote ${MCP_ENV}: PROMETHEUS_BASE_URL=${url}"

  if [[ -d "${ROOT}/mcp-servers" ]]; then
    (cd "${ROOT}/mcp-servers" && docker-compose up -d mcp-prometheus) || true
    local prom_c
    prom_c="$(docker ps --format '{{.Names}}' | grep -E 'mcp-prometheus' | head -1 || true)"
    if [[ -n "${prom_c}" ]]; then
      docker exec -i "${prom_c}" curl -sf "${url}/-/ready" >/dev/null \
        && log "MCP container can reach Prometheus" \
        || log "WARN: MCP container cannot reach ${url} — check extra_hosts in docker-compose.yml"
    fi
  fi
}

main() {
  require_cmd helm
  require_cmd kubectl
  require_cmd curl
  [[ -f "${VALUES}" ]] || die "values file missing: ${VALUES}"

  sed -i 's/\r$//' "${BASH_SOURCE[0]}" 2>/dev/null || true

  resolve_chart
  install_or_upgrade
  wait_prometheus_ready
  verify_nodeport
  verify_container_metrics
  configure_mcp_prometheus_url

  cat <<EOF

=== Done ===
Prometheus:  http://127.0.0.1:${NODE_PORT}
MCP URL:     http://host.docker.internal:${NODE_PORT}

Next (W3):
  source ${ROOT}/.venv/bin/activate
  export LANGGRAPH_API_URL=http://127.0.0.1:2024
  export MCP_PROM_CONTAINER=\$(docker ps --format '{{.Names}}' | grep mcp-prometheus | head -1)
  export MCP_K8S_CONTAINER=\$(docker ps --format '{{.Names}}' | grep mcp-k8s | head -1)
  export CLUSTER_ID=k3s-prod NAMESPACE=kube-system
  python ${ROOT}/agents/langgraph-integration/scripts/mcp_prom_sync_live.py

See: ${ROOT}/docs/DEPLOY-PROM-SYNC.md
EOF
}

main "$@"
