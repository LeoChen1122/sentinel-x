#!/usr/bin/env bash
# W3: Prometheus MCP -> LangGraph pod metrics sync (for cron or manual run).
set -uo pipefail

ENV_FILE="${SENTINEL_PROM_SYNC_ENV:-/etc/sentinel/sync-prom.env}"
LOCK_FILE="${SENTINEL_PROM_SYNC_LOCK:-/var/run/sentinel-prom-sync.lock}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source <(sed 's/\r$//' "$ENV_FILE")
  set +a
fi

SENTINEL_ROOT="${SENTINEL_ROOT:-/opt/sentinel-x}"
VENV_PYTHON="${VENV_PYTHON:-${SENTINEL_ROOT}/.venv/bin/python}"
SYNC_SCRIPT="${SENTINEL_ROOT}/agents/langgraph-integration/scripts/live/mcp_prom_sync_live.py"
LOG_FILE="${SENTINEL_PROM_SYNC_LOG:-/var/log/sentinel-prom-sync.log}"

MCP_K8S_CONTAINER="${MCP_K8S_CONTAINER:-${MCP_CONTAINER:-}}"
MCP_PROM_CONTAINER="${MCP_PROM_CONTAINER:-}"
CLUSTER_ID="${CLUSTER_ID:-k3s-prod}"
NAMESPACE="${NAMESPACE:-kube-system}"
LANGGRAPH_API_URL="${LANGGRAPH_API_URL:-http://127.0.0.1:2024}"

export LANGGRAPH_API_URL
export MCP_K8S_CONTAINER MCP_PROM_CONTAINER CLUSTER_ID NAMESPACE
export PYTHONPATH="${SENTINEL_ROOT}/agents/langgraph-integration/src${PYTHONPATH:+:${PYTHONPATH}}"
export LANGGRAPH_SYNC_STATE_PATH="${LANGGRAPH_SYNC_STATE_PATH:-/var/lib/sentinel/sync-state}"
export LANGGRAPH_SYNC_INCREMENTAL="${LANGGRAPH_SYNC_INCREMENTAL:-1}"
[[ -n "${TENANT_ID:-}" ]] && export TENANT_ID
[[ -n "${LANGGRAPH_THREAD_ID:-}" ]] && export LANGGRAPH_THREAD_ID

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG_FILE"
}

mkdir -p "$(dirname "$LOG_FILE")" "${LANGGRAPH_SYNC_STATE_PATH}" 2>/dev/null || true

if [[ ! -x "$VENV_PYTHON" ]]; then
  log "ERROR: python not found: $VENV_PYTHON"
  exit 1
fi
if [[ ! -f "$SYNC_SCRIPT" ]]; then
  log "ERROR: sync script not found: $SYNC_SCRIPT"
  exit 1
fi
if [[ -z "$MCP_K8S_CONTAINER" ]]; then
  log "ERROR: MCP_K8S_CONTAINER empty; set in $ENV_FILE"
  exit 1
fi
if [[ -z "$MCP_PROM_CONTAINER" ]]; then
  log "ERROR: MCP_PROM_CONTAINER empty; set in $ENV_FILE"
  exit 1
fi

run_sync() {
  log "START prom sync cluster=$CLUSTER_ID namespace=$NAMESPACE k8s=$MCP_K8S_CONTAINER prom=$MCP_PROM_CONTAINER"
  if ! curl -sf --connect-timeout 3 "${LANGGRAPH_API_URL%/}/ok" >/dev/null 2>&1; then
    log "WARN: LangGraph not reachable at $LANGGRAPH_API_URL (is sentinel-langgraph running?)"
  fi
  "$VENV_PYTHON" "$SYNC_SCRIPT" --skip-verify 2>&1 | while IFS= read -r line; do
    log "$line"
  done
  local rc=${PIPESTATUS[0]}
  if [[ "$rc" -eq 0 ]]; then
    log "OK prom sync finished"
  else
    log "ERROR prom sync exit code=$rc"
  fi
  return "$rc"
}

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    log "SKIP another prom sync is running (lock $LOCK_FILE)"
    exit 0
  fi
  run_sync
else
  run_sync
fi
