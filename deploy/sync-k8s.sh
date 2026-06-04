#!/usr/bin/env bash
# W1-3: K8s MCP -> LangGraph incremental sync (for cron or manual run).
set -uo pipefail

ENV_FILE="${SENTINEL_SYNC_ENV:-/etc/sentinel/sync-k8s.env}"
LOCK_FILE="${SENTINEL_SYNC_LOCK:-/var/run/sentinel-sync.lock}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  # Strip CRLF (common when env was edited/uploaded from Windows)
  source <(sed 's/\r$//' "$ENV_FILE")
  set +a
fi

SENTINEL_ROOT="${SENTINEL_ROOT:-/opt/sentinel-x}"
VENV_PYTHON="${VENV_PYTHON:-${SENTINEL_ROOT}/.venv/bin/python}"
SYNC_SCRIPT="${SENTINEL_ROOT}/agents/langgraph-integration/scripts/mcp_k8s_sync_live.py"
LOG_FILE="${SENTINEL_SYNC_LOG:-/var/log/sentinel-sync.log}"

MCP_CONTAINER="${MCP_CONTAINER:-}"
CLUSTER_ID="${CLUSTER_ID:-k3s-prod}"
NAMESPACE="${NAMESPACE:-kube-system}"
LANGGRAPH_API_URL="${LANGGRAPH_API_URL:-http://127.0.0.1:2024}"

export LANGGRAPH_API_URL
export MCP_CONTAINER CLUSTER_ID NAMESPACE
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
if [[ -z "$MCP_CONTAINER" ]]; then
  log "ERROR: MCP_CONTAINER empty; set in $ENV_FILE"
  exit 1
fi

run_sync() {
  log "START sync cluster=$CLUSTER_ID namespace=$NAMESPACE mcp=$MCP_CONTAINER"
  if ! curl -sf --connect-timeout 3 "${LANGGRAPH_API_URL%/}/ok" >/dev/null 2>&1; then
    log "WARN: LangGraph not reachable at $LANGGRAPH_API_URL (is sentinel-langgraph running?)"
  fi
  "$VENV_PYTHON" "$SYNC_SCRIPT" --skip-verify 2>&1 | while IFS= read -r line; do
    log "$line"
  done
  local rc=${PIPESTATUS[0]}
  if [[ "$rc" -eq 0 ]]; then
    log "OK sync finished"
  else
    log "ERROR sync exit code=$rc"
  fi
  return "$rc"
}

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    log "SKIP another sync is running (lock $LOCK_FILE)"
    exit 0
  fi
  run_sync
else
  run_sync
fi
