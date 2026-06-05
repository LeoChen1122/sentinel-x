#!/usr/bin/env bash
# Auto-discover Sentinel-X runtime parameters and optionally write to master env.
#
#   sudo bash deploy/config/sentinel-config-discover.sh           # print report
#   sudo bash deploy/config/sentinel-config-discover.sh --write   # merge into sentinel-x.env
#
set -euo pipefail

ROOT="${SENTINEL_ROOT:-/opt/sentinel-x}"
# shellcheck source=lib/paths.sh
. "${ROOT}/deploy/config/lib/paths.sh"
ENV_MASTER="${SENTINEL_X_ENV:-/etc/sentinel/sentinel-x.env}"
WRITE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --write) WRITE=1 ;;
    --env-file) ENV_MASTER="$2"; shift ;;
    -h|--help)
      echo "Usage: sentinel-config-discover.sh [--write] [--env-file PATH]"
      exit 0
      ;;
    *) echo "Unknown: $1" >&2; exit 1 ;;
  esac
  shift
done

# shellcheck source=lib/config-common.sh
. "${DEPLOY_CONFIG}/lib/config-common.sh"

[[ "$(id -u)" -eq 0 ]] || config_die "run as root (sudo)"
mkdir -p /etc/sentinel

if [[ ! -f "$ENV_MASTER" ]]; then
  if [[ -f "${DEPLOY_CONFIG}/sentinel-x.env.example" ]]; then
    install -m 600 "${DEPLOY_CONFIG}/sentinel-x.env.example" "$ENV_MASTER"
    config_strip_crlf "$ENV_MASTER"
  else
    config_die "missing $ENV_MASTER"
  fi
fi
config_strip_crlf "$ENV_MASTER"

# shellcheck disable=SC1090
set -a
source <(grep -v '^\s*#' "$ENV_MASTER" | grep -v '^\s*$' || true)
set +a

SENTINEL_ROOT="${SENTINEL_ROOT:-$ROOT}"
CLUSTER_ID="${CLUSTER_ID:-k3s-prod}"
NAMESPACE="${NAMESPACE:-kube-system}"
LANGGRAPH_API_URL="${LANGGRAPH_API_URL:-http://127.0.0.1:2024}"
KUBE_PROM_NODE_PORT="${KUBE_PROM_NODE_PORT:-30909}"

DISCOVER_MCP_K8S="$(config_detect_mcp_container sentinel-x-mcp-k8s:latest || true)"
DISCOVER_MCP_PROM="$(config_detect_mcp_container sentinel-x-mcp-prometheus:latest || true)"
DISCOVER_PROM_URL="$(config_detect_prometheus_url "$KUBE_PROM_NODE_PORT")"
DISCOVER_HOST_IP="$(config_detect_host_ip)"
DISCOVER_LANGGRAPH_OK="no"
config_langgraph_ok "$LANGGRAPH_API_URL" && DISCOVER_LANGGRAPH_OK="yes"

if [[ -x "${SENTINEL_ROOT}/.venv/bin/python" ]]; then
  DISCOVER_THREAD_ID="$(config_compute_thread_id "$SENTINEL_ROOT" "$CLUSTER_ID" "${TENANT_ID:-}")"
else
  DISCOVER_THREAD_ID="${LANGGRAPH_THREAD_ID:-}"
fi

cat <<EOF
=== Sentinel-X discover report ===
SENTINEL_ROOT=${SENTINEL_ROOT}
CLUSTER_ID=${CLUSTER_ID}
NAMESPACE=${NAMESPACE}
LANGGRAPH_API_URL=${LANGGRAPH_API_URL} (ok=${DISCOVER_LANGGRAPH_OK})
LANGGRAPH_THREAD_ID=${DISCOVER_THREAD_ID}
MCP_K8S_CONTAINER=${DISCOVER_MCP_K8S:-<not running>}
MCP_PROM_CONTAINER=${DISCOVER_MCP_PROM:-<not running>}
PROMETHEUS_BASE_URL=${DISCOVER_PROM_URL}
HOST_IP=${DISCOVER_HOST_IP:-<unknown>}
EOF

if [[ "$WRITE" -eq 0 ]]; then
  echo ""
  echo "Run with --write to update $ENV_MASTER (AUTO/empty fields only)."
  exit 0
fi

config_env_set_if_auto "$ENV_MASTER" MCP_K8S_CONTAINER "$DISCOVER_MCP_K8S" && \
  config_log "set MCP_K8S_CONTAINER=$DISCOVER_MCP_K8S" || true
config_env_set_if_auto "$ENV_MASTER" MCP_PROM_CONTAINER "$DISCOVER_MCP_PROM" && \
  config_log "set MCP_PROM_CONTAINER=$DISCOVER_MCP_PROM" || true
config_env_set_if_auto "$ENV_MASTER" PROMETHEUS_BASE_URL "$DISCOVER_PROM_URL" && \
  config_log "set PROMETHEUS_BASE_URL=$DISCOVER_PROM_URL" || true
config_env_set_if_auto "$ENV_MASTER" LANGGRAPH_THREAD_ID "$DISCOVER_THREAD_ID" && \
  config_log "set LANGGRAPH_THREAD_ID=$DISCOVER_THREAD_ID" || true

if [[ -n "$DISCOVER_MCP_K8S" ]]; then
  grep -qE '^MCP_K8S_CONTAINER=' "$ENV_MASTER" || echo "MCP_K8S_CONTAINER=${DISCOVER_MCP_K8S}" >>"$ENV_MASTER"
fi
if [[ -n "$DISCOVER_MCP_PROM" ]]; then
  grep -qE '^MCP_PROM_CONTAINER=' "$ENV_MASTER" || echo "MCP_PROM_CONTAINER=${DISCOVER_MCP_PROM}" >>"$ENV_MASTER"
fi

config_log "updated $ENV_MASTER (explicit values preserved; AUTO/empty merged)"
